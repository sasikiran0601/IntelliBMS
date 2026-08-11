from __future__ import annotations

import random
import time
from datetime import datetime, timedelta
from pathlib import Path
from threading import Lock
from typing import Any

import numpy as np
import pandas as pd
from sklearn.linear_model import LinearRegression

from app.core.config import settings
from app.db.models import Battery
from app.services.model_service import model_service


PREDEFINED_BATTERIES: dict[int, dict[str, Any]] = {
    1: {
        "name": "Tesla Model S Pack",
        "battery_type": "Li-ion",
        "num_cells": 48,
        "base_voltage": 4.1,
        "base_soh": 98.5,
        "base_temp": 25.5,
        "degradation_rate": 0.02,
        "fault_probability": 0.1,
        "capacity_ah": 100.0,
        "max_charge_rate": 50.0,
        "max_discharge_rate": 100.0,
        "operating_temp_min": -10.0,
        "operating_temp_max": 60.0,
        "description": "High-performance reference pack",
    },
    2: {
        "name": "BMW i3 Pack",
        "battery_type": "Li-ion",
        "num_cells": 40,
        "base_voltage": 3.9,
        "base_soh": 85.2,
        "base_temp": 28.0,
        "degradation_rate": 0.05,
        "fault_probability": 0.3,
        "capacity_ah": 94.0,
        "max_charge_rate": 48.0,
        "max_discharge_rate": 96.0,
        "operating_temp_min": -10.0,
        "operating_temp_max": 60.0,
        "description": "Moderate degradation test pack",
    },
    3: {
        "name": "Nissan Leaf Pack",
        "battery_type": "Li-ion",
        "num_cells": 44,
        "base_voltage": 4.0,
        "base_soh": 92.8,
        "base_temp": 26.2,
        "degradation_rate": 0.03,
        "fault_probability": 0.15,
        "capacity_ah": 98.0,
        "max_charge_rate": 49.0,
        "max_discharge_rate": 98.0,
        "operating_temp_min": -10.0,
        "operating_temp_max": 60.0,
        "description": "Balanced reference pack",
    },
    4: {
        "name": "Chevy Bolt Pack",
        "battery_type": "Li-ion",
        "num_cells": 36,
        "base_voltage": 3.8,
        "base_soh": 76.3,
        "base_temp": 30.1,
        "degradation_rate": 0.08,
        "fault_probability": 0.5,
        "capacity_ah": 90.0,
        "max_charge_rate": 46.0,
        "max_discharge_rate": 92.0,
        "operating_temp_min": -10.0,
        "operating_temp_max": 60.0,
        "description": "A higher-risk pack for alert simulation",
    },
    5: {
        "name": "Audi e-tron Pack",
        "battery_type": "Li-ion",
        "num_cells": 52,
        "base_voltage": 3.95,
        "base_soh": 89.7,
        "base_temp": 27.3,
        "degradation_rate": 0.04,
        "fault_probability": 0.2,
        "capacity_ah": 102.0,
        "max_charge_rate": 52.0,
        "max_discharge_rate": 104.0,
        "operating_temp_min": -10.0,
        "operating_temp_max": 60.0,
        "description": "Premium EV battery profile",
    },
}


def _status_label(soh: float) -> str:
    if soh >= 95:
        return "Excellent"
    if soh >= 85:
        return "Good"
    if soh >= 75:
        return "Fair"
    return "Critical"


