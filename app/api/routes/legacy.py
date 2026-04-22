from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.models import Battery
from app.db.session import get_db
from app.services.simulation_service import PREDEFINED_BATTERIES, battery_state_manager


router = APIRouter(tags=["legacy"])


@router.get("/live-data")
def legacy_default_live_data() -> dict:
    return battery_state_manager.simulate_preset(1)


@router.get("/live-data/{battery_id}")
def legacy_live_data(battery_id: int, db: Session = Depends(get_db)) -> dict:
    if battery_id in PREDEFINED_BATTERIES:
        return battery_state_manager.simulate_preset(battery_id)

    battery = db.get(Battery, battery_id)
    if battery is None:
        raise HTTPException(status_code=404, detail="Battery not found")
    return battery_state_manager.simulate_custom(battery)
