from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from database import SessionLocal
from models import Endpoint, CheckResult
from alerts import send_alert
from datetime import datetime, timezone
from netguard import BlockedURL, fetch
from schemas import MAX_INTERVAL_SECONDS, MIN_INTERVAL_SECONDS
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
            # SSRF-safe GET: public IPs only, DNS pinned, each redirect re-validated.
            result = fetch(endpoint.url, timeout=10)
            status_code = result.status_code
            response_time_ms = result.elapsed_ms
            is_up = status_code == endpoint.expected_status
        except BlockedURL as e:
            error_msg = f"blocked: {e}"[:200]
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


def schedule_endpoint(endpoint_id: int, interval_seconds: int):
    """(Re)schedule periodic checks for one endpoint.

    The interval is clamped to the allowed range so rows saved before the API
    validated it (e.g. 0 or negative) can't hammer the target.
    """
    seconds = min(max(interval_seconds or 0, MIN_INTERVAL_SECONDS), MAX_INTERVAL_SECONDS)
    scheduler.add_job(
        check_endpoint,
        trigger=IntervalTrigger(seconds=seconds),
        id=str(endpoint_id),
        args=[endpoint_id],
        replace_existing=True,
    )


def sync_jobs():
    """Reconcile scheduler jobs with active endpoints in DB."""
    db = SessionLocal()
    try:
        endpoints = db.query(Endpoint).filter(Endpoint.is_active == True).all()
        active_ids = {e.id for e in endpoints}
        existing_ids = {int(j.id) for j in scheduler.get_jobs() if j.id.isdigit()}

        for eid in active_ids - existing_ids:
            ep = db.get(Endpoint, eid)
            schedule_endpoint(eid, ep.interval_seconds)

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
