from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


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
    metrics_path: Path
    host: str
    port: int
    cors_origins: list[str]


def get_settings() -> Settings:
    project_root = Path(__file__).resolve().parents[2]
    data_dir = project_root / "data"
    model_path = Path(os.getenv("MODEL_PATH", str(project_root / "soh_model.h5")))
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
        metrics_path=metrics_path,
        host=os.getenv("HOST", "0.0.0.0"),
        port=int(os.getenv("PORT", "5002")),
        cors_origins=[
            origin.strip()
            for origin in os.getenv("CORS_ORIGINS", "*").split(",")
            if origin.strip()
        ],
    )


settings = get_settings()
