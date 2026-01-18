import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import MinMaxScaler
from sklearn.metrics import mean_absolute_error, r2_score
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import LSTM, Dense
import os
import json

print("Starting AI model training and validation process...")

# --- 1. Generate Synthetic Battery Data ---
print("Step 1: Generating synthetic battery data...")
total_points = 10000
voltage = np.random.normal(loc=4.1, scale=0.05, size=total_points)
current = np.random.normal(loc=20, scale=5, size=total_points)
temperature = np.random.normal(loc=35, scale=3, size=total_points)
initial_soh = 100
degradation = np.linspace(0, 15, total_points) + np.random.normal(0, 0.5, total_points)
soh = np.clip(initial_soh - degradation, 80, 100)
df = pd.DataFrame({'voltage': voltage, 'current': current, 'temperature': temperature, 'soh': soh})
print(f"Generated {len(df)} data points.")

# --- 2. Preprocess and Split the Data ---
print("\nStep 2: Preprocessing and splitting data into training and testing sets...")
scaler = MinMaxScaler(feature_range=(0, 1))
scaled_data = scaler.fit_transform(df)
sequence_length = 50 
X, y = [], []
for i in range(sequence_length, len(scaled_data)):
    X.append(scaled_data[i-sequence_length:i, :])
    y.append(scaled_data[i, -1])
X, y = np.array(X), np.array(y)
X = X.reshape(X.shape[0], sequence_length, df.shape[1])

# Split into 80% for training, 20% for testing to validate the model's real-world performance
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
print(f"Training data shape: {X_train.shape}")
print(f"Testing data shape: {X_test.shape}")

# --- 3. Build and Train the LSTM Model ---
print("\nStep 3: Building and training the LSTM model ONLY on the training data...")
model = Sequential([
    LSTM(units=50, return_sequences=True, input_shape=(X.shape[1], X.shape[2])),
    LSTM(units=50),
    Dense(units=1)
])
model.compile(optimizer='adam', loss='mean_squared_error')
model.fit(X_train, y_train, epochs=5, batch_size=32, verbose=1)
model_filename = 'soh_model.h5'
if os.path.exists(model_filename):
    os.remove(model_filename)
model.save(model_filename)
print(f"\nModel training complete! Saved as '{model_filename}'.")

# --- 4. Evaluate the Model on the Unseen Test Set ---
print("\nStep 4: Evaluating model performance on the unseen test set...")
predictions_scaled = model.predict(X_test)

# To calculate a meaningful error, we must "un-scale" the predictions and the actual test values
# back to their original SoH percentages (e.g., from 0.85 back to 98.5%)
dummy_array_for_inverse = np.zeros((len(y_test), df.shape[1]))
dummy_array_for_inverse[:, -1] = y_test.flatten()
y_test_actual = scaler.inverse_transform(dummy_array_for_inverse)[:, -1]

dummy_array_for_inverse[:, -1] = predictions_scaled.flatten()
predictions_actual = scaler.inverse_transform(dummy_array_for_inverse)[:, -1]

# --- 5. Calculate and Save Accuracy Metrics ---
print("\nStep 5: Calculating and saving accuracy metrics...")
mae = mean_absolute_error(y_test_actual, predictions_actual)
r2 = r2_score(y_test_actual, predictions_actual)

print("\n--- Model Performance Report ---")
print(f"Mean Absolute Error (MAE): Our model's predictions are, on average, off by only {mae:.4f}% SoH.")
print(f"R-squared (R²) Score: {r2:.4f} (A score closer to 1.0 means higher accuracy).")
print("---------------------------------")

metrics = {
    "mae": f"{mae:.2f}",
    "r2_score": f"{r2:.3f}"
}
metrics_filename = 'accuracy_metrics.json'
with open(metrics_filename, 'w') as f:
    json.dump(metrics, f)
print(f"Accuracy metrics saved to '{metrics_filename}'. You can now run app.py.")
