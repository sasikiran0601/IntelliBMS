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


print("Starting AI model training and validation process...")

ROOT = Path(__file__).resolve().parent
TRAINING_DATASET_PICKLE = ROOT / "datasets" / "processed" / "model_training_timeseries.pkl"
TRAINING_DATASET_CSV = ROOT / "datasets" / "processed" / "model_training_timeseries.csv"
MODEL_PATH = ROOT / "soh_model.h5"
METRICS_PATH = ROOT / "accuracy_metrics.json"
METADATA_PATH = ROOT / "model_metadata.json"

SEQUENCE_LENGTH = 50
FEATURE_COLUMNS = ["voltage", "current", "temperature"]
TARGET_COLUMN = "soh"


def load_training_frame() -> pd.DataFrame:
    if TRAINING_DATASET_PICKLE.exists():
        frame = pd.read_pickle(TRAINING_DATASET_PICKLE)
    elif TRAINING_DATASET_CSV.exists():
        frame = pd.read_csv(TRAINING_DATASET_CSV)
    else:
        raise FileNotFoundError(
            "Real training data not found. Run `python scripts/preprocess_battery_dataset.py` first."
        )

    sort_columns = [column for column in ["battery_id", "cycle_index", "elapsed_time_s"] if column in frame.columns]
    frame = frame.sort_values(sort_columns).reset_index(drop=True)
    required_columns = ["battery_id", *FEATURE_COLUMNS, TARGET_COLUMN]
    missing_columns = [column for column in required_columns if column not in frame.columns]
    if missing_columns:
        raise ValueError(f"Training data is missing required columns: {missing_columns}")
    return frame


def build_sequences(frame: pd.DataFrame) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    sequences: list[np.ndarray] = []
    targets: list[float] = []
    groups: list[str] = []

    for battery_id, battery_frame in frame.groupby("battery_id", sort=False):
        values = battery_frame[FEATURE_COLUMNS + [TARGET_COLUMN]].to_numpy(dtype=float)
        if len(values) <= SEQUENCE_LENGTH:
            continue
        for index in range(SEQUENCE_LENGTH, len(values)):
            sequences.append(values[index - SEQUENCE_LENGTH : index, : len(FEATURE_COLUMNS)])
            targets.append(values[index, -1])
            groups.append(str(battery_id))

    if not sequences:
        raise ValueError("Not enough rows to create training sequences.")

    return np.array(sequences), np.array(targets, dtype=float), np.array(groups)


def main() -> None:
    print("Step 1: Loading processed real battery data...")
    frame = load_training_frame()
    print(f"Loaded {len(frame)} sample-level rows across {frame['battery_id'].nunique()} batteries.")

    print("\nStep 2: Building leakage-free sequences...")
    X, y, groups = build_sequences(frame)
    splitter = GroupShuffleSplit(n_splits=1, test_size=0.25, random_state=42)
    train_indices, test_indices = next(splitter.split(X, y, groups=groups))

    X_train_raw, X_test_raw = X[train_indices], X[test_indices]
    y_train_raw, y_test_raw = y[train_indices], y[test_indices]
    train_groups, test_groups = groups[train_indices], groups[test_indices]

    held_out_batteries = sorted(set(test_groups.tolist()))
    train_batteries = sorted(set(train_groups.tolist()))

    feature_scaler = MinMaxScaler()
    target_scaler = MinMaxScaler()

    X_train_2d = X_train_raw.reshape(-1, len(FEATURE_COLUMNS))
    X_test_2d = X_test_raw.reshape(-1, len(FEATURE_COLUMNS))
    X_train = feature_scaler.fit_transform(X_train_2d).reshape(X_train_raw.shape)
    X_test = feature_scaler.transform(X_test_2d).reshape(X_test_raw.shape)
    y_train = target_scaler.fit_transform(y_train_raw.reshape(-1, 1)).ravel()
    y_test = target_scaler.transform(y_test_raw.reshape(-1, 1)).ravel()

    print(f"Training batteries: {train_batteries}")
    print(f"Held-out test batteries: {held_out_batteries}")
    print(f"Training data shape: {X_train.shape}")
    print(f"Testing data shape: {X_test.shape}")

    print("\nStep 3: Building and training the LSTM model on held-out-battery split...")
    model = Sequential(
        [
            LSTM(units=64, return_sequences=True, input_shape=(SEQUENCE_LENGTH, len(FEATURE_COLUMNS))),
            LSTM(units=32),
            Dense(units=1),
        ]
    )
    model.compile(optimizer="adam", loss="mean_squared_error")
    model.fit(X_train, y_train, epochs=5, batch_size=32, verbose=1)

    if MODEL_PATH.exists():
        os.remove(MODEL_PATH)
    model.save(MODEL_PATH)
    print(f"\nModel training complete! Saved as '{MODEL_PATH.name}'.")

    print("\nStep 4: Evaluating model performance on held-out batteries...")
    predictions_scaled = model.predict(X_test, verbose=0).ravel()
    y_test_actual = target_scaler.inverse_transform(y_test.reshape(-1, 1)).ravel()
    predictions_actual = target_scaler.inverse_transform(predictions_scaled.reshape(-1, 1)).ravel()

    print("\nStep 5: Calculating and saving accuracy metrics...")
    mae = mean_absolute_error(y_test_actual, predictions_actual)
    r2 = r2_score(y_test_actual, predictions_actual)

    print("\n--- Model Performance Report ---")
    print(f"Mean Absolute Error (MAE): {mae:.4f}% SoH on held-out batteries.")
    print(f"R-squared (R²) Score: {r2:.4f} on held-out batteries.")
    print("---------------------------------")

    metrics = {
        "mae": f"{mae:.2f}",
        "r2_score": f"{r2:.3f}",
        "evaluation": "held_out_battery_split",
        "train_batteries": train_batteries,
        "test_batteries": held_out_batteries,
    }
    METRICS_PATH.write_text(json.dumps(metrics, indent=2), encoding="utf-8")

    metadata = {
        "sequence_length": SEQUENCE_LENGTH,
        "feature_columns": FEATURE_COLUMNS,
        "feature_scaler_min": feature_scaler.min_.tolist(),
        "feature_scaler_scale": feature_scaler.scale_.tolist(),
        "target_scaler_min": target_scaler.min_.tolist(),
        "target_scaler_scale": target_scaler.scale_.tolist(),
    }
    METADATA_PATH.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    print(f"Accuracy metrics saved to '{METRICS_PATH.name}'. You can now run app.py.")


if __name__ == "__main__":
    main()
