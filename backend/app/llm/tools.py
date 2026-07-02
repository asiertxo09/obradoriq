"""Agent tools — the deterministic, grounded capabilities the orchestrator may call.

Each tool wraps the ML/service layer and returns JSON-serializable, grounded data. The
LLM decides *which* tool to call and with what arguments (e.g. turning "festival
Saturday" into demand_adjustment_pct=30), but every number originates here, not from the
model. This is the division of labour: LLM reasons + routes + phrases; tools/ML compute.
"""
from __future__ import annotations

import datetime as dt

from sqlalchemy.orm import Session

from app.data_hub.ingest import import_sales, import_waste
from app.service import (
    draft_production_sheet,
    generate_reallocations,
    generate_recommendations,
    intraday_status,
    weekly_summary,
)


def _tomorrow() -> str:
    return (dt.date.today() + dt.timedelta(days=1)).isoformat()


def tool_specs() -> list[dict]:
    """OpenAI-style function specs (works with NVIDIA/Groq/OpenAI tool-calling)."""
    date_prop = {"type": "string", "description": "ISO date YYYY-MM-DD"}
    adj_prop = {"type": "number", "description":
                "explicit % nudge to forecast demand for context the model can't know "
                "(e.g. 30 for a festival, -20 for a heatwave). Default 0."}
    rain_prop = {"type": "boolean", "description":
                 "set true if the owner says the target day will be rainy (applies the "
                 "learned rain elasticity). Holidays are detected automatically."}
    return [
        _fn("get_recommendations",
            "Per-site production recommendation (how much to bake) for a date, framed in "
            "euros of waste avoided. Auto-applies weather/holiday signals.",
            {"target_date": date_prop, "demand_adjustment_pct": adj_prop, "rainy": rain_prop}),
        _fn("get_reallocations",
            "Cross-site plan-level reallocation suggestions (shift planned production "
            "from an over-producing site to a sell-out site).",
            {"target_date": date_prop}),
        _fn("get_weekly_summary",
            "Weekly waste total and waste-adjusted ('True') margin per product.",
            {"week_end": date_prop}),
        _fn("draft_production_sheet",
            "Draft a chain-wide production sheet + estimated ingredient spend for approval.",
            {"target_date": date_prop, "demand_adjustment_pct": adj_prop, "rainy": rain_prop}),
        _fn("ingest_data",
            "Import sales or waste rows the owner pasted. Pass kind and CSV text with the "
            "required columns (sales: site,product,date,quantity_sold[,sold_out]; "
            "waste: site,product,date,quantity_wasted). Convert any messy input to that CSV.",
            {"kind": {"type": "string", "enum": ["sales", "waste"]},
             "csv_text": {"type": "string"}}, required=["kind", "csv_text"]),
        _fn("get_intraday_status",
            "Live, per (product, site) 'today so far' signal: sold-so-far vs on-hand vs "
            "projected end-of-day demand, with a mid-day bake_more/move/markdown/hold "
            "action when something is off pace (e.g. selling out early, or overstocked).",
            {"as_of": {"type": "string", "description":
                       "ISO datetime (e.g. 2026-06-20T11:00:00) for the moment to check. "
                       "Defaults to now."}}),
    ]


def _fn(name: str, desc: str, props: dict, required: list[str] | None = None) -> dict:
    return {"type": "function", "function": {
        "name": name, "description": desc,
        "parameters": {"type": "object", "properties": props, "required": required or []}}}


def execute_tool(db: Session, bakery_id: int, name: str, args: dict) -> dict:
    """Run a tool by name with model-provided args; returns grounded data."""
    td = _parse_date(args.get("target_date"))
    adj = float(args.get("demand_adjustment_pct") or 0.0)
    rainy = bool(args.get("rainy") or False)
    if name == "get_recommendations":
        recs = generate_recommendations(db, bakery_id, td, persist=False,
                                        demand_adjustment_pct=adj, rainy=rainy)
        return {"target_date": td.isoformat(), "demand_adjustment_pct": adj, "rainy": rainy,
                "recommendations": [r.model_dump() for r in recs]}
    if name == "get_reallocations":
        recs = generate_reallocations(db, bakery_id, td, persist=False)
        return {"target_date": td.isoformat(),
                "reallocations": [r.model_dump() for r in recs]}
    if name == "get_weekly_summary":
        we = _parse_date(args.get("week_end"))
        return weekly_summary(db, bakery_id, we).model_dump()
    if name == "draft_production_sheet":
        return draft_production_sheet(db, bakery_id, td, demand_adjustment_pct=adj, rainy=rainy)
    if name == "ingest_data":
        kind = args.get("kind")
        text = args.get("csv_text", "")
        result = (import_sales if kind == "sales" else import_waste)(db, bakery_id, text)
        return {"kind": kind, **result.model_dump()}
    if name == "get_intraday_status":
        as_of = _parse_datetime(args.get("as_of"))
        signals = intraday_status(db, bakery_id, as_of)
        return {"as_of": (as_of or dt.datetime.now()).isoformat(),
                "signals": [s.model_dump() for s in signals]}
    return {"error": f"unknown tool {name}"}


def _parse_date(value) -> dt.date:
    if not value:
        return dt.date.today() + dt.timedelta(days=1)
    try:
        return dt.date.fromisoformat(str(value))
    except ValueError:
        return dt.date.today() + dt.timedelta(days=1)


def _parse_datetime(value) -> dt.datetime | None:
    if not value:
        return None
    try:
        return dt.datetime.fromisoformat(str(value))
    except ValueError:
        return None