class BatteryStateManager:
    def __init__(self) -> None:
        self._states: dict[str, dict[str, Any]] = {}
        self._lock = Lock()
        
        cycle_features_path = settings.project_root / "All_Datasets" / "Converted_CSV_Datasets" / "engineered_features" / "cycle_level_features.csv"
        if cycle_features_path.exists():
            self._cycle_features_df = pd.read_csv(cycle_features_path)
        else:
            self._cycle_features_df = None

    def list_predefined(self) -> list[dict[str, Any]]:
        items = []
        for battery_id, config in PREDEFINED_BATTERIES.items():
            items.append(
                {
                    "id": battery_id,
                    "source": "preset",
                    "status": _status_label(config["base_soh"]),
                    **config,
                }
            )
        return items

    def simulate_preset(self, battery_id: int) -> dict[str, Any]:
        config = PREDEFINED_BATTERIES[battery_id]
        return self._simulate(f"preset_{battery_id}", battery_id, config)

    def simulate_custom(self, battery: Battery) -> dict[str, Any]:
        config = self._config_from_battery(battery)
        return self._simulate(f"custom_{battery.id}", battery.id, config)

    def _simulate(self, state_key: str, public_id: int, config: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            state = self._get_or_create_state(state_key, config)

            for cell in state["battery_cells"]:
                if not cell["is_faulty"]:
                    voltage_variation = random.uniform(-0.002, 0.002)
                    cell["voltage"] = round(
                        max(3.0, min(4.2, cell["voltage"] + voltage_variation)),
                        3,
                    )
                cell["temperature"] = round(config["base_temp"] + random.uniform(-2, 2), 1)

            if (
                not state["fault_introduced"]
                and time.time() - state["last_fault_check_time"] > 30
                and random.random() < config["fault_probability"] / 100
            ):
                state["faulty_cell_index"] = random.randint(0, config["num_cells"] - 1)
                state["battery_cells"][state["faulty_cell_index"]].update(
                    {"is_faulty": True, "voltage": config["base_voltage"] - 0.5}
                )
                state["fault_introduced"] = True
                state["last_fault_check_time"] = time.time()

            avg_voltage = sum(cell["voltage"] for cell in state["battery_cells"]) / config["num_cells"]
            avg_temp = sum(cell["temperature"] for cell in state["battery_cells"]) / config["num_cells"]

            # FIX: Use NASA training distribution current (~2A constant discharge)
            # model_metadata scaler shows training current range was [1.975, 2.029]A
            # Values outside this range produce LSTM inputs outside [0,1] → garbage predictions
            sim_current = random.uniform(1.95, 2.05)
            # FIX: Clamp voltage to training max (4.03V) to avoid out-of-distribution LSTM input
            lstm_voltage = min(4.03, avg_voltage)
            state["history_buffer"].append(
                [lstm_voltage, sim_current, avg_temp, state["pack_soh"]]
            )
            previous_soh = state["pack_soh"]
            predicted_soh = model_service.predict_soh(state["history_buffer"])
            if predicted_soh is not None:
                # Rate-limit LSTM influence: max 0.5% SoH change per step to prevent sudden crashes
                blended = (previous_soh * 0.72) + (predicted_soh * 0.28)
                max_step = 0.5
                state["pack_soh"] = float(max(previous_soh - max_step, min(previous_soh + max_step, blended)))

            thermal_stress = max(0.0, avg_temp - config["base_temp"]) * 0.0025
            voltage_stress = abs(avg_voltage - config["base_voltage"]) * 0.08
            micro_variation = random.uniform(-0.03, 0.008)

            state["pack_soh"] += micro_variation
            state["pack_soh"] -= thermal_stress + voltage_stress
            state["pack_soh"] -= config["degradation_rate"] / 365 / 24 / 60
            state["pack_soh"] = float(max(0.0, min(100.0, state["pack_soh"])))
            self._record_history_point(state)

            # --- RUL Prediction & Dataset Integration ---
            history_frame = state.get("history_df", pd.DataFrame())
            # FIX: Use sim_cycle (starts at 0) instead of len(history_frame) (starts at 180)
            # history_frame is pre-loaded with 180 historical rows → cycle_idx was always 180+
            # causing row_idx to always pin to the last (most degraded) NASA row.
            state["sim_cycle"] = state.get("sim_cycle", 0) + 1
            cycle_idx = state["sim_cycle"]
            
            # Extract realistic features if available
            real_features = {}
            if self._cycle_features_df is not None and not self._cycle_features_df.empty:
                # Map presets to dataset batteries for realistic simulation
                battery_map = {1: "B0005", 2: "B0006", 3: "B0007", 4: "B0018", 5: "B0025"}
                dataset_b_id = battery_map.get(public_id, "B0005")
                battery_data = self._cycle_features_df[self._cycle_features_df["battery_id"] == dataset_b_id]
                
                if not battery_data.empty:
                    row_idx = min(cycle_idx, len(battery_data) - 1)
                    cycle_row = battery_data.iloc[row_idx]
                    real_features = {
                        "max_temp_discharge_C": float(cycle_row.get("max_temp_discharge_C", avg_temp)),
                        "mean_temp_discharge_C": float(cycle_row.get("mean_temp_discharge_C", avg_temp)),
                        "max_temp_charge_C": float(cycle_row.get("max_temp_charge_C", avg_temp)),
                        "ambient_temperature_C": float(cycle_row.get("ambient_temperature_C", config["base_temp"])),
                        "mean_current_discharge_A": float(cycle_row.get("mean_current_discharge_A", config.get("max_discharge_rate", 50) * 0.6)),
                        "c_rate": float(cycle_row.get("c_rate", 0.5)),
                        "mean_current_charge_A": float(cycle_row.get("mean_current_charge_A", config.get("max_charge_rate", 50) * 0.4)),
                        "dod_pct": float(cycle_row.get("dod_pct", 80.0)),
                        "discharge_time_s": float(cycle_row.get("discharge_time_s", 3600)),
                        "charge_time_s": float(cycle_row.get("charge_time_s", 7200)),
                        "min_voltage_V": float(cycle_row.get("min_voltage_V", 3.0 * config["num_cells"])),
                        "ir_drop_proxy_V": float(cycle_row.get("ir_drop_proxy_V", 0.15)),
                        "Re_ohm": float(cycle_row.get("Re_ohm", 0.015)),
                        "Rct_ohm": float(cycle_row.get("Rct_ohm", 0.045)),
                        "R_total_ohm": float(cycle_row.get("R_total_ohm", 0.060)),
                        "Rct_slope_10cyc": 0.0001,
                    }
            
            soh_slope_5cyc = 0.0
            soh_slope_10cyc = 0.0
            if len(history_frame) >= 5:
                soh_slope_5cyc = (history_frame["soh"].iloc[-1] - history_frame["soh"].iloc[-5]) / 5.0
            if len(history_frame) >= 10:
                soh_slope_10cyc = (history_frame["soh"].iloc[-1] - history_frame["soh"].iloc[-10]) / 10.0
                
            rul_features_dict = {
                "soh": state["pack_soh"],
                "discharge_capacity_ah": 2.0 * (state["pack_soh"] / 100.0),
                "discharge_time_s": real_features.get("discharge_time_s", 3600.0),
                "mean_voltage": 3.5,
                "min_voltage": real_features.get("min_voltage_V", 2.7),
                "max_voltage": 4.2,
                "voltage_drop": 1.5,
                "mean_current": real_features.get("mean_current_discharge_A", 1.0),
                "max_current": 2.0,
                "c_rate": real_features.get("c_rate", 0.5),
                "dod_pct": real_features.get("dod_pct", 80.0),
                "mean_temp": real_features.get("mean_temp_discharge_C", avg_temp),
                "max_temp": real_features.get("max_temp_discharge_C", avg_temp + random.uniform(2, 5)),
                "temp_delta": 5.0,
                "ambient_temp": real_features.get("ambient_temperature_C", config.get("base_temp", 25.0)),
                "charge_time_s": real_features.get("charge_time_s", 3600.0),
                "Re_ohm": real_features.get("Re_ohm", 0.015),
                "Rct_ohm": real_features.get("Rct_ohm", 0.045),
                "R_total_ohm": real_features.get("R_total_ohm", 0.060),
                "cycle_number": cycle_idx,
            }
            predicted_rul = model_service.predict_rul(rul_features_dict)
            
            # Compute RUL Bands
            best_rul = None
            likely_rul = None
            worst_rul = None
            if predicted_rul is not None:
                likely_rul = int(round(predicted_rul))
                best_rul = int(round(predicted_rul * 1.15))
                worst_rul = int(round(predicted_rul * 0.85))
                
            # Identify Degradation Drivers
            drivers = []
            if rul_features_dict.get("max_temp", 25) > 35:
                drivers.append("High Temperature Exposure")
            if rul_features_dict.get("dod_pct", 80) > 85:
                drivers.append("Deep Discharge Cycles")
            # FIX: Use only c_rate (dimensionless, comparable across all battery sizes).
            # mean_current_discharge_A > 40 was unreliable: fallback = max_discharge * 0.6 = 60A
            # for Tesla 100Ah pack, which triggered "High C-Rate" even at normal 0.6C operation.
            if rul_features_dict.get("c_rate", 0.5) > 1.0:
                drivers.append("High C-Rate / Current Bursts")
            if rul_features_dict.get("Re_ohm", 0.015) > 0.05:
                drivers.append("Increased Internal Resistance")
            if not drivers:
                drivers.append("Normal Aging")
                
            # Generate Safety-Aware Summary
            # FIX: SoH<80 is the primary trigger for "Replace Soon"
            # RUL alone on a healthy battery (SoH>90%) must NOT trigger "Replace Soon" —
            # that would show healthy Tesla at 98% SoH as needing replacement, which is wrong.
            active_drivers = [d for d in drivers if d != "Normal Aging"]
            if state["pack_soh"] < 80:
                safety_summary = "Replace Soon: Battery health has reached critical degradation levels."
            elif (
                state["pack_soh"] < 90
                or (likely_rul is not None and likely_rul < 50)
                or len(active_drivers) >= 2
            ):
                safety_summary = "Monitor Closely: Significant degradation factors identified."
            else:
                safety_summary = "Normal Operation: Battery parameters are within safe operating range."

            safety_summary += "\n\nDisclaimer: This is a predictive estimate based on historical patterns and should not be used as the sole operational guideline. Always consult manufacturer guidelines."

            # Enhance long term forecast with RUL
            forecast_data = self._forecast(state)
            if "rul_history" not in state:
                state["rul_history"] = []
            if likely_rul is not None:
                state["rul_history"].append({"timestamp": int(time.time()), "rul": likely_rul, "best": best_rul, "worst": worst_rul})
            # Keep only last 60 points for rul history matching SOH window roughly
            state["rul_history"] = state["rul_history"][-60:]
            forecast_data["rul_history"] = state["rul_history"]

            return {
                "pack_summary": {
                    "total_voltage": float(round(sum(c["voltage"] for c in state["battery_cells"]), 2)),
                    "avg_temperature": float(round(avg_temp, 2)),
                    "state_of_health": float(round(state["pack_soh"], 2)),
                    "remaining_useful_life_cycles": likely_rul if likely_rul is not None else "N/A",
                    "rul_bands": {"best": best_rul, "likely": likely_rul, "worst": worst_rul},
                    "degradation_drivers": drivers,
                    "safety_summary": safety_summary,
                    "alert": (
                        f"Critical Fault: Cell #{state['faulty_cell_index']} is malfunctioning!"
                        if state["fault_introduced"]
                        else "None"
                    ),
                    "battery_name": config["name"],
                    "battery_id": public_id,
                },
                "cells": state["battery_cells"],
                "long_term_forecast": forecast_data,
                "model_performance": model_service.metrics,
            }

    def _get_or_create_state(self, state_key: str, config: dict[str, Any]) -> dict[str, Any]:
        config_signature = self._config_signature(config)
        if state_key in self._states:
            existing_state = self._states[state_key]
            if existing_state.get("config_signature") == config_signature:
                return existing_state
            del self._states[state_key]

        history_path = self._history_path(state_key)
        if not history_path.exists():
            self._generate_history_file(history_path, config)

        history_frame = pd.read_csv(history_path)
        if not self._history_matches_config(history_frame, config):
            self._generate_history_file(history_path, config)
            history_frame = pd.read_csv(history_path)
        linear_model = LinearRegression().fit(history_frame[["timestamp"]], history_frame["soh"])

        state = {
            "config": config,
            "config_signature": config_signature,
            "history_df": history_frame,
            "lr_model": linear_model,
            "history_buffer": [],
            "battery_cells": [
                {
                    "id": index,
                    "voltage": config["base_voltage"],
                    "is_faulty": False,
                    "is_balancing": False,
                    "temperature": config["base_temp"],
                }
                for index in range(config["num_cells"])
            ],
            "pack_soh": float(history_frame.iloc[-1]["soh"]) if not history_frame.empty else config["base_soh"],
            "fault_introduced": False,
            "faulty_cell_index": -1,
            "last_fault_check_time": time.time(),
            "sim_cycle": 0,  # FIX: track real simulation cycles (not history_df length)
        }
        self._states[state_key] = state
        return state

    def _forecast(self, state: dict[str, Any]) -> dict[str, Any]:
        history_frame = state["history_df"].sort_values("timestamp").reset_index(drop=True)
        anchor_timestamp = int(history_frame.iloc[-1]["timestamp"]) if not history_frame.empty else int(datetime.now().timestamp())
        future_timestamps = [
            int((datetime.fromtimestamp(anchor_timestamp) + timedelta(days=offset * 30)).timestamp())
            for offset in range(1, 25)
        ]

        recent_frame = history_frame.tail(min(60, len(history_frame))).copy()
        if len(recent_frame) >= 8:
            start_timestamp = int(recent_frame.iloc[0]["timestamp"])
            elapsed_days = (recent_frame["timestamp"] - start_timestamp) / 86400.0
            degree = 2 if elapsed_days.nunique() >= 3 else 1
            coefficients = np.polyfit(elapsed_days.to_numpy(), recent_frame["soh"].to_numpy(), deg=degree)
            polynomial = np.poly1d(coefficients)
            future_elapsed_days = np.array([(timestamp - start_timestamp) / 86400.0 for timestamp in future_timestamps], dtype=float)
            future_soh = polynomial(future_elapsed_days)
            anchor_soh = float(recent_frame.iloc[-1]["soh"])
            future_soh = anchor_soh + (future_soh - future_soh[0])
            future_soh = np.minimum.accumulate(future_soh)
            future_soh = np.clip(future_soh, 0.0, 100.0)
        else:
            future_frame = pd.DataFrame({"timestamp": future_timestamps})
            future_soh = state["lr_model"].predict(future_frame)

        anchor_soh = float(history_frame.iloc[-1]["soh"]) if not history_frame.empty else float(state["pack_soh"])
        config = state["config"]
        max_monthly_drop = max(0.4, min(2.5, float(config["degradation_rate"]) * 12.0))
        smoothed_projection: list[float] = []
        previous_value = anchor_soh
        for raw_value in future_soh:
            numeric_value = float(np.clip(raw_value, 0.0, 100.0))
            bounded_value = min(previous_value, max(previous_value - max_monthly_drop, numeric_value))
            smoothed_projection.append(bounded_value)
            previous_value = bounded_value
        future_soh = np.array(smoothed_projection, dtype=float)

        projection = [
            {"x": timestamp, "y": float(value)}
            for timestamp, value in zip(future_timestamps, future_soh)
        ]

        forecast_text = "Stable"
        for timestamp, value in zip(future_timestamps, future_soh):
            if value <= 80:
                forecast_text = datetime.fromtimestamp(timestamp).strftime("%b %Y")
                break

        history = state["history_df"].to_dict("records")
        return {"text": forecast_text, "history": history, "projection": projection}

    def _record_history_point(self, state: dict[str, Any]) -> None:
        now_dt = datetime.now()
        now_timestamp = int(now_dt.timestamp())
        history_frame = state["history_df"]

        if not history_frame.empty:
            last_timestamp = int(history_frame.iloc[-1]["timestamp"])
            last_dt = datetime.fromtimestamp(last_timestamp)
            if last_dt.date() == now_dt.date():
                history_frame.loc[history_frame.index[-1], "soh"] = state["pack_soh"]
                history_frame.loc[history_frame.index[-1], "timestamp"] = now_timestamp
            else:
                history_frame = pd.concat(
                    [
                        history_frame,
                        pd.DataFrame([{"timestamp": now_timestamp, "soh": state["pack_soh"]}]),
                    ],
                    ignore_index=True,
                )
        else:
            history_frame = pd.DataFrame([{"timestamp": now_timestamp, "soh": state["pack_soh"]}])

        history_frame = history_frame.sort_values("timestamp").tail(180).reset_index(drop=True)
        state["history_df"] = history_frame
        state["lr_model"] = LinearRegression().fit(history_frame[["timestamp"]], history_frame["soh"])

    def _generate_history_file(self, history_path: Path, config: dict[str, Any]) -> None:
        timestamps = [
            int((datetime.now() - timedelta(days=offset)).timestamp())
            for offset in range(180)
        ]
        base_degradation = config["degradation_rate"] * 180 / 365 * 100
        soh_history = (
            config["base_soh"]
            + np.linspace(base_degradation, 0, 180)
            + np.random.normal(0, 0.5, 180)
        )
        soh_history = np.clip(soh_history, 0, 100)
        pd.DataFrame(
            {"timestamp": sorted(timestamps), "soh": soh_history}
        ).to_csv(history_path, index=False)

    @staticmethod
    def _config_signature(config: dict[str, Any]) -> tuple[Any, ...]:
        return (
            config.get("name"),
            config.get("battery_type"),
            int(config.get("num_cells", 0)),
            round(float(config.get("base_voltage", 0.0)), 3),
            round(float(config.get("base_soh", 0.0)), 3),
            round(float(config.get("base_temp", 0.0)), 3),
            round(float(config.get("degradation_rate", 0.0)), 5),
            round(float(config.get("fault_probability", 0.0)), 5),
        )

    @staticmethod
    def _history_matches_config(history_frame: pd.DataFrame, config: dict[str, Any]) -> bool:
        if history_frame.empty or "soh" not in history_frame.columns or "timestamp" not in history_frame.columns:
            return False

        clean_history = history_frame.copy()
        clean_history["soh"] = pd.to_numeric(clean_history["soh"], errors="coerce")
        clean_history["timestamp"] = pd.to_numeric(clean_history["timestamp"], errors="coerce")
        clean_history = clean_history.dropna(subset=["soh", "timestamp"]).sort_values("timestamp")

        if clean_history.empty:
            return False

        if (clean_history["soh"] < 0).any() or (clean_history["soh"] > 100).any():
            return False

        base_soh = float(config["base_soh"])
        recent_window = clean_history.tail(min(30, len(clean_history)))
        recent_mean = float(recent_window["soh"].mean())
        recent_last = float(recent_window.iloc[-1]["soh"])

        if abs(recent_last - base_soh) > 12:
            return False

        if abs(recent_mean - base_soh) > 15:
            return False

        return True

    def _history_path(self, state_key: str) -> Path:
        filename = f"soh_history_{state_key}.csv"
        return settings.history_dir / filename

    @staticmethod
    def _config_from_battery(battery: Battery) -> dict[str, Any]:
        payload = battery.to_dict()
        payload.setdefault("capacity_ah", 100.0)
        payload.setdefault("max_charge_rate", 50.0)
        payload.setdefault("max_discharge_rate", 100.0)
        payload.setdefault("operating_temp_min", -10.0)
        payload.setdefault("operating_temp_max", 60.0)
        payload.setdefault("typical_dod_pct", 80.0)
        payload.setdefault("typical_c_rate", 0.5)
        return payload


battery_state_manager = BatteryStateManager()
