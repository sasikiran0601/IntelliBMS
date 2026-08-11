"""
train_rul_all_batteries.py
===========================
Step 1: Reads ALL 38 battery discharge + impedance CSV files (B0005–B0056)
Step 2: Computes cycle-level features per battery (20 features)
Step 3: Generates RUL labels (direct if EOL reached, exponential decay extrapolation otherwise)
Step 4: Trains XGBoost regressor
Step 5: Saves rul_model.pkl to project root (app loads this)

Run from project root:
    python scripts/train_rul_all_batteries.py
"""

from __future__ import annotations

from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from scipy.optimize import curve_fit
from sklearn.metrics import mean_absolute_error, r2_score
from sklearn.model_selection import GroupKFold
# pyrefly: ignore [missing-import]
from xgboost import XGBRegressor

# ── Paths ─────────────────────────────────────────────────────────────────────
ROOT        = Path(__file__).resolve().parents[1]
CSV_BASE    = ROOT / "datasets" / "04_Converted_CSV" / "5. Battery Data Set"
FEATURES_DIR = ROOT / "datasets" / "04_Converted_CSV" / "engineered_features" / "rul_outputs"
RUL_MODEL_PATH = ROOT / "rul_model.pkl"   # app will load from here

FEATURES_DIR.mkdir(parents=True, exist_ok=True)

# End-of-life SOH threshold
EOL_SOH = 70.0

# Columns we need from raw CSV
USECOLS = [
    "cycle_id", "type", "ambient_temperature",
    "Voltage_measured", "Current_measured", "Temperature_measured",
    "Time", "Capacity", "Re", "Rct"
]

FEATURE_COLS = [
    "soh",
    "discharge_capacity_ah",
    "discharge_time_s",
    "mean_voltage",
    "min_voltage",
    "max_voltage",
    "voltage_drop",
    "mean_current",
    "max_current",
    "c_rate",
    "dod_pct",
    "mean_temp",
    "max_temp",
    "temp_delta",
    "ambient_temp",
    "charge_time_s",
    "Re_ohm",
    "Rct_ohm",
    "R_total_ohm",
    "cycle_number",
]


def exponential_decay(x: np.ndarray, a: float, b: float, c: float) -> np.ndarray:
    return a * np.exp(-b * x) + c


def compute_rul_label(soh_series: pd.Series, eol: float = EOL_SOH) -> pd.Series:
    """
    Compute RUL for each cycle.
    If battery reached EOL: RUL = (eol_cycle - current_cycle), clipped to 0.
    If not reached: extrapolate via exponential decay fit.
    """
    cycles = soh_series.index.to_numpy(dtype=float)
    sohs   = soh_series.to_numpy(dtype=float)

    eol_mask = sohs <= eol
    if eol_mask.any():
        eol_cycle = cycles[eol_mask][0]
        return pd.Series(np.maximum(0.0, eol_cycle - cycles), index=soh_series.index)

    # Extrapolate
    try:
        if len(cycles) < 5:
            raise ValueError("Too few cycles to fit")
        popt, _ = curve_fit(
            exponential_decay, cycles, sohs,
            p0=[100.0, 1e-3, 60.0],
            maxfev=5000,
            bounds=([0, 0, 0], [200, 1.0, 100]),
        )
        # Find where decay hits EOL
        from scipy.optimize import brentq
        try:
            eol_cycle_extrap = brentq(
                lambda x: exponential_decay(np.array([x]), *popt)[0] - eol,
                cycles[0], cycles[-1] + 2000,
            )
        except ValueError:
            eol_cycle_extrap = cycles[-1] + 200  # fallback
        rul = np.maximum(0.0, eol_cycle_extrap - cycles)
        return pd.Series(rul, index=soh_series.index)
    except Exception:
        # Linear extrapolation fallback
        if len(sohs) >= 2:
            slope = (sohs[-1] - sohs[0]) / max(cycles[-1] - cycles[0], 1)
            if slope < 0:
                cycles_to_eol = (sohs[-1] - eol) / abs(slope)
                rul = np.maximum(0.0, cycles_to_eol - (cycles - cycles[-1]))
                return pd.Series(rul, index=soh_series.index)
        return pd.Series(np.full(len(cycles), 200.0), index=soh_series.index)


