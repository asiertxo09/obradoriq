"""Agent orchestrator + tools tests (offline deterministic path)."""
from __future__ import annotations

import datetime as dt

import pytest

from app.llm import orchestrator, tools as toolkit
from app.models import SessionLocal, init_db
from app.seed import seed

TARGET = "2026-06-29"


@pytest.fixture(scope="module", autouse=True)
def _seeded():
    init_db()
    seed(force=True)


@pytest.fixture()
def db():
    s = SessionLocal()
    yield s
    s.close()


def test_tool_get_recommendations_is_grounded(db):
    r = toolkit.execute_tool(db, 1, "get_recommendations", {"target_date": TARGET})
    assert len(r["recommendations"]) == 12
    assert all(x["recommended_qty"] > 0 for x in r["recommendations"])


def test_tool_demand_adjustment_increases_quantities(db):
    base = toolkit.execute_tool(db, 1, "get_recommendations", {"target_date": TARGET})
    up = toolkit.execute_tool(db, 1, "get_recommendations",
                              {"target_date": TARGET, "demand_adjustment_pct": 40})
    base_total = sum(x["recommended_qty"] for x in base["recommendations"])
    up_total = sum(x["recommended_qty"] for x in up["recommendations"])
    assert up_total > base_total  # context nudge flows through to the grounded numbers


def test_tool_demand_adjustment_is_clamped_high(db):
    """A wild/hallucinated adjustment (e.g. 500%) never reaches the forecast unclamped."""
    huge = toolkit.execute_tool(db, 1, "get_recommendations",
                                {"target_date": TARGET, "demand_adjustment_pct": 500})
    capped = toolkit.execute_tool(db, 1, "get_recommendations",
                                  {"target_date": TARGET, "demand_adjustment_pct": 100})
    huge_total = sum(x["recommended_qty"] for x in huge["recommendations"])
    capped_total = sum(x["recommended_qty"] for x in capped["recommendations"])
    assert huge["demand_adjustment_pct"] == 100  # echoed value reflects the clamp, not the raw input
    assert huge_total == capped_total


def test_tool_demand_adjustment_is_clamped_low(db):
    extreme = toolkit.execute_tool(db, 1, "get_recommendations",
                                   {"target_date": TARGET, "demand_adjustment_pct": -90})
    floor = toolkit.execute_tool(db, 1, "get_recommendations",
                                 {"target_date": TARGET, "demand_adjustment_pct": -50})
    extreme_total = sum(x["recommended_qty"] for x in extreme["recommendations"])
    floor_total = sum(x["recommended_qty"] for x in floor["recommendations"])
    assert extreme["demand_adjustment_pct"] == -50
    assert extreme_total == floor_total


def test_tool_draft_production_sheet(db):
    r = toolkit.execute_tool(db, 1, "draft_production_sheet", {"target_date": TARGET})
    assert r["estimated_ingredient_spend_eur"] > 0
    assert r["lines"] and "total_qty" in r["lines"][0]


def test_tool_ingest_data_validates(db):
    bad = "site,product,date,quantity_sold\nCentro,Croissant,2026-06-01,30\nCentro,Ghost,2026-06-02,5\n"
    r = toolkit.execute_tool(db, 1, "ingest_data", {"kind": "sales", "csv_text": bad})
    assert r["inserted"] == 1 and r["rejected"] == 1


def test_offline_router_routes_to_reallocation(db):
    out = orchestrator.chat(db, 1, f"Can we move product between sites on {TARGET}?")
    assert out["tool_results"][0]["tool"] == "get_reallocations"
    assert "reallocation" in out["reply"].lower() or "balanced" in out["reply"].lower()


def test_offline_router_default_is_recommendations(db):
    out = orchestrator.chat(db, 1, f"How much should I bake on {TARGET}?")
    assert out["tool_results"][0]["tool"] == "get_recommendations"


def test_offline_router_weekly(db):
    out = orchestrator.chat(db, 1, "show me the weekly margin review for 2026-06-28")
    assert out["tool_results"][0]["tool"] == "get_weekly_summary"


# ---- online path: conversation history must reach the model ----

def _force_online(monkeypatch):
    from app.core.config import get_settings

    monkeypatch.setenv("LLM_PROVIDER", "groq")
    monkeypatch.setenv("LLM_OFFLINE", "false")
    monkeypatch.setenv("LLM_API_KEY", "test-key")
    get_settings.cache_clear()
    return get_settings


def test_online_chat_includes_conversation_history(db, monkeypatch):
    get_settings = _force_online(monkeypatch)
    calls = []

    def fake_raw_complete(system, user, **kwargs):
        calls.append(user)
        if len(calls) == 1:
            return '{"tool": "get_recommendations", "args": {"target_date": "2026-06-29"}}'
        return "Here is tomorrow's plan."

    monkeypatch.setattr(orchestrator.router, "raw_complete", fake_raw_complete)
    history = [
        {"role": "user", "content": "We have a street festival on 2026-06-29."},
        {"role": "assistant", "content": "Noted — I'll factor that into the plan."},
    ]
    try:
        out = orchestrator.chat(db, 1, "OK, so how much should I bake that day?", history)
    finally:
        get_settings.cache_clear()

    assert len(calls) == 2  # planner + composer
    assert all("street festival" in c for c in calls), "prior turns must reach both prompts"
    assert all("how much should i bake that day" in c.lower() for c in calls)
    assert out["reply"]


def test_online_chat_truncates_history_to_recent_turns(db, monkeypatch):
    get_settings = _force_online(monkeypatch)
    calls = []

    def fake_raw_complete(system, user, **kwargs):
        calls.append(user)
        if len(calls) == 1:
            return '{"tool": "get_recommendations", "args": {}}'
        return "ok"

    monkeypatch.setattr(orchestrator.router, "raw_complete", fake_raw_complete)
    history = [{"role": "user", "content": f"turn {i}"} for i in range(10)]
    try:
        orchestrator.chat(db, 1, "latest question", history)
    finally:
        get_settings.cache_clear()

    assert "turn 3" not in calls[0]  # oldest turns dropped
    assert "turn 4" in calls[0]      # only the most recent window kept
    assert "turn 9" in calls[0]
