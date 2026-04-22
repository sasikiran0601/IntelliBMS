from __future__ import annotations

from datetime import datetime

from sqlalchemy import Column, DateTime, Float, Integer, String, Text

from app.db.base import Base


class Battery(Base):
    __tablename__ = "battery"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    battery_type = Column(String(50), nullable=False)
    num_cells = Column(Integer, nullable=False)
    base_voltage = Column(Float, nullable=False)
    base_soh = Column(Float, nullable=False)
    base_temp = Column(Float, nullable=False)
    degradation_rate = Column(Float, nullable=False)
    fault_probability = Column(Float, nullable=False)
    capacity_ah = Column(Float, nullable=True)
    max_charge_rate = Column(Float, nullable=True)
    max_discharge_rate = Column(Float, nullable=True)
    operating_temp_min = Column(Float, nullable=True)
    operating_temp_max = Column(Float, nullable=True)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    # Kept for compatibility with the legacy Flask database.
    user_id = Column(Integer, nullable=False, default=1)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "battery_type": self.battery_type,
            "num_cells": self.num_cells,
            "base_voltage": self.base_voltage,
            "base_soh": self.base_soh,
            "base_temp": self.base_temp,
            "degradation_rate": self.degradation_rate,
            "fault_probability": self.fault_probability,
            "capacity_ah": self.capacity_ah,
            "max_charge_rate": self.max_charge_rate,
            "max_discharge_rate": self.max_discharge_rate,
            "operating_temp_min": self.operating_temp_min,
            "operating_temp_max": self.operating_temp_max,
            "description": self.description,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