def extract_cycle_features(csv_path: Path) -> pd.DataFrame | None:
    battery_id = csv_path.stem
    print(f"  Processing {battery_id} ...", end=" ", flush=True)

    try:
        available = pd.read_csv(csv_path, nrows=0).columns.tolist()
        use = [c for c in USECOLS if c in available]
        raw = pd.read_csv(csv_path, usecols=use, low_memory=False)
    except Exception as exc:
        print(f"SKIP — {exc}")
        return None

    raw["type"] = raw["type"].astype(str).str.strip().str.lower()

    # ── Discharge features ──────────────────────────────────────────────────
    dis = raw[raw["type"] == "discharge"].copy()
    if dis.empty:
        print("SKIP — no discharge rows")
        return None

    for col in ["Voltage_measured", "Current_measured", "Temperature_measured", "Time", "Capacity"]:
        if col in dis.columns:
            dis[col] = pd.to_numeric(dis[col], errors="coerce")

    dis["Current_measured"] = dis["Current_measured"].abs()
    dis["cycle_id"] = pd.to_numeric(dis["cycle_id"], errors="coerce").astype("Int64")
    dis = dis.dropna(subset=["Voltage_measured", "Current_measured", "cycle_id"])

    # Capacity is sparse — only first row of each cycle has it. Broadcast to all rows.
    cycle_cap = (
        dis.groupby("cycle_id")["Capacity"]
        .first()
        .reset_index()
        .rename(columns={"Capacity": "_cycle_cap"})
    )
    dis = dis.merge(cycle_cap, on="cycle_id", how="left")
    dis["Capacity"] = dis["_cycle_cap"].ffill()
    dis = dis.drop(columns=["_cycle_cap"])
    dis = dis.dropna(subset=["Capacity"])

    dis_agg = dis.groupby("cycle_id").agg(
        discharge_capacity_ah=("Capacity", "max"),
        discharge_time_s=("Time", lambda x: x.max() - x.min()),
        mean_voltage=("Voltage_measured", "mean"),
        min_voltage=("Voltage_measured", "min"),
        max_voltage=("Voltage_measured", "max"),
        mean_current=("Current_measured", "mean"),
        max_current=("Current_measured", "max"),
        mean_temp=("Temperature_measured", "mean"),
        max_temp=("Temperature_measured", "max"),
        ambient_temp=("ambient_temperature", "first") if "ambient_temperature" in dis.columns else ("Voltage_measured", lambda _: np.nan),
    ).reset_index()

    # ── Charge features ─────────────────────────────────────────────────────
    chg = raw[raw["type"] == "charge"].copy()
    if not chg.empty:
        chg["Time"] = pd.to_numeric(chg["Time"], errors="coerce")
        chg["cycle_id"] = pd.to_numeric(chg["cycle_id"], errors="coerce").astype("Int64")
        chg_agg = chg.groupby("cycle_id").agg(
            charge_time_s=("Time", lambda x: x.max() - x.min()),
        ).reset_index()
        dis_agg = dis_agg.merge(chg_agg, on="cycle_id", how="left")
    else:
        dis_agg["charge_time_s"] = np.nan

    # ── Impedance features ──────────────────────────────────────────────────
    imp = raw[raw["type"] == "impedance"].copy()
    if not imp.empty and "Re" in imp.columns and "Rct" in imp.columns:
        imp["Re"]  = pd.to_numeric(imp["Re"],  errors="coerce")
        imp["Rct"] = pd.to_numeric(imp["Rct"], errors="coerce")
        imp["cycle_id"] = pd.to_numeric(imp["cycle_id"], errors="coerce").astype("Int64")
        imp_agg = imp.groupby("cycle_id").agg(
            Re_ohm=("Re",  "mean"),
            Rct_ohm=("Rct", "mean"),
        ).reset_index()
        dis_agg = dis_agg.merge(imp_agg, on="cycle_id", how="left")
    else:
        dis_agg["Re_ohm"]  = np.nan
        dis_agg["Rct_ohm"] = np.nan

    dis_agg["R_total_ohm"] = dis_agg["Re_ohm"].fillna(0) + dis_agg["Rct_ohm"].fillna(0)
    dis_agg["R_total_ohm"] = dis_agg["R_total_ohm"].replace(0, np.nan)

    # ── SOH and derived features ─────────────────────────────────────────────
    initial_cap = dis_agg["discharge_capacity_ah"].replace(0, np.nan).iloc[:10].median()
    if pd.isna(initial_cap) or initial_cap <= 0:
        initial_cap = dis_agg["discharge_capacity_ah"].replace(0, np.nan).max()
    if pd.isna(initial_cap) or initial_cap <= 0:
        print("SKIP — cannot determine initial capacity")
        return None

    dis_agg["soh"]        = (dis_agg["discharge_capacity_ah"] / initial_cap * 100).clip(0, 100)
    dis_agg["voltage_drop"] = dis_agg["max_voltage"] - dis_agg["min_voltage"]
    dis_agg["temp_delta"]   = dis_agg["max_temp"] - dis_agg["mean_temp"]
    dis_agg["dod_pct"]      = (dis_agg["discharge_capacity_ah"] / initial_cap * 100).clip(0, 100)
    dis_agg["c_rate"]       = dis_agg["mean_current"] / initial_cap

    dis_agg = dis_agg.sort_values("cycle_id").reset_index(drop=True)
    dis_agg["cycle_number"] = np.arange(1, len(dis_agg) + 1)

    # ── RUL label ────────────────────────────────────────────────────────────
    soh_series = dis_agg.set_index("cycle_number")["soh"]
    dis_agg["rul"] = compute_rul_label(soh_series).values

    dis_agg["battery_id"] = battery_id
    print(f"OK — {len(dis_agg)} cycles, SOH {dis_agg['soh'].min():.1f}%–{dis_agg['soh'].max():.1f}%, "
          f"RUL {dis_agg['rul'].min():.0f}–{dis_agg['rul'].max():.0f}")
    return dis_agg


