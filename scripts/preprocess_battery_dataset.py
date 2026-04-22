from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
DATASET_ROOT = ROOT / "Battery_dataset"
PROCESSED_ROOT = DATASET_ROOT / "processed"

DISCHARGE_FILE = DATASET_ROOT / "discharge.csv"
CURVE_FILES = {
    "dataset3": DATASET_ROOT / "Dataset#3.xlsx",
    "dataset5": DATASET_ROOT / "Dataset#5.xlsx",
}
ALT_DATASET_ROOT = DATASET_ROOT / "battery_alt_dataset"


def ensure_dirs() -> None:
    PROCESSED_ROOT.mkdir(parents=True, exist_ok=True)


def normalize_duplicate_headers(columns: list[str]) -> list[str]:
    seen: dict[str, int] = {}
    normalized: list[str] = []
    for column in columns:
        base = (
            str(column)
            .strip()
            .lower()
            .replace("#", "num")
            .replace("%", "pct")
            .replace("(", "")
            .replace(")", "")
            .replace("/", "_")
            .replace("-", "_")
            .replace(" ", "_")
        )
        base = "_".join(part for part in base.split("_") if part)
        count = seen.get(base, 0)
        seen[base] = count + 1
        normalized.append(base if count == 0 else f"{base}_{count + 1}")
    return normalized


def preprocess_discharge_dataset() -> tuple[pd.DataFrame, pd.DataFrame]:
    frame = pd.read_csv(DISCHARGE_FILE)
    frame.columns = normalize_duplicate_headers(frame.columns.tolist())

    frame = frame.rename(
        columns={
            "voltage_measured": "voltage",
            "current_measured": "current",
            "temperature_measured": "temperature",
            "time": "elapsed_time_s",
            "time_2": "calendar_time",
            "id_cycle": "cycle_index",
            "battery": "battery_id",
            "ambient_temperature": "ambient_temperature_c",
            "capacity": "capacity_ah",
        }
    )

    frame["current"] = frame["current"].abs()
    frame["cycle_index"] = frame["cycle_index"].astype(int)

    initial_capacity = frame.groupby("battery_id")["capacity_ah"].transform("max")
    frame["soh"] = (frame["capacity_ah"] / initial_capacity * 100).clip(0, 100)
    frame["source"] = "nasa_discharge"

    sample_training_frame = frame[
        [
            "source",
            "battery_id",
            "cycle_index",
            "elapsed_time_s",
            "voltage",
            "current",
            "temperature",
            "soh",
            "capacity_ah",
        ]
    ].copy()
    sample_training_frame = sample_training_frame.sort_values(
        ["battery_id", "cycle_index", "elapsed_time_s"]
    ).reset_index(drop=True)

    cycle_frame = (
        frame.groupby(["battery_id", "cycle_index"], as_index=False)
        .agg(
            voltage=("voltage", "mean"),
            voltage_min=("voltage", "min"),
            voltage_max=("voltage", "max"),
            current=("current", "mean"),
            current_min=("current", "min"),
            current_max=("current", "max"),
            temperature=("temperature", "mean"),
            temperature_max=("temperature", "max"),
            elapsed_time_s=("elapsed_time_s", "max"),
            capacity_ah=("capacity_ah", "first"),
            ambient_temperature_c=("ambient_temperature_c", "first"),
        )
        .sort_values(["battery_id", "cycle_index"])
    )

    cycle_frame["initial_capacity_ah"] = cycle_frame.groupby("battery_id")["capacity_ah"].transform("max")
    cycle_frame["soh"] = (cycle_frame["capacity_ah"] / cycle_frame["initial_capacity_ah"] * 100).clip(0, 100)
    cycle_frame["source"] = "nasa_discharge"

    cycle_frame.to_csv(PROCESSED_ROOT / "discharge_cycle_soh.csv", index=False)
    sample_training_frame.to_pickle(PROCESSED_ROOT / "model_training_timeseries.pkl")
    return sample_training_frame, cycle_frame


