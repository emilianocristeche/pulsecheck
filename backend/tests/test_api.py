"""Endpoint validation, scheduling bounds and timestamp serialization."""

from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import database
import scheduler
from database import get_db
from main import app
from models import CheckResult, Endpoint
from routers import endpoints as endpoints_router

PUBLIC_URL = "https://8.8.8.8/"   # IP literal: validated without a DNS lookup


@pytest.fixture
def session_factory():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False},
                           poolclass=StaticPool)
    database.Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine)


@pytest.fixture
def client(session_factory, monkeypatch):
    def override():
        s = session_factory()
        try:
            yield s
        finally:
            s.close()

    scheduled = []
    # No real scheduling or background HTTP checks in these tests.
    monkeypatch.setattr(endpoints_router, "schedule_endpoint",
                        lambda eid, iv: scheduled.append((eid, iv)))
    monkeypatch.setattr(endpoints_router, "check_endpoint", lambda eid: None)
    app.dependency_overrides[get_db] = override
    c = TestClient(app)   # no context manager: lifespan/scheduler not started
    c.scheduled = scheduled
    yield c
    app.dependency_overrides.clear()


def _create(client, **fields):
    return client.post("/api/endpoints/", json={"name": "api", "url": PUBLIC_URL, **fields})


@pytest.mark.parametrize("interval", [-5, 0, 1, 9, 86_401])
def test_interval_out_of_bounds_rejected(client, interval):
    assert _create(client, interval_seconds=interval).status_code == 422
    assert client.scheduled == []


@pytest.mark.parametrize("interval", [10, 60, 86_400])
def test_interval_within_bounds_accepted(client, interval):
    r = _create(client, interval_seconds=interval)
    assert r.status_code == 201
    assert client.scheduled == [(r.json()["id"], interval)]


@pytest.mark.parametrize("status", [0, 99, 600])
def test_expected_status_must_be_an_http_status(client, status):
    assert _create(client, expected_status=status).status_code == 422


def test_legacy_rows_with_bad_interval_still_listed(client, session_factory):
    # Rows saved before validation existed must not break GET (500).
    with session_factory() as s:
        s.add(Endpoint(name="old", url=PUBLIC_URL, interval_seconds=0))
        s.commit()
    r = client.get("/api/endpoints/")
    assert r.status_code == 200
    assert r.json()[0]["interval_seconds"] == 0


@pytest.mark.parametrize("stored, expected", [(0, 10), (-5, 10), (1, 10), (60, 60),
                                              (10**9, 86_400)])
def test_schedule_endpoint_clamps_interval(monkeypatch, stored, expected):
    calls = []
    monkeypatch.setattr(scheduler.scheduler, "add_job", lambda *a, **kw: calls.append(kw))
    scheduler.schedule_endpoint(1, stored)
    assert calls[0]["trigger"].interval.total_seconds() == expected


def test_check_timestamps_serialize_as_utc(client, session_factory):
    with session_factory() as s:
        ep = Endpoint(name="x", url=PUBLIC_URL)
        s.add(ep)
        s.commit()
        s.add(CheckResult(endpoint_id=ep.id, is_up=True,
                          timestamp=datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc)))
        s.commit()
        eid = ep.id
    ts = client.get(f"/api/checks/{eid}").json()[0]["timestamp"]
    # SQLite returns it naive; the API must still say it's UTC.
    assert ts == "2026-01-02T03:04:05Z"
