from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models import Battery
from app.db.session import get_db
from app.schemas.battery import BatteryCatalogItem, BatteryCreate, BatteryRead
from app.services.simulation_service import PREDEFINED_BATTERIES, battery_state_manager
from app.services.upload_service import allowed_file, parse_battery_file


router = APIRouter(prefix="/batteries", tags=["batteries"])


def _custom_status(battery: Battery) -> str:
    soh = battery.base_soh
    if soh >= 95:
        return "Excellent"
    if soh >= 85:
        return "Good"
    if soh >= 75:
        return "Fair"
    return "Critical"


@router.get("")
def list_batteries(db: Session = Depends(get_db)) -> dict:
    custom_batteries = db.query(Battery).order_by(Battery.created_at.desc()).all()
    custom = [
        BatteryCatalogItem.model_validate(
            {
                **battery.to_dict(),
                "source": "custom",
                "status": _custom_status(battery),
            }
        ).model_dump()
        for battery in custom_batteries
    ]

    return {
        "predefined": battery_state_manager.list_predefined(),
        "custom": custom,
    }


@router.post("", response_model=BatteryRead, status_code=201)
def create_battery(payload: BatteryCreate, db: Session = Depends(get_db)) -> Battery:
    battery = Battery(**payload.model_dump(), user_id=1)
    db.add(battery)
    db.commit()
    db.refresh(battery)
    return battery


@router.delete("/{battery_id}")
def delete_battery(battery_id: int, db: Session = Depends(get_db)) -> dict:
    battery = db.get(Battery, battery_id)
    if battery is None:
        raise HTTPException(status_code=404, detail="Battery not found")

    db.delete(battery)
    db.commit()
    return {"success": True, "message": "Battery deleted successfully"}


@router.get("/preset/{battery_id}/live-data")
def get_preset_live_data(battery_id: int) -> dict:
    if battery_id not in PREDEFINED_BATTERIES:
        raise HTTPException(status_code=404, detail="Preset battery not found")
    return battery_state_manager.simulate_preset(battery_id)


@router.get("/custom/{battery_id}/live-data")
def get_custom_live_data(battery_id: int, db: Session = Depends(get_db)) -> dict:
    battery = db.get(Battery, battery_id)
    if battery is None:
        raise HTTPException(status_code=404, detail="Battery not found")
    return battery_state_manager.simulate_custom(battery)


@router.post("/upload")
async def upload_battery_files(
    files: list[UploadFile] = File(...),
    db: Session = Depends(get_db),
) -> dict:
    created_batteries: list[int] = []

    for upload in files:
        if not upload.filename or not allowed_file(upload.filename):
            continue

        safe_name = Path(upload.filename).name
        target_path = settings.upload_dir / safe_name
        with target_path.open("wb") as handle:
            handle.write(await upload.read())

        battery_payload = parse_battery_file(Path(target_path), safe_name)
        battery = Battery(**battery_payload, user_id=1)
        db.add(battery)
        db.commit()
        db.refresh(battery)
        created_batteries.append(battery.id)
        target_path.unlink(missing_ok=True)

    if not created_batteries:
        raise HTTPException(status_code=400, detail="No valid files were processed")

    return {
        "success": True,
        "message": f"Successfully created {len(created_batteries)} battery(s)",
        "battery_ids": created_batteries,
        "battery_id": created_batteries[0],
    }
