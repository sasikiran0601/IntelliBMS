# IntelliBMS

IntelliBMS is a battery State of Health (SOH) monitoring platform built around a FastAPI backend, a lightweight frontend dashboard, and a real-data ML pipeline for SOH prediction. The project combines battery catalog management, live telemetry simulation, historical SOH tracking, long-term forecasting, and LSTM-based model training using publicly available battery degradation datasets.

The current version is organized as a minimal full-stack application:

- FastAPI for APIs and app serving
- SQLite + SQLAlchemy for persistence
- a single frontend app for dashboard views
- a preprocessing pipeline for real battery datasets
- an LSTM model trained on processed battery telemetry

## What The Project Does

IntelliBMS is designed as a compact battery analytics workspace with two goals:

1. Provide an interactive monitoring dashboard for preset and custom batteries.
2. Showcase a realistic ML workflow for battery SOH prediction using real degradation data instead of synthetic samples.

From the UI, you can:

- browse preset battery profiles
- create custom battery configurations
- delete custom batteries
- import battery files and convert them into saved battery entries
- inspect live pack metrics such as voltage, temperature, and SOH
- visualize SOH history and a 24-month forecast
- inspect cell-level voltage and temperature in a heatmap-style grid

From the ML side, the project can:

- preprocess raw battery datasets into model-ready training files
- train an LSTM model using real telemetry-derived sequences
- evaluate the model using a held-out battery split
- serve model-backed SOH behavior inside the monitoring app

## Datasets Used

This project now uses real battery datasets stored under [Battery_dataset](C:\Users\sasik\OneDrive\Documents\IntelliBMS\Battery_dataset).

### Primary dataset used for model training

The current training pipeline uses:

- [Battery_dataset/discharge.csv](C:\Users\sasik\OneDrive\Documents\IntelliBMS\Battery_dataset\discharge.csv)

This file is the main labeled training source. It provides discharge-cycle telemetry including:

- measured voltage
- measured current
- measured temperature
- capacity
- battery id
- cycle id

From this dataset, the preprocessing script computes:

- sample-level training rows
- per-cycle SOH summaries
- SOH as `capacity / initial_capacity * 100`

Current processed summary from [Battery_dataset/processed/preprocessing_summary.json](C:\Users\sasik\OneDrive\Documents\IntelliBMS\Battery_dataset\processed\preprocessing_summary.json):

- `169,766` training rows
- `4` batteries: `B0005`, `B0006`, `B0007`, `B0018`
- SOH range from about `56.69%` to `100%`

### Additional datasets included in the repository

These datasets are included and supported by preprocessing utilities, but they are optional in the current default training flow.

1. Battery degradation curve workbooks

