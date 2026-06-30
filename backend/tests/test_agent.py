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
