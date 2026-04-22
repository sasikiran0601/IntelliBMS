from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import FileResponse

from app.core.config import settings


router = APIRouter(include_in_schema=False)


@router.get("/")
def index() -> FileResponse:
    return FileResponse(settings.frontend_dir / "index.html")


@router.get("/health")
def health() -> dict:
    return {"status": "ok"}
