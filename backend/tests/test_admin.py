"""Admin /generate endpoint: token-guarded, populates the DB."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.main import app
from app.models import SaleEvent, SessionLocal, init_db

client = TestClient(app)


@pytest.fixture(scope="module", autouse=True)
def _db():
    init_db()


def test_disabled_when_no_token(monkeypatch):
    monkeypatch.setenv("ADMIN_TOKEN", "")
    get_settings.cache_clear()
    try:
        r = client.post("/api/admin/generate?days=5&weather=false")
        assert r.status_code == 403
    finally:
        get_settings.cache_clear()


def test_rejects_bad_token(monkeypatch):
    monkeypatch.setenv("ADMIN_TOKEN", "secret123")
    get_settings.cache_clear()
    try:
        r = client.post("/api/admin/generate?days=5&weather=false",
                        headers={"X-Admin-Token": "wrong"})
        assert r.status_code == 401
    finally:
        get_settings.cache_clear()


def test_generates_with_valid_token(monkeypatch):
    monkeypatch.setenv("ADMIN_TOKEN", "secret123")
    get_settings.cache_clear()
    try:
        r = client.post("/api/admin/generate?days=8&weather=false",
                        headers={"X-Admin-Token": "secret123"})
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["status"] == "ok"
        assert body["days"] == 8
        assert body["sale_event"] > 0
        assert SessionLocal().query(SaleEvent).count() > 0
    finally:
        get_settings.cache_clear()
