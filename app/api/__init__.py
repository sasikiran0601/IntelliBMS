from fastapi import APIRouter

from app.api.routes import batteries, legacy


api_router = APIRouter()
api_router.include_router(batteries.router)
api_router.include_router(legacy.router)
