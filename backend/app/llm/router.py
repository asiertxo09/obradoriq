"""LLM model router — applies the Sonnet/Opus rule (AGENT_FRAMEWORK.md §6a).

Opus for reasoning/judgment tasks; Sonnet for well-defined execution. In offline
mode (default in tests/CI) it returns deterministic stub text and never touches the
network — so tests are reproducible and the grounding guarantee can be asserted.
"""
from __future__ import annotations

from app.core.config import get_settings

# task -> tier ("reasoning" => Opus, "execution" => Sonnet)
TASK_TIER = {
    "orchestrate": "reasoning",
    "reallocation_justify": "reasoning",
    "low_confidence_diagnosis": "reasoning",
    "true_margin_narrative": "reasoning",
    "phrase_recommendation": "execution",
    "csv_mapping": "execution",
    "report_format": "execution",
    "scope_classify": "execution",
}


def model_for(task: str) -> str:
    s = get_settings()
    tier = TASK_TIER.get(task, "execution")
    return s.model_reasoning if tier == "reasoning" else s.model_execution


def complete(task: str, prompt: str, *, offline_stub: str | None = None) -> str:
    """Run a completion for `task`, routed to the correct model.

    `offline_stub` is the deterministic text returned when LLM is offline; callers
    build it from grounded numbers so the Trust Layer's grounding check passes.
    """
    settings = get_settings()
    model = model_for(task)
    if settings.llm_offline or not settings.anthropic_api_key:
        return offline_stub if offline_stub is not None else prompt

    # Online path — kept minimal; the system prompt enforces grounding.
    from anthropic import Anthropic  # imported lazily

    client = Anthropic(api_key=settings.anthropic_api_key)
    msg = client.messages.create(
        model=model,
        max_tokens=300,
        system=(
            "You are ObradorIQ, a calm bakery operations advisor. Rephrase the given "
            "facts in warm, plain business language. Use ONLY the numbers provided; "
            "never invent or change any number. Keep it to 1-2 sentences."
        ),
        messages=[{"role": "user", "content": prompt}],
    )
    return "".join(block.text for block in msg.content if getattr(block, "type", "") == "text")
