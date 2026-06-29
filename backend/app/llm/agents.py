"""Agent layer — specialist agents that phrase grounded results in the owner's voice.

Each agent: builds a masked GroundedPayload, routes to the correct model, then runs
the Trust Layer grounding check before returning text. The numbers always come from
the recommender core; the LLM only phrases them.
"""
from __future__ import annotations

from app.recommender.types import Reallocation, Recommendation
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
