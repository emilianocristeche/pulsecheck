from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
from database import Base


class Endpoint(Base):
    __tablename__ = "endpoints"

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    url = Column(String, nullable=False)
    expected_status = Column(Integer, default=200)
    interval_seconds = Column(Integer, default=60)
    is_active = Column(Boolean, default=True)
    last_status = Column(Boolean, nullable=True)  # None = never checked yet

    checks = relationship("CheckResult", back_populates="endpoint", cascade="all, delete")


class CheckResult(Base):
    __tablename__ = "check_results"

    id = Column(Integer, primary_key=True)
    endpoint_id = Column(Integer, ForeignKey("endpoints.id"), nullable=False)
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    status_code = Column(Integer, nullable=True)
    response_time_ms = Column(Float, nullable=True)
    is_up = Column(Boolean, nullable=False)
    error_msg = Column(String, nullable=True)

    endpoint = relationship("Endpoint", back_populates="checks")
