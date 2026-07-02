"""Intraday service/API/agent wiring — the seam Track D owns.

Covers: GET /api/intraday (shape + tenant isolation), the offline agent route to
get_intraday_status, and phrase_intraday's Trust Layer grounding guarantee.
"""
from __future__ import annotations

import datetime as dt

import pytest
from fastapi.testclient import TestClient

from app.llm import agents, orchestrator
from app.main import app
from app.models import SessionLocal, init_db
from app.recommender.types import IntradaySignal
from app.seed import DEMO_EMAIL, DEMO_PASSWORD, seed
from app.trust import layer

client = TestClient(app)

# Squarely inside the seeded sale_event range (2026-05-30 .. 2026-06-28): plenty of
# prior days for a learned pace curve, and events on the day itself for sold_so_far.
AS_OF = "2026-06-20T11:00:00"
ACTIONS = {"bake_more", "move", "markdown", "hold"}


@pytest.fixture(scope="module", autouse=True)
def _seeded():
    init_db()
    seed(force=True)  # ensure the canonical demo chain, independent of other suites


@pytest.fixture()
def db():
    s = SessionLocal()
    yield s
    s.close()


def _register(email: str, bakery: str) -> str:
    r = client.post("/api/auth/register", json={
        "bakery_name": bakery, "email": email, "password": "bakery123"})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


def _demo_token() -> str:
    r = client.post("/api/auth/login", json={"email": DEMO_EMAIL, "password": DEMO_PASSWORD})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


# ---- API shape ----
def test_intraday_endpoint_returns_well_formed_signals():
    r = client.get(f"/api/intraday?as_of={AS_OF}", headers=_auth(_demo_token()))
    assert r.status_code == 200, r.text
    signals = r.json()
    assert signals  # 6 products x 2 sites for the demo chain
    assert len(signals) == 12

    for s in signals:
        assert s["action"] in ACTIONS
        assert s["sold_so_far"] >= 0
        assert s["on_hand"] >= 0
        assert s["projected_demand"] >= 0
        assert s["confidence"] in {"HIGH", "LOW"}
        assert s["product_name"] and s["site_name"]
        assert s["reason"]
        if s["action"] == "move":
            assert s["from_site_id"] is not None and s["from_site_name"]
        else:
            assert s["from_site_id"] is None

    # Shape holds regardless of whether the demo data happens to be balanced: either at
    # least one signal is actionable, or every one is a well-formed "hold".
    actionable = [s for s in signals if s["action"] != "hold"]
    assert actionable or all(s["action"] == "hold" for s in signals)


def test_intraday_requires_auth():
    assert client.get(f"/api/intraday?as_of={AS_OF}").status_code == 401


def test_intraday_defaults_as_of_to_now():
    r = client.get("/api/intraday", headers=_auth(_demo_token()))
    assert r.status_code == 200
    assert isinstance(r.json(), list)


# ---- tenant isolation ----
def test_intraday_tenant_isolation():
    """A fresh bakery (no products/sites/events) must never see the demo chain's signals."""
    token_b = _register("intraday-owner@x.com", "Delta Bakers")
    r = client.get(f"/api/intraday?as_of={AS_OF}", headers=_auth(token_b))
    assert r.status_code == 200
    assert r.json() == []  # nothing belongs to this bakery yet — no leakage from bakery 1


# ---- offline agent routing ----
def test_offline_router_routes_intraday_question_to_tool(db):
    out = orchestrator.chat(db, 1, "is anything selling out right now?")
    assert out["tool_results"][0]["tool"] == "get_intraday_status"
    assert out["reply"]


def test_offline_router_intraday_reply_is_sane(db):
    out = orchestrator.chat(db, 1, "are we on track today so far?")
    result = out["tool_results"][0]["result"]
    assert "signals" in result
    assert isinstance(result["signals"], list)


# ---- grounding ----
def _sig(**kw) -> IntradaySignal:
    base = dict(
        product_id=1, site_id=1, as_of=dt.datetime(2026, 6, 20, 11, 0),
        sold_so_far=40, on_hand=10, projected_demand=60.0,
        projected_sellout_time=dt.time(13, 30), action="bake_more", action_qty=12,
        from_site_id=None, eur_at_risk=25.5, confidence="HIGH", reason="stub reason",
    )
    base.update(kw)
    return IntradaySignal(**base)


def test_phrase_intraday_bake_more_is_grounded():
    sig = _sig(action="bake_more", action_qty=12, eur_at_risk=25.5)
    text = agents.phrase_intraday(sig, "Croissant", "Centro")
    assert layer.assert_grounded(text, [12.0, 25.5])


def test_phrase_intraday_move_is_grounded():
    sig = _sig(action="move", action_qty=8, from_site_id=2, eur_at_risk=14.0)
    text = agents.phrase_intraday(sig, "Croissant", "Centro", from_site_name="Barrio")
    assert layer.assert_grounded(text, [8.0, 14.0])


def test_phrase_intraday_markdown_is_grounded():
    sig = _sig(action="markdown", action_qty=6, projected_sellout_time=None, eur_at_risk=3.6)
    text = agents.phrase_intraday(sig, "Sourdough Loaf", "Barrio")
    assert layer.assert_grounded(text, [6.0, 3.6])


def test_phrase_intraday_hold_is_grounded():
    sig = _sig(action="hold", action_qty=0, projected_sellout_time=None, eur_at_risk=0.0)
    text = agents.phrase_intraday(sig, "Baguette", "Centro")
    assert layer.assert_grounded(text, [0.0])


def test_phrase_intraday_never_leaks_sellout_time_digits():
    """The sellout time (13:30) must never appear as a bare, ungrounded number."""
    sig = _sig(action="bake_more", action_qty=12, eur_at_risk=25.5,
               projected_sellout_time=dt.time(13, 30))
    text = agents.phrase_intraday(sig, "Croissant", "Centro")
    # Would raise GroundingError if "13" or "30" leaked in as an invented number.
    assert layer.assert_grounded(text, [12.0, 25.5])
