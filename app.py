from __future__ import annotations

import uvicorn

from app.core.config import settings
from main import app


if __name__ == "__main__":
    uvicorn.run("main:app", host=settings.host, port=settings.port, reload=False)