def main() -> None:
    print("\n=== Step 1: Extracting cycle-level features from all 38 batteries ===")
    all_csvs = sorted(CSV_BASE.rglob("*.csv"))
    print(f"Found {len(all_csvs)} CSV files.\n")

    all_frames: list[pd.DataFrame] = []
    for csv_path in all_csvs:
        df = extract_cycle_features(csv_path)
        if df is not None:
            all_frames.append(df)

    if not all_frames:
        raise RuntimeError("No valid cycle features extracted.")

    combined = pd.concat(all_frames, ignore_index=True)
    print(f"\nTotal cycles: {len(combined):,} across {combined['battery_id'].nunique()} batteries")

    # Save full features CSV
    features_csv = FEATURES_DIR / "cycle_features_with_rul_all.csv"
    combined.to_csv(features_csv, index=False)
    print(f"Saved features → {features_csv.name}")

    # ── Prepare XGBoost training ─────────────────────────────────────────────
    print("\n=== Step 2: Preparing XGBoost training data ===")

    # Keep only features that exist and are numeric
    available_features = [f for f in FEATURE_COLS if f in combined.columns]
    print(f"Using {len(available_features)} features: {available_features}")

    df_clean = combined[available_features + ["rul", "battery_id"]].copy()
    df_clean = df_clean.dropna(subset=["rul"])

    # Fill impedance NaN with median (not all batteries have impedance data)
    for col in ["Re_ohm", "Rct_ohm", "R_total_ohm"]:
        if col in df_clean.columns:
            df_clean[col] = df_clean[col].fillna(df_clean[col].median())

    df_clean = df_clean.fillna(df_clean.median(numeric_only=True))

    X = df_clean[available_features].to_numpy(dtype=float)
    y = df_clean["rul"].to_numpy(dtype=float)
    groups = df_clean["battery_id"].to_numpy()

    print(f"X shape: {X.shape}, y range: {y.min():.0f}–{y.max():.0f} cycles")

    # ── GroupKFold cross-validation ──────────────────────────────────────────
    print("\n=== Step 3: Training XGBoost with GroupKFold cross-validation ===")
    n_splits = min(5, combined["battery_id"].nunique())
    gkf = GroupKFold(n_splits=n_splits)
    cv_maes, cv_r2s = [], []

    for fold, (train_idx, val_idx) in enumerate(gkf.split(X, y, groups=groups), 1):
        model = XGBRegressor(
            n_estimators=500,
            learning_rate=0.05,
            max_depth=5,
            reg_alpha=0.1,
            reg_lambda=1.0,
            subsample=0.8,
            colsample_bytree=0.8,
            n_jobs=-1,
            random_state=42,
            verbosity=0,
        )
        model.fit(X[train_idx], y[train_idx])
        preds = model.predict(X[val_idx])
        preds = np.maximum(0.0, preds)

        fold_mae = mean_absolute_error(y[val_idx], preds)
        fold_r2  = r2_score(y[val_idx], preds)
        cv_maes.append(fold_mae)
        cv_r2s.append(fold_r2)
        val_batteries = sorted(set(groups[val_idx]))
        print(f"  Fold {fold}: MAE={fold_mae:.1f} cycles, R²={fold_r2:.3f} | val batteries: {val_batteries[:5]}...")

    print(f"\nCV Mean MAE: {np.mean(cv_maes):.1f} ± {np.std(cv_maes):.1f} cycles")
    print(f"CV Mean R²:  {np.mean(cv_r2s):.3f} ± {np.std(cv_r2s):.3f}")

    # ── Train final model on all data ────────────────────────────────────────
    print("\n=== Step 4: Training final XGBoost model on all data ===")
    final_model = XGBRegressor(
        n_estimators=500,
        learning_rate=0.05,
        max_depth=5,
        reg_alpha=0.1,
        reg_lambda=1.0,
        subsample=0.8,
        colsample_bytree=0.8,
        n_jobs=-1,
        random_state=42,
        verbosity=0,
    )
    final_model.fit(X, y)

    # Feature importances
    importances = dict(zip(available_features, final_model.feature_importances_))
    top_features = sorted(importances.items(), key=lambda x: x[1], reverse=True)[:5]
    print("\nTop 5 most important features:")
    for feat, imp in top_features:
        print(f"  {feat}: {imp:.4f}")

    # ── Save model ───────────────────────────────────────────────────────────
    model_payload = {
        "model": final_model,
        "features": available_features,
        "cv_mae_mean": float(np.mean(cv_maes)),
        "cv_r2_mean":  float(np.mean(cv_r2s)),
        "n_batteries": int(combined["battery_id"].nunique()),
        "eol_soh": EOL_SOH,
    }
    joblib.dump(model_payload, RUL_MODEL_PATH)

    # Also save to the legacy path the app's config.py points to
    legacy_path = ROOT / "All_Datasets" / "Converted_CSV_Datasets" / "engineered_features" / "rul_outputs" / "rul_xgboost_model.pkl"
    legacy_path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(model_payload, legacy_path)

    print(f"\n=== RUL Training Complete ===")
    print(f"  Model saved → {RUL_MODEL_PATH}")
    print(f"  Also saved  → {legacy_path}")
    print(f"  CV MAE:     {np.mean(cv_maes):.1f} cycles")
    print(f"  CV R²:      {np.mean(cv_r2s):.3f}")
    print(f"  Batteries:  {combined['battery_id'].nunique()}")
    print(f"  Features:   {available_features}")


if __name__ == "__main__":
    main()
