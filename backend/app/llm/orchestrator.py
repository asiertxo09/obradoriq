"""Orchestrator — the conversational agent that routes to grounded tools.

Online (NVIDIA/Groq/OpenAI-compatible): a real tool-calling loop — the model picks tools,
we execute them (grounded), feed results back, and it composes the answer.
Offline (default in tests/CI, or no key): a deterministic rule-based router that maps the
message to one tool and returns a templated reply. Same tools, same grounded data.
"""
from __future__ import annotations

import datetime as dt
import json
import re

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.llm import router
from app.llm import tools as toolkit

MAX_HISTORY_TURNS = 6


def chat(db: Session, bakery_id: int, message: str, history: list[dict] | None = None) -> dict:
    s = get_settings()
    history = history or []
    if s.llm_offline or not s.api_key() or s.llm_provider == "anthropic":
        return _offline_chat(db, bakery_id, message)
    try:
        return _online_chat(db, bakery_id, message, history)
    except Exception as e:  # never break the chat on a provider error
        out = _offline_chat(db, bakery_id, message)
        out["note"] = f"(fell back to offline routing: {type(e).__name__})"
        return out


def _format_history(history: list[dict]) -> str:
    """Render the last few turns as a transcript so follow-ups ("what about that day?")
    resolve against what was actually said, not just the latest message in isolation."""
    recent = history[-MAX_HISTORY_TURNS:]
    if not recent:
        return ""
    lines = [f"{h.get('role', 'user')}: {h.get('content', '')}" for h in recent]
    return "Conversation so far:\n" + "\n".join(lines) + "\n\n"


def _tool_catalog() -> str:
    lines = []
    for spec in toolkit.tool_specs():
        fn = spec["function"]
        params = ", ".join(fn["parameters"]["properties"].keys()) or "(none)"
        lines.append(f"- {fn['name']}({params}): {fn['description']}")
    return "\n".join(lines)


# Provider-agnostic, two-step JSON tool-planning (works on any model via plain
# completions — no gated native function-calling API needed).
def _online_chat(db: Session, bakery_id: int, message: str, history: list[dict]) -> dict:
    today = dt.date.today().isoformat()
    history_block = _format_history(history)
    plan_system = (
        "You are the planner for ObradorIQ, a bakery-chain ops advisor. Pick the ONE best "
        "tool to answer the owner, and its arguments. Respond with ONLY a JSON object: "
        '{\"tool\": \"<name>\", \"args\": {...}}. No prose.\n'
        f"Today is {today}. Dates must be YYYY-MM-DD; if the owner says 'tomorrow' use the "
        "day after today. If they mention something the data can't know (a festival, weather, "
        "a launch, a supplier issue, a competitor), set demand_adjustment_pct (e.g. 30 for a "
        f"busy festival, -20 for a heatwave).\nTools:\n{_tool_catalog()}"
    )
    plan_raw = router.raw_complete(
        plan_system, f"{history_block}Owner: {message}",
        max_tokens=router.PLAN_MAX_TOKENS, temperature=0.0, json_mode=True)
    plan = _extract_json(plan_raw)
    tool = plan.get("tool")
    if tool not in {s["function"]["name"] for s in toolkit.tool_specs()}:
        raise ValueError(f"planner returned no valid tool: {plan_raw[:120]}")
    args = plan.get("args") or {}

    result = toolkit.execute_tool(db, bakery_id, tool, args)

    compose_system = (
        "You are ObradorIQ, a calm bakery operations advisor. Answer the owner in 1-3 short, "
        "practical sentences using ONLY the numbers in DATA — never invent or change a number. "
        "If an adjustment was applied for context they mentioned, say so. Use the conversation "
        "so far for context, but don't repeat earlier answers verbatim."
    )
    reply = router.raw_complete(
        compose_system,
        f"{history_block}Owner asked: {message}\nDATA (from tool {tool}): "
        f"{json.dumps(result, default=str)[:6000]}",
        max_tokens=router.COMPOSE_MAX_TOKENS)
    return {"reply": reply.strip(), "tool_results": [
        {"tool": tool, "args": args, "result": result}]}


def _extract_json(text: str) -> dict:
    """Pull the first JSON object out of a model reply (tolerates code fences/prose)."""
    text = text.strip()
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if not m:
        return {}
    try:
        return json.loads(m.group(0))
    except json.JSONDecodeError:
        return {}


# ---- offline deterministic router ----
def _offline_chat(db: Session, bakery_id: int, message: str) -> dict:
    m = message.lower()
    date = _find_date(message)
    args = {"target_date": date} if date else {}

    if any(k in m for k in ("now", "right now", "selling out", "sell out", "bake more",
                            "on track", "today so far", "so far today")):
        tool, args = "get_intraday_status", {}
    elif any(k in m for k in ("realloc", "move", "shift", "rebalance", "between site")):
        tool = "get_reallocations"
    elif any(k in m for k in ("week", "margin", "profit")):
        tool, args = "get_weekly_summary", {"week_end": date or _last_complete_day()}
    elif any(k in m for k in ("order", "supplier", "shopping", "production sheet", "buy")):
        tool = "draft_production_sheet"
    else:
        tool = "get_recommendations"

    result = toolkit.execute_tool(db, bakery_id, tool, args)
    return {"reply": _summarize(tool, result), "tool_results": [
        {"tool": tool, "args": args, "result": result}]}


def _summarize(tool: str, r: dict) -> str:
    if tool == "get_recommendations":
        recs = r.get("recommendations", [])
        risk = sum(x["predicted_waste_eur"] for x in recs)
        return (f"Here is the production plan for {r.get('target_date')}: {len(recs)} "
                f"site-product recommendations, with about €{risk:.2f} of leftover risk if "
                f"you over-bake. See the breakdown below.")
    if tool == "get_reallocations":
        rs = r.get("reallocations", [])
        if not rs:
            return "Sites look balanced — no reallocation needed for that date."
        top = rs[0]
        return (f"{len(rs)} reallocation(s). Top: shift {top['quantity']}× "
                f"{top['product_name']} from site {top['from_site_id']} to "
                f"{top['to_site_id']}, recovering €{top['eur_waste_avoided']}.")
    if tool == "get_weekly_summary":
        return (f"Week {r['week_start']}→{r['week_end']}: €{r['total_waste_eur']} wasted, "
                f"~€{r['eur_avoided_estimate']} recoverable. True-margin breakdown below.")
    if tool == "draft_production_sheet":
        return (f"Draft production sheet for {r['target_date']}: estimated ingredient spend "
                f"€{r['estimated_ingredient_spend_eur']}. Review the lines below and approve.")
    if tool == "get_intraday_status":
        sigs = r.get("signals", [])
        acting = [x for x in sigs if x["action"] != "hold"]
        if not acting:
            return (f"Everything looks on track right now — {len(sigs)} product-site signals, "
                    f"all holding.")
        top = acting[0]
        return (f"{len(acting)} item(s) need attention right now. Top: {top['action']} "
                f"{top['action_qty']}× {top['product_name']} at {top['site_name']} "
                f"(~€{top['eur_at_risk']:.2f} at risk). See the breakdown below.")
    return "Done."


def _find_date(text: str) -> str | None:
    m = re.search(r"\d{4}-\d{2}-\d{2}", text)
    return m.group(0) if m else None


def _last_complete_day() -> str:
    return (dt.date.today() - dt.timedelta(days=1)).isoformat()
