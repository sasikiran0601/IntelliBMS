from __future__ import annotations

import json
from pathlib import Path

import pandas as pd


ALLOWED_EXTENSIONS = {"csv", "json", "xlsx", "xls", "txt"}


def allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def _default_battery_data(filename: str) -> dict:
    return {
        "name": f"Auto Battery - {filename}",
        "battery_type": "Li-ion",
        "num_cells": 48,
        "base_voltage": 4.1,
        "base_soh": 95.0,
        "base_temp": 25.0,
        "degradation_rate": 0.03,
        "fault_probability": 0.1,
        "capacity_ah": 100.0,
        "max_charge_rate": 50.0,
        "max_discharge_rate": 100.0,
        "operating_temp_min": -10.0,
        "operating_temp_max": 60.0,
        "description": f"Auto-generated from uploaded file: {filename}",
    }


def _first_value(frame: pd.DataFrame, *keys: str, default):
    for key in keys:
        if key in frame.columns:
            return frame[key].iloc[0]
    return default


def parse_battery_file(file_path: Path, filename: str) -> dict:
    try:
        extension = filename.rsplit(".", 1)[1].lower()

        if extension == "csv":
            frame = pd.read_csv(file_path)
        elif extension in {"xlsx", "xls"}:
            frame = pd.read_excel(file_path)
        elif extension == "json":
            with file_path.open("r", encoding="utf-8") as handle:
                payload = json.load(handle)
            frame = pd.DataFrame([payload] if isinstance(payload, dict) else payload)
        else:
            try:
                frame = pd.read_csv(file_path, delimiter="\t")
            except Exception:
                parsed = {}
                with file_path.open("r", encoding="utf-8") as handle:
                    for line in handle:
                        if ":" not in line:
                            continue
                        key, value = line.strip().split(":", 1)
                        parsed[key.strip()] = value.strip()
                frame = pd.DataFrame([parsed])

        if frame.empty:
            return _default_battery_data(filename)

        return {
            "name": _first_value(frame, "name", "battery_name", default="Auto Battery"),
            "battery_type": _first_value(frame, "type", "battery_type", default="Li-ion"),
            "num_cells": int(_first_value(frame, "cells", "num_cells", default=48)),
            "base_voltage": float(_first_value(frame, "voltage", "base_voltage", default=4.1)),
            "base_soh": float(_first_value(frame, "soh", "base_soh", default=95.0)),
            "base_temp": float(_first_value(frame, "temperature", "base_temp", default=25.0)),
            "degradation_rate": float(_first_value(frame, "degradation", "degradation_rate", default=0.03)),
            "fault_probability": float(_first_value(frame, "fault_prob", "fault_probability", default=0.1)),
            "capacity_ah": float(_first_value(frame, "capacity", "capacity_ah", default=100.0)),
            "max_charge_rate": float(_first_value(frame, "charge_rate", "max_charge_rate", default=50.0)),
            "max_discharge_rate": float(_first_value(frame, "discharge_rate", "max_discharge_rate", default=100.0)),
            "operating_temp_min": float(_first_value(frame, "temp_min", "operating_temp_min", default=-10.0)),
            "operating_temp_max": float(_first_value(frame, "temp_max", "operating_temp_max", default=60.0)),
            "description": _first_value(
                frame,
                "description",
                default="Auto-generated from uploaded file",
            ),
        }
    except Exception:
        return _default_battery_data(filename)
