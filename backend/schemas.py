from pydantic import BaseModel, ConfigDict, Field, field_validator
from datetime import datetime, timezone
from typing import Optional

# Check interval bounds. Below 10s a monitor turns into a load generator
# against the target (and against our own scheduler); above a day it is not
# really monitoring anymore.
MIN_INTERVAL_SECONDS = 10
MAX_INTERVAL_SECONDS = 86_400


class EndpointCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    url: str = Field(min_length=1, max_length=2048)
    expected_status: int = Field(200, ge=100, le=599)
    interval_seconds: int = Field(60, ge=MIN_INTERVAL_SECONDS, le=MAX_INTERVAL_SECONDS)


class EndpointRead(BaseModel):
    # Not derived from EndpointCreate on purpose: rows created before the
    # bounds existed must still be readable instead of failing validation.
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    url: str
    expected_status: int
    interval_seconds: int
    is_active: bool
    last_status: Optional[bool]


class CheckResultRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    endpoint_id: int
    timestamp: datetime
    status_code: Optional[int]
    response_time_ms: Optional[float]
    is_up: bool
    error_msg: Optional[str]

    @field_validator("timestamp")
    @classmethod
    def _assume_utc(cls, v: datetime) -> datetime:
        # Timestamps are written in UTC, but SQLite hands them back without a
        # zone. Mark them as UTC so they serialize with "Z" and the browser
        # doesn't read them as local time.
        return v.replace(tzinfo=timezone.utc) if v.tzinfo is None else v


class UptimeStats(BaseModel):
    endpoint_id: int
    uptime_percent: float
    total_checks: int
    last_24h_checks: int
    avg_response_time_ms: Optional[float]
