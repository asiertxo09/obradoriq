"""Trust Layer + agent tests: grounding guarantee, masking, model routing."""
from __future__ import annotations

import datetime as dt

import pytest

from app.llm import agents, router
from app.recommender.types import Reallocation, Recommendation
from app.trust import layer
from app.trust.layer import GroundingError


# ---- masking ----
def test_mask_strips_sensitive_keys():
    raw = {"product": "Croissant", "recommended_qty": 30, "ingredient_cost": 0.55,
           "revenue": 120.0, "customer": "Ana"}
    masked = layer.mask(raw)
    assert "product" in masked and "recommended_qty" in masked
    assert "ingredient_cost" not in masked
    assert "revenue" not in masked
    assert "customer" not in masked


# ---- grounding ----
def test_assert_grounded_accepts_matching_numbers():
    assert layer.assert_grounded("Bake 30 tomorrow, demand ~24.", [30, 24])


def test_assert_grounded_rejects_missing_number():
    with pytest.raises(GroundingError):
        layer.assert_grounded("Bake some tomorrow.", [30])


def test_assert_grounded_rejects_invented_number():
    with pytest.raises(GroundingError):
        layer.assert_grounded("Bake 30, and you'll earn €999.", [30])


# ---- model routing ----
def test_routing_reasoning_uses_opus():
    assert "opus" in router.model_for("reallocation_justify").lower()
    assert "opus" in router.model_for("orchestrate").lower()


def test_routing_execution_uses_sonnet():
    assert "sonnet" in router.model_for("phrase_recommendation").lower()
    assert "sonnet" in router.model_for("report_format").lower()


# ---- agents (offline stub path) keep grounding ----
def test_phrase_recommendation_is_grounded():
    rec = Recommendation(
        product_id=1, site_id=1, target_date=dt.date(2026, 7, 1),
        forecast_qty=24.0, recommended_qty=30, confidence="HIGH",
        predicted_waste_eur=3.30, reason="x",
    )
    text = agents.phrase_recommendation(rec, "Croissant")
    assert "30" in text
    assert "Croissant" in text


def test_justify_reallocation_is_grounded():
    r = Reallocation(
        product_id=1, target_date=dt.date(2026, 7, 1), from_site_id=2, to_site_id=1,
        quantity=12, eur_waste_avoided=11.40, justification="x",
    )
    text = agents.justify_reallocation(r, "Almond Croissant", "Barrio", "Centro")
    assert "12" in text
    assert "Barrio" in text and "Centro" in text
