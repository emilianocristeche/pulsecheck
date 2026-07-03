from pydantic import BaseModel
from datetime import datetime
from typing import Optional


class EndpointCreate(BaseModel):
    name: str
    url: str
    expected_status: int = 200
    interval_seconds: int = 60


class EndpointRead(EndpointCreate):
    id: int
    is_active: bool
    last_status: Optional[bool]

    class Config:
        from_attributes = True


class CheckResultRead(BaseModel):
    id: int
    endpoint_id: int
    timestamp: datetime
    status_code: Optional[int]
    response_time_ms: Optional[float]
    is_up: bool
    error_msg: Optional[str]

    class Config:
        from_attributes = True


class UptimeStats(BaseModel):
    endpoint_id: int
    uptime_percent: float
    total_checks: int
    last_24h_checks: int
    avg_response_time_ms: Optional[float]
