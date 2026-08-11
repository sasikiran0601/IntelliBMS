"""
train_soh_all_batteries.py
===========================
Step 1: Reads ALL 38 battery discharge CSV files (B0005–B0056)
Step 2: Builds a combined time-series training dataset
Step 3: Trains a Stacked LSTM for SOH prediction
Step 4: Saves soh_model.h5, model_metadata.json, accuracy_metrics.json

Run from project root:
    python scripts/train_soh_all_batteries.py
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error, r2_score
from sklearn.model_selection import GroupShuffleSplit
from sklearn.preprocessing import MinMaxScaler
from tensorflow.keras.layers import LSTM, Dense
from tensorflow.keras.models import Sequential

# ── Paths ─────────────────────────────────────────────────────────────────────
ROOT = Path(__file__).resolve().parents[1]
CSV_BASE = ROOT / "datasets" / "04_Converted_CSV" / "5. Battery Data Set"
PROCESSED_DIR = ROOT / "datasets" / "06_Processed"
MODEL_PATH = ROOT / "soh_model.h5"
METRICS_PATH = ROOT / "accuracy_metrics.json"
METADATA_PATH = ROOT / "model_metadata.json"

PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

# ── Config ────────────────────────────────────────────────────────────────────
SEQUENCE_LENGTH = 50
FEATURE_COLUMNS = ["voltage", "current", "temperature"]
TARGET_COLUMN = "soh"

# Columns we actually need from each raw CSV (saves RAM on 38 large files)
USECOLS = [
    "cycle_id", "type", "Voltage_measured",
    "Current_measured", "Temperature_measured", "Time", "Capacity"
]


def load_all_batteries() -> pd.DataFrame:
    """
    Walk every sub-folder of CSV_BASE, read all B????.csv files,
    keep only discharge rows, compute SOH, and return a unified frame.
    """
    frames: list[pd.DataFrame] = []

    all_csvs = sorted(CSV_BASE.rglob("*.csv"))
    print(f"Found {len(all_csvs)} CSV files across all batches.")

    for csv_path in all_csvs:
        battery_id = csv_path.stem          # e.g. "B0005"
        print(f"  Loading {battery_id} ({csv_path.stat().st_size / 1e6:.1f} MB) ...", end=" ", flush=True)

        try:
            raw = pd.read_csv(
                csv_path,
                usecols=USECOLS,
                low_memory=False,
            )
        except Exception as exc:
            print(f"SKIP — {exc}")
            continue

        # Keep only discharge rows
        raw["type"] = raw["type"].astype(str).str.strip().str.lower()
        discharge = raw[raw["type"] == "discharge"].copy()

        if discharge.empty:
            print("SKIP — no discharge rows")
            continue

        discharge = discharge.rename(columns={
            "cycle_id":              "cycle_index",
            "Voltage_measured":      "voltage",
            "Current_measured":      "current",
            "Temperature_measured":  "temperature",
            "Time":                  "elapsed_time_s",
            "Capacity":              "capacity_ah",
        })

        # Convert sensor columns to numeric
        for col in ["cycle_index", "voltage", "current", "temperature", "elapsed_time_s"]:
            discharge[col] = pd.to_numeric(discharge[col], errors="coerce")
        discharge["capacity_ah"] = pd.to_numeric(discharge["capacity_ah"], errors="coerce")

        # Capacity is only filled on the first row of each cycle — broadcast it to all rows
        discharge["cycle_index"] = pd.to_numeric(discharge["cycle_index"], errors="coerce")
        discharge = discharge.dropna(subset=["voltage", "current", "temperature", "cycle_index"])
        discharge["cycle_index"] = discharge["cycle_index"].astype(int)
        discharge["current"] = discharge["current"].abs()

        # Per-cycle capacity: take first non-null value in each cycle
        cycle_cap = (
            discharge.groupby("cycle_index")["capacity_ah"]
            .first()
            .reset_index()
            .rename(columns={"capacity_ah": "cycle_capacity"})
        )
        discharge = discharge.merge(cycle_cap, on="cycle_index", how="left")
        discharge["capacity_ah"] = discharge["cycle_capacity"].ffill()
        discharge = discharge.drop(columns=["cycle_capacity"])
        discharge = discharge.dropna(subset=["capacity_ah"])

        battery_initial = discharge["capacity_ah"].max()
        if battery_initial <= 0:
            print("SKIP — zero initial capacity")
            continue

        discharge["soh"] = (discharge["capacity_ah"] / battery_initial * 100).clip(0, 100)

        # Filter out physically impossible SOH readings (< 50% likely corrupt data)
        valid_before = len(discharge)
        discharge = discharge[discharge["soh"] >= 50.0]
        dropped = valid_before - len(discharge)
        if dropped > 0:
            print(f"\n    (filtered {dropped} rows with SOH < 50% as corrupt)", end=" ", flush=True)
        discharge["battery_id"] = battery_id
        discharge["source"] = "nasa_discharge"

        frames.append(discharge[[
            "source", "battery_id", "cycle_index", "elapsed_time_s",
            "voltage", "current", "temperature", "soh", "capacity_ah"
        ]])

        print(f"OK — {len(discharge):,} rows, {discharge['cycle_index'].nunique()} cycles, "
              f"SOH {discharge['soh'].min():.1f}%–{discharge['soh'].max():.1f}%")

    if not frames:
        raise RuntimeError("No valid discharge data found. Check CSV_BASE path.")

    combined = pd.concat(frames, ignore_index=True)
    combined = combined.sort_values(["battery_id", "cycle_index", "elapsed_time_s"]).reset_index(drop=True)
    return combined


def build_sequences(frame: pd.DataFrame) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    sequences: list[np.ndarray] = []
    targets: list[float] = []
    groups: list[str] = []

    for battery_id, bdf in frame.groupby("battery_id", sort=False):
        values = bdf[FEATURE_COLUMNS + [TARGET_COLUMN]].to_numpy(dtype=float)
        if len(values) <= SEQUENCE_LENGTH:
            continue
        for i in range(SEQUENCE_LENGTH, len(values)):
            sequences.append(values[i - SEQUENCE_LENGTH: i, :len(FEATURE_COLUMNS)])
            targets.append(values[i, -1])
            groups.append(str(battery_id))

    if not sequences:
        raise ValueError("Not enough rows to create sequences. Check data.")

    return np.array(sequences), np.array(targets, dtype=float), np.array(groups)


def main() -> None:
    print("\n=== Step 1: Loading all battery discharge data ===")
    frame = load_all_batteries()
    print(f"\nTotal: {len(frame):,} rows | {frame['battery_id'].nunique()} batteries")
    print(f"SOH range: {frame['soh'].min():.1f}% – {frame['soh'].max():.1f}%")

    # Save combined timeseries for reference
    out_csv = PROCESSED_DIR / "model_training_timeseries_all.csv"
    frame.to_csv(out_csv, index=False)
    print(f"Saved combined timeseries → {out_csv.name}")

    # Also overwrite the file the app loads by default
    frame.to_csv(PROCESSED_DIR / "model_training_timeseries.csv", index=False)
    frame.to_pickle(PROCESSED_DIR / "model_training_timeseries.pkl")

    print("\n=== Step 2: Building sequences (50-timestep windows) ===")
    X, y, groups = build_sequences(frame)
    print(f"Total sequences: {len(X):,}")

    # Hold out ~25% of batteries entirely (battery-level split)
    splitter = GroupShuffleSplit(n_splits=1, test_size=0.25, random_state=42)
    train_idx, test_idx = next(splitter.split(X, y, groups=groups))

    X_train_raw, X_test_raw = X[train_idx], X[test_idx]
    y_train_raw, y_test_raw = y[train_idx], y[test_idx]
    train_groups, test_groups = groups[train_idx], groups[test_idx]

    train_batteries = sorted(set(train_groups.tolist()))
    test_batteries  = sorted(set(test_groups.tolist()))
    print(f"Train batteries ({len(train_batteries)}): {train_batteries}")
    print(f"Test  batteries ({len(test_batteries)}):  {test_batteries}")

    # Scale features and targets
    feature_scaler = MinMaxScaler()
    target_scaler  = MinMaxScaler()

    X_train_2d = X_train_raw.reshape(-1, len(FEATURE_COLUMNS))
    X_test_2d  = X_test_raw.reshape(-1, len(FEATURE_COLUMNS))
    X_train = feature_scaler.fit_transform(X_train_2d).reshape(X_train_raw.shape)
    X_test  = feature_scaler.transform(X_test_2d).reshape(X_test_raw.shape)
    y_train = target_scaler.fit_transform(y_train_raw.reshape(-1, 1)).ravel()
    y_test  = target_scaler.transform(y_test_raw.reshape(-1, 1)).ravel()

    print(f"X_train: {X_train.shape}, X_test: {X_test.shape}")

    print("\n=== Step 3: Training Stacked LSTM ===")
    model = Sequential([
        LSTM(64, return_sequences=True, input_shape=(SEQUENCE_LENGTH, len(FEATURE_COLUMNS))),
        LSTM(32),
        Dense(1),
    ])
    model.compile(optimizer="adam", loss="mean_squared_error")
    model.summary()
    model.fit(X_train, y_train, epochs=10, batch_size=64, verbose=1)

    if MODEL_PATH.exists():
        os.remove(MODEL_PATH)
    model.save(MODEL_PATH)
    print(f"\nModel saved → {MODEL_PATH.name}")

    print("\n=== Step 4: Evaluating on held-out batteries ===")
    preds_scaled = model.predict(X_test, verbose=0).ravel()
    y_actual = target_scaler.inverse_transform(y_test.reshape(-1, 1)).ravel()
    y_pred   = target_scaler.inverse_transform(preds_scaled.reshape(-1, 1)).ravel()

    mae = mean_absolute_error(y_actual, y_pred)
    r2  = r2_score(y_actual, y_pred)

    print(f"\n--- Results ---")
    print(f"MAE:  {mae:.4f} pp SOH")
    print(f"R²:   {r2:.4f}")
    print(f"Test batteries: {test_batteries}")

    metrics = {
        "mae": f"{mae:.2f}",
        "r2_score": f"{r2:.3f}",
        "evaluation": "held_out_battery_split",
        "train_batteries": train_batteries,
        "test_batteries": test_batteries,
        "total_batteries": frame['battery_id'].nunique(),
        "total_training_rows": len(frame),
    }
    METRICS_PATH.write_text(json.dumps(metrics, indent=2), encoding="utf-8")

    metadata = {
        "sequence_length": SEQUENCE_LENGTH,
        "feature_columns": FEATURE_COLUMNS,
        "feature_scaler_min":   feature_scaler.min_.tolist(),
        "feature_scaler_scale": feature_scaler.scale_.tolist(),
        "target_scaler_min":    target_scaler.min_.tolist(),
        "target_scaler_scale":  target_scaler.scale_.tolist(),
    }
    METADATA_PATH.write_text(json.dumps(metadata, indent=2), encoding="utf-8")

    print(f"\nSaved: {METRICS_PATH.name}, {METADATA_PATH.name}")
    print("\n=== SOH Training Complete ===")
    print(f"  Model:   {MODEL_PATH}")
    print(f"  MAE:     {mae:.2f} pp")
    print(f"  R²:      {r2:.3f}")
    print(f"  Trained on {len(train_batteries)} batteries, tested on {len(test_batteries)} batteries")


if __name__ == "__main__":
    main()
