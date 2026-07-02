"""Agent layer — specialist agents that phrase grounded results in the owner's voice.

Each agent: builds a masked GroundedPayload, routes to the correct model, then runs
the Trust Layer grounding check before returning text. The numbers always come from
the recommender core; the LLM only phrases them.
"""
from __future__ import annotations

from app.recommender.types import IntradaySignal, Reallocation, Recommendation
from app.trust import layer
from app.trust.layer import GroundingError


def _grounded_or_stub(text: str, grounded: list[float], stub: str) -> str:
    """Trust Layer gate: accept the LLM text only if it passes the grounding check;
    otherwise reject it and return the deterministic, guaranteed-grounded stub."""
    try:
        layer.assert_grounded(text, grounded)
        return text
    except GroundingError:
        return stub


def phrase_recommendation(rec: Recommendation, product_name: str) -> str:
    """Production Planning Agent (Sonnet) — frame a recommendation as €-waste-avoided."""
    grounded = [float(rec.recommended_qty), round(rec.forecast_qty)]
    if rec.predicted_waste_eur > 0:
        grounded.append(rec.predicted_waste_eur)

    facts = layer.mask({
        "product": product_name,
        "recommended_qty": rec.recommended_qty,
        "forecast": round(rec.forecast_qty),
        "predicted_waste_eur": rec.predicted_waste_eur,
        "confidence": rec.confidence,
    })
    prompt = f"Facts: {facts}. Write a one-line production recommendation."

    waste_clause = (
        f" That trims about €{rec.predicted_waste_eur:.2f} of likely leftovers."
        if rec.predicted_waste_eur > 0 else ""
    )
    stub = (
        f"For {product_name}, bake {rec.recommended_qty} tomorrow — demand looks like "
        f"about {round(rec.forecast_qty)}.{waste_clause} ({rec.confidence} confidence)."
    )

    from app.llm.router import complete

    text = complete("phrase_recommendation", prompt, offline_stub=stub)
    return _grounded_or_stub(text, grounded, stub)


def justify_reallocation(realloc: Reallocation, product_name: str,
                         from_site: str, to_site: str) -> str:
    """Reallocation Agent (Opus) — explain a cross-site plan-level shift."""
    grounded = [float(realloc.quantity), realloc.eur_waste_avoided]
    prompt = (
        f"Facts: product={product_name}, move {realloc.quantity} planned units from "
        f"{from_site} to {to_site}, recovering €{realloc.eur_waste_avoided:.2f}. "
        "Explain why in one sentence."
    )
    stub = (
        f"Shift {realloc.quantity} of {product_name}'s planned production from {from_site} "
        f"to {to_site}: {from_site} over-bakes them while {to_site} sells out, so this "
        f"recovers about €{realloc.eur_waste_avoided:.2f} with no extra baking."
    )
    from app.llm.router import complete

    text = complete("reallocation_justify", prompt, offline_stub=stub)
    return _grounded_or_stub(text, grounded, stub)


def phrase_intraday(sig: IntradaySignal, product_name: str, site_name: str,
                    from_site_name: str = "") -> str:
    """Intraday Agent (execution tier) — phrase a mid-day 'living plan' alert.

    Grounded numbers are [action_qty, eur_at_risk] (eur_at_risk only when > 0, matching the
    conditional phrasing below). The projected sellout time is informational only — it is
    never rendered as a bare digit in the LLM-facing text, so it can never be mistaken for a
    grounded (or invented) number by the Trust Layer's digit-matching check.
    """
    grounded = [float(sig.action_qty)]
    if sig.eur_at_risk > 0:
        grounded.append(sig.eur_at_risk)

    facts = layer.mask({
        "product": product_name,
        "site": site_name,
        "action": sig.action,
        "action_qty": sig.action_qty,
        "eur_at_risk": sig.eur_at_risk,
        "confidence": sig.confidence,
    })
    prompt = f"Facts: {facts}. Write a one-line intraday 'living plan' alert for the owner."

    risk_clause = (f" to protect about €{sig.eur_at_risk:.2f} of sales"
                   if sig.eur_at_risk > 0 else "")
    recover_clause = (f" to recover about €{sig.eur_at_risk:.2f} of leftover cost"
                      if sig.eur_at_risk > 0 else "")

    if sig.action == "bake_more":
        stub = (f"{product_name} at {site_name} is pacing hot — bake {sig.action_qty} more "
               f"now{risk_clause}. ({sig.confidence} confidence.)")
    elif sig.action == "move":
        source = f" from {from_site_name}" if from_site_name else ""
        stub = (f"{product_name} at {site_name} is projected to run short — move "
               f"{sig.action_qty}{source} now{risk_clause}. ({sig.confidence} confidence.)")
    elif sig.action == "markdown":
        stub = (f"{product_name} at {site_name} has a projected surplus of {sig.action_qty} — "
               f"mark it down now{recover_clause}. ({sig.confidence} confidence.)")
    else:  # hold
        stub = (f"{product_name} at {site_name} is on track — hold, {sig.action_qty} extra "
               f"units needed right now. ({sig.confidence} confidence.)")

    from app.llm.router import complete

    text = complete("phrase_intraday", prompt, offline_stub=stub)
    return _grounded_or_stub(text, grounded, stub)
