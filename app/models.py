from datetime import datetime
from typing import Literal
from pydantic import BaseModel, Field, model_validator, ConfigDict


class StrictModel(BaseModel):
    model_config = ConfigDict(extra='forbid', allow_inf_nan=False)


class Reservoir(StrictModel):
    id: str = Field(min_length=1, max_length=80)
    name: str = Field(min_length=1, max_length=120)
    basin: str
    capacity_tmc: float = Field(gt=0)
    storage_tmc: float = Field(ge=0)
    operating_floor_tmc: float = Field(ge=0)
    drinking_reserve_tmc: float = Field(ge=0)
    other_commitments_tmc: float = Field(ge=0)
    environmental_reserve_tmc: float = Field(ge=0)
    hydro_hold_tmc: float = Field(ge=0)
    observed_at: datetime
    source: str = Field(min_length=3)
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    @model_validator(mode='after')
    def check_storage(self):
        if self.storage_tmc > self.capacity_tmc:
            raise ValueError('Storage exceeds capacity')
        if self.observed_at.tzinfo is None:
            raise ValueError('Observation time must include timezone')
        return self


class Village(StrictModel):
    id: str
    name: str
    district: str
    reservoir_id: str
    crop: str
    stage: Literal['new planting', 'vegetative', 'flowering', 'grain filling']
    area_ha: float = Field(gt=0, le=100000)
    population: int = Field(gt=0)
    net_irrigation_mm: float = Field(ge=0, le=500)
    soil_credit_mm: float = Field(ge=0, le=500)
    efficiency: float = Field(gt=0, le=1)
    lift_head_m: float = Field(ge=0, le=1000)
    pump_efficiency: float = Field(gt=0, le=1)
    pump_capacity_mw: float = Field(gt=0)
    power_hours_day: float = Field(ge=0, le=24)
    canal_capacity_cusecs: float = Field(gt=0)
    travel_hours: float = Field(ge=0)
    deadline_days: int = Field(ge=1, le=30)
    tail_end: bool = False


class Dataset(StrictModel):
    label: str
    mode: Literal['synthetic_demo']
    reservoirs: list[Reservoir] = Field(min_length=1, max_length=200)
    villages: list[Village] = Field(min_length=1, max_length=20000)
    @model_validator(mode='after')
    def check_ids(self):
        ids = [r.id for r in self.reservoirs]
        if len(ids) != len(set(ids)) or len({v.id for v in self.villages}) != len(self.villages):
            raise ValueError('Duplicate reservoir or village ID')
        if any(v.reservoir_id not in ids for v in self.villages):
            raise ValueError('Village has an unknown reservoir route')
        return self


class Scenario(StrictModel):
    name: str = Field(default='Seven day crop rescue', min_length=1, max_length=100)
    horizon_days: int = Field(default=7, ge=1, le=14)
    demand_multiplier: float = Field(default=1, ge=0.25, le=3)
    rainfall_credit_mm: float = Field(default=0, ge=0, le=100)
    power_hours_override: float | None = Field(default=None, ge=0, le=24)
    failure_mode: Literal['none', 'stale reservoir', 'weather unavailable', 'power outage'] = 'none'


class Decision(StrictModel):
    role: Literal['water', 'power']
    action: Literal['approve', 'reject']
    reviewer: str = Field(min_length=2, max_length=80)
    reason: str = Field(min_length=3, max_length=500)


class Delivery(StrictModel):
    village_id: str
    delivered_m3: float = Field(ge=0)
    note: str = Field(min_length=3, max_length=500)
