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


def test_routing_switches_to_groq_models(monkeypatch):
    """With provider=groq, tiers map to free llama models (reasoning vs execution)."""
    from app.core.config import get_settings

    monkeypatch.setenv("LLM_PROVIDER", "groq")
    get_settings.cache_clear()
    try:
        assert "70b" in router.model_for("reallocation_justify")   # reasoning tier
        assert "8b" in router.model_for("phrase_recommendation")   # execution tier
    finally:
        get_settings.cache_clear()  # restore default for other tests


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


def test_ungrounded_llm_output_is_rejected_to_stub(monkeypatch):
    """If a live model invents a number, the Trust Layer rejects it and falls back
    to the deterministic grounded stub (never shows ungrounded figures)."""
    monkeypatch.setattr("app.llm.router.complete",
                        lambda *a, **k: "Bake 30 and you'll magically earn €999 extra!")
    rec = Recommendation(
        product_id=1, site_id=1, target_date=dt.date(2026, 7, 1),
        forecast_qty=24.0, recommended_qty=30, confidence="HIGH",
        predicted_waste_eur=0.0, reason="x",
    )
    text = agents.phrase_recommendation(rec, "Croissant")
    assert "999" not in text          # ungrounded number rejected
    assert "30" in text and "Croissant" in text  # safe stub returned


# ---- provider call parameter plumbing (temperature / JSON mode) ----

def test_complete_openai_compatible_passes_temperature_and_json_mode(monkeypatch):
    captured = {}

    class FakeCompletions:
        def create(self, **kwargs):
            captured.update(kwargs)

            class Msg:
                content = "ok"

            class Choice:
                message = Msg()

            class Resp:
                choices = [Choice()]

            return Resp()

    class FakeChat:
        completions = FakeCompletions()

    class FakeOpenAI:
        def __init__(self, api_key=None, base_url=None):
            self.chat = FakeChat()

    monkeypatch.setattr("openai.OpenAI", FakeOpenAI)

    router._complete_openai_compatible(
        "llama-3.3-70b-versatile", "hello", "key", "https://api.groq.com/openai/v1",
        temperature=0.0, json_mode=True)

    assert captured["temperature"] == 0.0
    assert captured["response_format"] == {"type": "json_object"}


def test_complete_openai_compatible_omits_temperature_and_json_mode_by_default(monkeypatch):
    captured = {}

    class FakeCompletions:
        def create(self, **kwargs):
            captured.update(kwargs)

            class Msg:
                content = "ok"

            class Choice:
                message = Msg()

            class Resp:
                choices = [Choice()]

            return Resp()

    class FakeChat:
        completions = FakeCompletions()

    class FakeOpenAI:
        def __init__(self, api_key=None, base_url=None):
            self.chat = FakeChat()

    monkeypatch.setattr("openai.OpenAI", FakeOpenAI)

    router._complete_openai_compatible("model", "hello", "key", "https://x")

    assert "temperature" not in captured
    assert "response_format" not in captured


def test_complete_anthropic_passes_temperature(monkeypatch):
    captured = {}

    class FakeMessages:
        def create(self, **kwargs):
            captured.update(kwargs)

            class Block:
                type = "text"
                text = "ok"

            class Msg:
                content = [Block()]

            return Msg()

    class FakeAnthropic:
        def __init__(self, api_key=None):
            self.messages = FakeMessages()

    monkeypatch.setattr("anthropic.Anthropic", FakeAnthropic)

    router._complete_anthropic("claude-opus-4-8", "hello", "key", temperature=0.0)

    assert captured["temperature"] == 0.0


def test_complete_anthropic_omits_temperature_by_default(monkeypatch):
    captured = {}

    class FakeMessages:
        def create(self, **kwargs):
            captured.update(kwargs)

            class Block:
                type = "text"
                text = "ok"

            class Msg:
                content = [Block()]

            return Msg()

    class FakeAnthropic:
        def __init__(self, api_key=None):
            self.messages = FakeMessages()

    monkeypatch.setattr("anthropic.Anthropic", FakeAnthropic)

    router._complete_anthropic("claude-opus-4-8", "hello", "key")

    assert "temperature" not in captured


def test_justify_reallocation_is_grounded():
    r = Reallocation(
        product_id=1, target_date=dt.date(2026, 7, 1), from_site_id=2, to_site_id=1,
        quantity=12, eur_waste_avoided=11.40, justification="x",
    )
    text = agents.justify_reallocation(r, "Almond Croissant", "Barrio", "Centro")
    assert "12" in text
    assert "Barrio" in text and "Centro" in text