- [Battery_dataset/Dataset#3.xlsx](C:\Users\sasik\OneDrive\Documents\IntelliBMS\Battery_dataset\Dataset%233.xlsx)
- [Battery_dataset/Dataset#5.xlsx](C:\Users\sasik\OneDrive\Documents\IntelliBMS\Battery_dataset\Dataset%235.xlsx)

These are useful for extracting degradation-curve features such as:

- voltage-grid capacity signatures
- end-capacity behavior
- degradation trend features

They are processed only when explicitly requested:

```bash
python scripts/preprocess_battery_dataset.py --include-curves
```

2. Alternative battery telemetry dataset

- [Battery_dataset/battery_alt_dataset](C:\Users\sasik\OneDrive\Documents\IntelliBMS\Battery_dataset\battery_alt_dataset)

This dataset contains large accelerated-life telemetry files across:

- regular batteries
- recommissioned batteries
- second-life batteries

It is useful for:

- telemetry analytics
- cycle summarization
- future feature engineering

It is intentionally optional because preprocessing is slow:

```bash
python scripts/preprocess_battery_dataset.py --include-alt
```

## Current ML Pipeline

### Preprocessing

The main preprocessing entry point is [scripts/preprocess_battery_dataset.py](C:\Users\sasik\OneDrive\Documents\IntelliBMS\scripts\preprocess_battery_dataset.py).

By default, it preprocesses the fast labeled discharge dataset needed for training.

It creates:

- [Battery_dataset/processed/model_training_timeseries.pkl](C:\Users\sasik\OneDrive\Documents\IntelliBMS\Battery_dataset\processed\model_training_timeseries.pkl)
- [Battery_dataset/processed/discharge_cycle_soh.csv](C:\Users\sasik\OneDrive\Documents\IntelliBMS\Battery_dataset\processed\discharge_cycle_soh.csv)
- [Battery_dataset/processed/preprocessing_summary.json](C:\Users\sasik\OneDrive\Documents\IntelliBMS\Battery_dataset\processed\preprocessing_summary.json)

Optional outputs:

- [Battery_dataset/processed/degradation_curve_features.csv](C:\Users\sasik\OneDrive\Documents\IntelliBMS\Battery_dataset\processed\degradation_curve_features.csv)
- [Battery_dataset/processed/alt_battery_cycle_summary.csv](C:\Users\sasik\OneDrive\Documents\IntelliBMS\Battery_dataset\processed\alt_battery_cycle_summary.csv)

### Training

The training entry point is [generate_and_train.py](C:\Users\sasik\OneDrive\Documents\IntelliBMS\generate_and_train.py).

The training workflow:

- loads processed real sample-level data
- builds time-series sequences of length `50`
- uses `voltage`, `current`, and `temperature` as input features
- predicts SOH
- performs a held-out battery split using `GroupShuffleSplit`
- trains an LSTM model with TensorFlow/Keras

Saved model artifacts:

- [soh_model.h5](C:\Users\sasik\OneDrive\Documents\IntelliBMS\soh_model.h5)
- [accuracy_metrics.json](C:\Users\sasik\OneDrive\Documents\IntelliBMS\accuracy_metrics.json)
- [model_metadata.json](C:\Users\sasik\OneDrive\Documents\IntelliBMS\model_metadata.json)

Current evaluation from [accuracy_metrics.json](C:\Users\sasik\OneDrive\Documents\IntelliBMS\accuracy_metrics.json):

- MAE: `5.52`
- R2: `0.678`
- evaluation strategy: `held_out_battery_split`
- train batteries: `B0005`, `B0007`, `B0018`
- held-out test battery: `B0006`

This is a stricter and more realistic evaluation than a random sequence split.

## Application Architecture

### Backend

The backend is centered on [main.py](C:\Users\sasik\OneDrive\Documents\IntelliBMS\main.py), which starts a FastAPI app and mounts both the API and the frontend.

Main backend responsibilities:

- battery CRUD operations
- file upload handling
- live battery simulation
- SOH history generation
- long-term forecast generation
- model metric exposure to the frontend

Important backend modules:

- [app/api/routes/batteries.py](C:\Users\sasik\OneDrive\Documents\IntelliBMS\app\api\routes\batteries.py)
- [app/services/simulation_service.py](C:\Users\sasik\OneDrive\Documents\IntelliBMS\app\services\simulation_service.py)
- [app/services/model_service.py](C:\Users\sasik\OneDrive\Documents\IntelliBMS\app\services\model_service.py)
- [app/services/upload_service.py](C:\Users\sasik\OneDrive\Documents\IntelliBMS\app\services\upload_service.py)
- [app/db/models.py](C:\Users\sasik\OneDrive\Documents\IntelliBMS\app\db\models.py)
- [app/db/session.py](C:\Users\sasik\OneDrive\Documents\IntelliBMS\app\db\session.py)

### Frontend

The frontend is a single app served from:

- [frontend/index.html](C:\Users\sasik\OneDrive\Documents\IntelliBMS\frontend\index.html)
- [frontend/src/App.jsx](C:\Users\sasik\OneDrive\Documents\IntelliBMS\frontend\src\App.jsx)
- [frontend/src/api.js](C:\Users\sasik\OneDrive\Documents\IntelliBMS\frontend\src\api.js)
- [frontend/src/styles.css](C:\Users\sasik\OneDrive\Documents\IntelliBMS\frontend\src\styles.css)

Current UI functionality:

- preset battery selection
- custom battery selection
- add battery form
- file import flow
- live dashboard cards
- adaptive SOH history chart
- adaptive 24-month forecast chart
- heatmap-style cell detail view

### Database and runtime data

The application uses SQLite for persistent battery storage:

- [data/intellibms.db](C:\Users\sasik\OneDrive\Documents\IntelliBMS\data\intellibms.db)

Runtime-generated history files are stored under:

- [data/history](C:\Users\sasik\OneDrive\Documents\IntelliBMS\data\history)

Temporary upload handling uses:

- [data/uploads](C:\Users\sasik\OneDrive\Documents\IntelliBMS\data\uploads)

## Latest Project Structure

```text
IntelliBMS/
|-- app/
|   |-- api/
|   |   `-- routes/
|   |       |-- batteries.py
|   |       |-- legacy.py
|   |       `-- ui.py
|   |-- core/
|   |   `-- config.py
|   |-- db/
|   |   |-- base.py
|   |   |-- models.py
|   |   `-- session.py
|   |-- schemas/
|   |   `-- battery.py
|   `-- services/
|       |-- model_service.py
|       |-- simulation_service.py
|       `-- upload_service.py
|-- Battery_dataset/
|   |-- discharge.csv
|   |-- Dataset#3.xlsx
|   |-- Dataset#5.xlsx
|   |-- battery_alt_dataset/
|   `-- processed/
|       |-- model_training_timeseries.pkl
|       |-- model_training_timeseries.csv
|       |-- discharge_cycle_soh.csv
|       |-- degradation_curve_features.csv
|       |-- alt_battery_cycle_summary.csv
|       `-- preprocessing_summary.json
|-- data/
|   |-- history/
|   |-- uploads/
|   `-- intellibms.db
|-- frontend/
|   |-- index.html
|   `-- src/
|       |-- App.jsx
|       |-- api.js
|       |-- main.jsx
|       `-- styles.css
|-- scripts/
|   `-- preprocess_battery_dataset.py
|-- app.py
|-- main.py
|-- generate_and_train.py
|-- soh_model.h5
|-- accuracy_metrics.json
|-- model_metadata.json
|-- Dockerfile
|-- requirements.txt
`-- README.md
```

## API Overview

Main battery routes:

- `GET /api/batteries`
- `POST /api/batteries`
- `DELETE /api/batteries/{battery_id}`
- `POST /api/batteries/upload`
- `GET /api/batteries/preset/{battery_id}/live-data`
- `GET /api/batteries/custom/{battery_id}/live-data`

The backend also mounts the frontend under:

- `/app`

## How Live Simulation Works

The monitoring dashboard is not just static chart rendering. The simulation service:

- maintains battery state per preset/custom battery
- generates per-cell voltage and temperature changes
- injects occasional faults based on fault probability
- tracks SOH over time
- generates long-term forecast projections from recent SOH history
- smooths critical-battery forecasts so charts remain readable

Recent improvements in the simulation/charting flow:

- stale history files are detected and regenerated when they do not match the current battery config
- critical batteries use adaptive chart ranges instead of forcing healthy thresholds into the visible plot area
- forecast curves are smoothed to avoid unrealistic one-step collapse to zero

## Setup

Install dependencies:

```bash
pip install -r requirements.txt
```

If you are using the bundled virtual environment on Windows:

```powershell
.\venv\Scripts\python.exe -m pip install -r requirements.txt
```

## Run The Application

Start the app:

```bash
python app.py
```

On Windows with the local virtual environment:

```powershell
.\venv\Scripts\python.exe app.py
```

Then open:

```text
http://localhost:5002
```

Important:

- use `localhost:5002` in the browser, not `0.0.0.0:5002`
- restart the backend after ML or simulation changes so cached state is refreshed

## Preprocess The Datasets

Default fast preprocessing:

```bash
python scripts/preprocess_battery_dataset.py
```

Include the Excel degradation-curve workbooks:

```bash
python scripts/preprocess_battery_dataset.py --include-curves
```

Include the large alternative telemetry dataset:

```bash
python scripts/preprocess_battery_dataset.py --include-alt
```

Include both optional dataset families:

```bash
python scripts/preprocess_battery_dataset.py --include-curves --include-alt
```

## Train The ML Model

After preprocessing:

```bash
python generate_and_train.py
```

This will:

- train the LSTM model
- save `soh_model.h5`
- save `accuracy_metrics.json`
- save `model_metadata.json`

## Docker

Build the image:

```bash
docker build -t your-dockerhub-user/intellibms:latest .
```

Run locally:

```bash
docker run --rm -p 5002:5002 your-dockerhub-user/intellibms:latest
```

Run with persistent runtime data:

```bash
docker run --rm -p 5002:5002 -v intellibms-data:/app/data your-dockerhub-user/intellibms:latest
```

Push to Docker Hub:

```bash
docker login
docker push your-dockerhub-user/intellibms:latest
```

## Tech Stack

### Backend

- Python
- FastAPI
- SQLAlchemy
- SQLite
- Uvicorn
- Pydantic

### Frontend

- React
- JavaScript / JSX
- Recharts
- HTML
- CSS

### ML / Data

- TensorFlow
- Keras
- scikit-learn
- pandas
- NumPy
- LSTM

### Packaging / Deployment

- Docker

## Current Limitations

- the default training flow uses the labeled discharge dataset as the main supervised training source
- the optional Excel and alternative telemetry datasets are preprocessed for extension work, but they are not yet fully fused into the current LSTM training pipeline
- simulation-backed dashboard behavior is designed for product demonstration and ML integration, not as a replacement for industrial BMS hardware telemetry

## Summary

IntelliBMS is now a real-data-driven battery monitoring and SOH prediction project rather than a synthetic demo. It combines:

- a modular FastAPI backend
- a persistent battery catalog
- live simulation and forecasting
- adaptive charting for both normal and critical battery states
- a real battery dataset preprocessing pipeline
- a held-out-battery LSTM evaluation workflow

This makes it suitable both as:

- a portfolio-ready ML + backend project
- a base for future battery analytics and deployment work