def _extract_curve_sheet(dataset_name: str, workbook_path: Path, sheet_name: str) -> pd.DataFrame:
    raw = pd.read_excel(workbook_path, sheet_name=sheet_name, header=None)
    voltage_grid = pd.to_numeric(
        raw.iloc[1, 1:].astype(str).str.replace(" V", "", regex=False),
        errors="coerce",
    )
    body = raw.iloc[2:, :].copy()
    body.columns = ["sample_name", *[f"v_{value:.2f}" for value in voltage_grid]]
    body = body.dropna(subset=["sample_name"]).reset_index(drop=True)
    extracted_sample_index = pd.to_numeric(
        body["sample_name"].astype(str).str.extract(r"(\d+)")[0],
        errors="coerce",
    )
    body["sample_index"] = extracted_sample_index.fillna(pd.Series(np.arange(1, len(body) + 1))).astype(int)

    feature_cols = [column for column in body.columns if column.startswith("v_")]
    feature_frame = body[feature_cols].apply(pd.to_numeric, errors="coerce").fillna(0.0)

    summary = pd.DataFrame(
        {
            "source": dataset_name,
            "cell_id": sheet_name,
            "sample_index": body["sample_index"],
            "grid_point_count": len(feature_cols),
            "voltage_grid_start": float(voltage_grid.min()),
            "voltage_grid_end": float(voltage_grid.max()),
            "capacity_end_ah": feature_frame.iloc[:, -1],
            "capacity_mid_ah": feature_frame.iloc[:, len(feature_cols) // 2],
            "capacity_area_ah_v": np.trapezoid(feature_frame.to_numpy(), x=voltage_grid.to_numpy(), axis=1),
            "capacity_max_ah": feature_frame.max(axis=1),
        }
    )

    initial_capacity = summary["capacity_end_ah"].replace(0, np.nan).iloc[:25].median()
    if pd.isna(initial_capacity) or initial_capacity <= 0:
        initial_capacity = summary["capacity_end_ah"].replace(0, np.nan).max()
    summary["initial_capacity_ah"] = float(initial_capacity)
    summary["soh"] = (summary["capacity_end_ah"] / initial_capacity * 100).clip(0, 100)
    return summary


def preprocess_curve_datasets() -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    for dataset_name, workbook_path in CURVE_FILES.items():
        try:
            workbook = pd.ExcelFile(workbook_path)
            for sheet_name in workbook.sheet_names:
                frames.append(_extract_curve_sheet(dataset_name, workbook_path, sheet_name))
        except KeyboardInterrupt:
            print(f"Skipped curve dataset {workbook_path.name}: interrupted while parsing.")
            break
        except Exception as exc:
            print(f"Skipped curve dataset {workbook_path.name}: {exc}")

    curve_frame = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    if not curve_frame.empty:
        curve_frame.to_csv(PROCESSED_ROOT / "degradation_curve_features.csv", index=False)
    return curve_frame


def _default_alt_stats() -> dict[str, float | int | str | None]:
    return {
        "row_count": 0,
        "time_min": float("inf"),
        "time_max": float("-inf"),
        "voltage_sum": 0.0,
        "voltage_count": 0,
        "voltage_min": float("inf"),
        "voltage_max": float("-inf"),
        "current_sum": 0.0,
        "current_count": 0,
        "current_min": float("inf"),
        "current_max": float("-inf"),
        "temperature_sum": 0.0,
        "temperature_count": 0,
        "temperature_min": float("inf"),
        "temperature_max": float("-inf"),
        "mission_type": None,
    }


def _update_metric(stats: dict[str, float | int | str | None], prefix: str, values: pd.Series) -> None:
    clean = pd.to_numeric(values, errors="coerce").dropna()
    if clean.empty:
        return
    stats[f"{prefix}_sum"] += float(clean.sum())
    stats[f"{prefix}_count"] += int(clean.count())
    stats[f"{prefix}_min"] = min(stats[f"{prefix}_min"], float(clean.min()))
    stats[f"{prefix}_max"] = max(stats[f"{prefix}_max"], float(clean.max()))


def preprocess_alt_telemetry() -> pd.DataFrame:
    usecols = [
        "start_time",
        "time",
        "mode",
        "voltage_load",
        "current_load",
        "temperature_battery",
        "mission_type",
    ]

    rows: list[dict[str, float | int | str]] = []
    for csv_path in sorted(ALT_DATASET_ROOT.rglob("battery*.csv")):
        grouped_stats: dict[str, dict[str, float | int | str | None]] = defaultdict(_default_alt_stats)

        for chunk in pd.read_csv(csv_path, usecols=usecols, chunksize=200_000, low_memory=False):
            chunk.columns = normalize_duplicate_headers(chunk.columns.tolist())
            chunk = chunk.rename(columns={"time": "elapsed_time_s"})
            chunk["mode"] = pd.to_numeric(chunk["mode"], errors="coerce")
            discharge_chunk = chunk[chunk["mode"] == -1].copy()
            if discharge_chunk.empty:
                continue

            discharge_chunk["current_load"] = pd.to_numeric(discharge_chunk["current_load"], errors="coerce").abs()

            for start_time, group in discharge_chunk.groupby("start_time", sort=False):
                stats = grouped_stats[str(start_time)]
                stats["row_count"] += int(len(group))
                time_values = pd.to_numeric(group["elapsed_time_s"], errors="coerce").dropna()
                if not time_values.empty:
                    stats["time_min"] = min(stats["time_min"], float(time_values.min()))
                    stats["time_max"] = max(stats["time_max"], float(time_values.max()))
                _update_metric(stats, "voltage", group["voltage_load"])
                _update_metric(stats, "current", group["current_load"])
                _update_metric(stats, "temperature", group["temperature_battery"])

                mission = group["mission_type"].dropna()
                if stats["mission_type"] is None and not mission.empty:
                    stats["mission_type"] = str(mission.iloc[0])

        cycle_rows: list[dict[str, float | int | str]] = []
        for start_time, stats in grouped_stats.items():
            if stats["row_count"] == 0 or stats["current_count"] == 0 or stats["voltage_count"] == 0:
                continue
            cycle_rows.append(
                {
                    "source": "alt_telemetry",
                    "battery_id": csv_path.stem,
                    "battery_group": csv_path.parent.name,
                    "start_time": start_time,
                    "mission_type": stats["mission_type"] or "",
                    "duration_s": max(0.0, float(stats["time_max"]) - float(stats["time_min"])),
                    "voltage_mean": stats["voltage_sum"] / stats["voltage_count"],
                    "voltage_min": stats["voltage_min"],
                    "voltage_max": stats["voltage_max"],
                    "current_mean": stats["current_sum"] / stats["current_count"],
                    "current_min": stats["current_min"],
                    "current_max": stats["current_max"],
                    "temperature_mean": stats["temperature_sum"] / stats["temperature_count"]
                    if stats["temperature_count"]
                    else np.nan,
                    "temperature_max": stats["temperature_max"]
                    if stats["temperature_count"]
                    else np.nan,
                    "row_count": stats["row_count"],
                }
            )

        if not cycle_rows:
            continue

        battery_frame = pd.DataFrame(cycle_rows).sort_values("start_time").reset_index(drop=True)
        battery_frame["cycle_index"] = np.arange(1, len(battery_frame) + 1)
        rows.extend(battery_frame.to_dict("records"))

    alt_frame = pd.DataFrame(rows)
    if not alt_frame.empty:
        alt_frame.to_csv(PROCESSED_ROOT / "alt_battery_cycle_summary.csv", index=False)
    return alt_frame


def write_summary(
    training_frame: pd.DataFrame,
    cycle_frame: pd.DataFrame,
    curve_frame: pd.DataFrame,
    alt_frame: pd.DataFrame,
    include_curves: bool,
    include_alt: bool,
) -> None:
    curve_rows = int(len(curve_frame))
    curve_cells = int(curve_frame["cell_id"].nunique()) if "cell_id" in curve_frame.columns else 0
    alt_rows = int(len(alt_frame))
    alt_batteries = int(alt_frame["battery_id"].nunique()) if "battery_id" in alt_frame.columns else 0

    summary = {
        "training_rows": int(len(training_frame)),
        "training_batteries": sorted(training_frame["battery_id"].astype(str).unique().tolist()),
        "training_soh_min": float(training_frame["soh"].min()),
        "training_soh_max": float(training_frame["soh"].max()),
        "cycle_summary_rows": int(len(cycle_frame)),
        "curve_rows": curve_rows,
        "curve_cells": curve_cells,
        "alt_cycle_rows": alt_rows,
        "alt_batteries": alt_batteries,
        "curves_included": include_curves,
        "alt_included": include_alt,
    }
    (PROCESSED_ROOT / "preprocessing_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Preprocess local battery datasets for model training.")
    parser.add_argument(
        "--include-curves",
        action="store_true",
        help="Also preprocess the Excel degradation-curve workbooks.",
    )
    parser.add_argument(
        "--include-alt",
        action="store_true",
        help="Also preprocess the very large accelerated-life telemetry CSVs.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    ensure_dirs()
    training_frame, cycle_frame = preprocess_discharge_dataset()
    curve_frame = preprocess_curve_datasets() if args.include_curves else pd.DataFrame()
    alt_frame = preprocess_alt_telemetry() if args.include_alt else pd.DataFrame()
    write_summary(
        training_frame,
        cycle_frame,
        curve_frame,
        alt_frame,
        args.include_curves,
        args.include_alt,
    )

    print("Created:")
    for path in sorted(PROCESSED_ROOT.iterdir()):
        print("-", path.relative_to(ROOT).as_posix())


if __name__ == "__main__":
    main()
