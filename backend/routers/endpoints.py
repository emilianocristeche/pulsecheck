from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db
from models import Endpoint
from schemas import EndpointCreate, EndpointRead
from scheduler import scheduler, check_endpoint
from netguard import BlockedURL, resolve_and_validate
import requests
from apscheduler.triggers.interval import IntervalTrigger
from typing import List
import threading

router = APIRouter()


@router.get("/", response_model=List[EndpointRead])
def list_endpoints(db: Session = Depends(get_db)):
    return db.query(Endpoint).all()


@router.post("/", response_model=EndpointRead, status_code=201)
def create_endpoint(data: EndpointCreate, db: Session = Depends(get_db)):
    # Fail fast on targets that would be refused at check time anyway. A name
    # that does not resolve yet is accepted (it will just show as down); the
    # scheduler re-validates on every check, since DNS can change later.
    try:
        resolve_and_validate(data.url)
    except BlockedURL as e:
        raise HTTPException(422, f"URL not allowed: {e}")
    except requests.ConnectionError:
        pass

    ep = Endpoint(**data.model_dump())
    db.add(ep)
    db.commit()
    db.refresh(ep)

    scheduler.add_job(
        check_endpoint,
        trigger=IntervalTrigger(seconds=ep.interval_seconds),
        id=str(ep.id),
        args=[ep.id],
        replace_existing=True,
    )
    # First check runs immediately in background so the UI shows status fast
    threading.Thread(target=check_endpoint, args=(ep.id,), daemon=True).start()
    return ep


@router.delete("/{endpoint_id}", status_code=204)
def delete_endpoint(endpoint_id: int, db: Session = Depends(get_db)):
    ep = db.query(Endpoint).filter(Endpoint.id == endpoint_id).first()
    if not ep:
        raise HTTPException(404, "Not found")
    try:
        scheduler.remove_job(str(endpoint_id))
    except Exception:
        pass
    db.delete(ep)
    db.commit()


@router.patch("/{endpoint_id}/toggle", response_model=EndpointRead)
def toggle_endpoint(endpoint_id: int, db: Session = Depends(get_db)):
    ep = db.query(Endpoint).filter(Endpoint.id == endpoint_id).first()
    if not ep:
        raise HTTPException(404, "Not found")
    ep.is_active = not ep.is_active
    db.commit()
    db.refresh(ep)

    if ep.is_active:
        scheduler.add_job(
            check_endpoint,
            trigger=IntervalTrigger(seconds=ep.interval_seconds),
            id=str(ep.id),
            args=[ep.id],
            replace_existing=True,
        )
    else:
        try:
            scheduler.remove_job(str(ep.id))
        except Exception:
            pass
    return ep
