from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from database import get_db
from models import CheckResult
from schemas import CheckResultRead, UptimeStats
from datetime import datetime, timezone, timedelta
from typing import List

router = APIRouter()


@router.get("/{endpoint_id}", response_model=List[CheckResultRead])
def get_checks(
    endpoint_id: int,
    limit: int = Query(100, le=1000),
    db: Session = Depends(get_db),
):
    return (
        db.query(CheckResult)
        .filter(CheckResult.endpoint_id == endpoint_id)
        .order_by(CheckResult.timestamp.desc())
        .limit(limit)
        .all()
    )


@router.get("/{endpoint_id}/stats", response_model=UptimeStats)
def get_stats(endpoint_id: int, db: Session = Depends(get_db)):
    since_24h = datetime.now(timezone.utc) - timedelta(hours=24)

    total = db.query(func.count(CheckResult.id)).filter(
        CheckResult.endpoint_id == endpoint_id
    ).scalar()

    up_count = db.query(func.count(CheckResult.id)).filter(
        CheckResult.endpoint_id == endpoint_id,
        CheckResult.is_up == True,
    ).scalar()

    last_24h = db.query(func.count(CheckResult.id)).filter(
        CheckResult.endpoint_id == endpoint_id,
        CheckResult.timestamp >= since_24h,
    ).scalar()

    avg_rt = db.query(func.avg(CheckResult.response_time_ms)).filter(
        CheckResult.endpoint_id == endpoint_id,
        CheckResult.is_up == True,
    ).scalar()

    return UptimeStats(
        endpoint_id=endpoint_id,
        uptime_percent=round((up_count / total * 100) if total else 0.0, 2),
        total_checks=total,
        last_24h_checks=last_24h,
        avg_response_time_ms=round(avg_rt, 1) if avg_rt else None,
    )
