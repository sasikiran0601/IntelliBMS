from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class BatteryBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    battery_type: str = Field(default="Li-ion", min_length=1, max_length=50)
    num_cells: int = Field(default=48, ge=1)
    base_voltage: float = 4.1
    base_soh: float = 95.0
    base_temp: float = 25.0
    degradation_rate: float = 0.03
    fault_probability: float = 0.1
    capacity_ah: float | None = 100.0
    max_charge_rate: float | None = 50.0
    max_discharge_rate: float | None = 100.0
    operating_temp_min: float | None = -10.0
    operating_temp_max: float | None = 60.0
    description: str | None = "Custom battery configuration"


class BatteryCreate(BatteryBase):
    pass


class BatteryRead(BatteryBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime | None = None
    updated_at: datetime | None = None


class BatteryCatalogItem(BatteryRead):
    source: str
    status: str
