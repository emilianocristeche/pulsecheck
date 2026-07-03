from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from database import SessionLocal
from models import Endpoint, CheckResult
from alerts import send_alert
from datetime import datetime, timezone
import requests
import logging

logger = logging.getLogger(__name__)
scheduler = BackgroundScheduler()


def check_endpoint(endpoint_id: int):
    db = SessionLocal()
    try:
        endpoint = db.query(Endpoint).filter(
            Endpoint.id == endpoint_id, Endpoint.is_active == True
        ).first()
        if not endpoint:
            return

        is_up = False
        status_code = None
        response_time_ms = None
        error_msg = None

        try:
            resp = requests.get(endpoint.url, timeout=10)
            status_code = resp.status_code
            response_time_ms = resp.elapsed.total_seconds() * 1000
            is_up = status_code == endpoint.expected_status
        except Exception as e:
            error_msg = str(e)[:200]

        result = CheckResult(
            endpoint_id=endpoint_id,
            timestamp=datetime.now(timezone.utc),
            status_code=status_code,
            response_time_ms=response_time_ms,
            is_up=is_up,
            error_msg=error_msg,
        )
        db.add(result)

        # Alert only on state change (DOWN → UP or UP → DOWN)
        if endpoint.last_status is not None and endpoint.last_status != is_up:
            send_alert(endpoint.name, endpoint.url, is_up)

        endpoint.last_status = is_up
        db.commit()
    except Exception as e:
        logger.error("Error checking endpoint %d: %s", endpoint_id, e)
        db.rollback()
    finally:
        db.close()


def sync_jobs():
    """Reconcile scheduler jobs with active endpoints in DB."""
    db = SessionLocal()
    try:
        endpoints = db.query(Endpoint).filter(Endpoint.is_active == True).all()
        active_ids = {e.id for e in endpoints}
        existing_ids = {int(j.id) for j in scheduler.get_jobs() if j.id.isdigit()}

        for eid in active_ids - existing_ids:
            ep = db.query(Endpoint).get(eid)
            scheduler.add_job(
                check_endpoint,
                trigger=IntervalTrigger(seconds=ep.interval_seconds),
                id=str(eid),
                args=[eid],
                replace_existing=True,
            )

        for eid in existing_ids - active_ids:
            try:
                scheduler.remove_job(str(eid))
            except Exception:
                pass
    finally:
        db.close()


def start_scheduler():
    scheduler.add_job(sync_jobs, trigger=IntervalTrigger(seconds=30), id="sync")
    scheduler.start()
    sync_jobs()


def stop_scheduler():
    scheduler.shutdown(wait=False)
