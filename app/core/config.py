from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Settings:
    project_root: Path
    data_dir: Path
    frontend_dir: Path
    history_dir: Path
    upload_dir: Path
    db_path: Path
    legacy_db_path: Path
    model_path: Path
    rul_model_path: Path
    metrics_path: Path
    host: str
    port: int
    cors_origins: list[str]
    n8n_webhook_url: str | None
    n8n_api_key: str | None
    n8n_admin_token: str | None
    openai_api_key: str | None


def get_settings() -> Settings:
    project_root = Path(__file__).resolve().parents[2]
    data_dir = project_root / "data"
    model_path = Path(os.getenv("MODEL_PATH", str(project_root / "soh_model.h5")))
    _rul_default = (
        project_root / "rul_model.pkl"
        if (project_root / "rul_model.pkl").exists()
        else project_root / "All_Datasets" / "Converted_CSV_Datasets" / "engineered_features" / "rul_outputs" / "rul_xgboost_model.pkl"
    )
    rul_model_path = Path(os.getenv("RUL_MODEL_PATH", str(_rul_default)))
    metrics_path = Path(os.getenv("METRICS_PATH", str(project_root / "accuracy_metrics.json")))

    return Settings(
        project_root=project_root,
        data_dir=data_dir,
        frontend_dir=project_root / "frontend",
        history_dir=data_dir / "history",
        upload_dir=data_dir / "uploads",
        db_path=data_dir / "intellibms.db",
        legacy_db_path=project_root / "instance" / "intellibms.db",
        model_path=model_path,
        rul_model_path=rul_model_path,
        metrics_path=metrics_path,
        host=os.getenv("HOST", "0.0.0.0"),
        port=int(os.getenv("PORT", "5002")),
        cors_origins=[
            origin.strip()
            for origin in os.getenv("CORS_ORIGINS", "*").split(",")
            if origin.strip()
        ],
        n8n_webhook_url=os.getenv("N8N_WEBHOOK_URL"),
        n8n_api_key=os.getenv("N8N_API_KEY"),
        n8n_admin_token=os.getenv("N8N_ADMIN_TOKEN", "default-secret-token"),
        openai_api_key=os.getenv("OPENAI_API_KEY"),
    )


settings = get_settings()
