from __future__ import annotations

import json

import numpy as np
from tensorflow.keras.models import load_model

from app.core.config import settings


SEQUENCE_LENGTH = 50
FEATURE_CENTER = np.array([4.1, 20.0, 35.0, 90.0], dtype=float)
FEATURE_SCALE = np.array([0.1, 10.0, 10.0, 10.0], dtype=float)
MODEL_METADATA_PATH = settings.project_root / "model_metadata.json"


class ModelService:
    def __init__(self) -> None:
        self.model = None
        self.metrics = {"mae": "N/A", "r2_score": "N/A"}
        self.sequence_length = SEQUENCE_LENGTH
        self.feature_columns = ["voltage", "current", "temperature", "soh"]
        self.feature_min = None
        self.feature_scale = None
        self.target_min = None
        self.target_scale = None
        self.reload()

    def reload(self) -> None:
        self.model = None
        self.metrics = {"mae": "N/A", "r2_score": "N/A"}
        self.sequence_length = SEQUENCE_LENGTH
        self.feature_columns = ["voltage", "current", "temperature", "soh"]
        self.feature_min = None
        self.feature_scale = None
        self.target_min = None
        self.target_scale = None

        try:
            if settings.model_path.exists():
                self.model = load_model(settings.model_path)
        except Exception:
            self.model = None

        try:
            if MODEL_METADATA_PATH.exists():
                with MODEL_METADATA_PATH.open("r", encoding="utf-8") as handle:
                    metadata = json.load(handle)
                self.sequence_length = int(metadata.get("sequence_length", SEQUENCE_LENGTH))
                self.feature_columns = metadata.get("feature_columns", self.feature_columns)
                self.feature_min = np.array(metadata.get("feature_scaler_min", []), dtype=float)
                self.feature_scale = np.array(metadata.get("feature_scaler_scale", []), dtype=float)
                self.target_min = np.array(metadata.get("target_scaler_min", []), dtype=float)
                self.target_scale = np.array(metadata.get("target_scaler_scale", []), dtype=float)
        except Exception:
            self.sequence_length = SEQUENCE_LENGTH
            self.feature_columns = ["voltage", "current", "temperature", "soh"]
            self.feature_min = None
            self.feature_scale = None
            self.target_min = None
            self.target_scale = None

        try:
            if settings.metrics_path.exists():
                with settings.metrics_path.open("r", encoding="utf-8") as handle:
                    self.metrics = json.load(handle)
        except Exception:
            self.metrics = {"mae": "N/A", "r2_score": "N/A"}

    def predict_soh(self, history_buffer: list[list[float]]) -> float | None:
        if self.model is None or len(history_buffer) < self.sequence_length:
            return None

        expected_features = len(self.feature_columns)
        recent_history = np.array(history_buffer[-self.sequence_length :], dtype=float)
        if recent_history.ndim != 2 or recent_history.shape[1] < expected_features:
            return None

        recent_history = recent_history[:, :expected_features]
        if (
            self.feature_min is not None
            and self.feature_scale is not None
            and len(self.feature_min) == expected_features
            and len(self.feature_scale) == expected_features
        ):
            scaled = recent_history * self.feature_scale + self.feature_min
        else:
            scaled = (recent_history - FEATURE_CENTER[:expected_features]) / FEATURE_SCALE[:expected_features]

        reshaped = scaled.reshape(1, self.sequence_length, expected_features)
        predicted = self.model.predict(reshaped, verbose=0)[0][0]
        if (
            self.target_min is not None
            and self.target_scale is not None
            and len(self.target_min) == 1
            and len(self.target_scale) == 1
        ):
            return float((predicted - self.target_min[0]) / self.target_scale[0])
        return float(predicted * 20 + 80)


model_service = ModelService()
