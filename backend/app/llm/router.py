"""LLM model router — applies the Sonnet/Opus rule (AGENT_FRAMEWORK.md §6a).

Two tiers: "reasoning" (judgment) and "execution" (well-defined). Each tier maps to a
model that depends on the configured provider. Providers:
  - anthropic         : Opus (reasoning) / Sonnet (execution)
  - groq              : llama-3.3-70b (reasoning) / llama-3.1-8b (execution)  [free]
  - nvidia            : llama-3.3-70b (reasoning) / llama-3.1-8b (execution)  [free]
  - openai_compatible : you set the models + base_url explicitly

Groq/NVIDIA use the OpenAI-compatible chat API. In offline mode (default in tests/CI)
the router returns deterministic stub text and never touches the network.
"""
from __future__ import annotations

from app.core.config import get_settings

# task -> tier ("reasoning" => bigger model, "execution" => fast model)
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

# Per-provider defaults: (base_url, reasoning_model, execution_model)
PROVIDER_DEFAULTS = {
    "anthropic": ("", "claude-opus-4-8", "claude-sonnet-4-6"),
    "groq": ("https://api.groq.com/openai/v1",
             "llama-3.3-70b-versatile", "llama-3.1-8b-instant"),
    "nvidia": ("https://integrate.api.nvidia.com/v1",
               "meta/llama-3.3-70b-instruct", "meta/llama-3.1-8b-instruct"),
    "openai_compatible": ("", "", ""),
}

SYSTEM_PROMPT = (
    "You are ObradorIQ, a calm bakery operations advisor. Rephrase the given facts in "
    "warm, plain business language. Use ONLY the numbers provided; never invent or change "
    "any number. Keep it to 1-2 sentences."
)


def _provider_defaults(provider: str):
    return PROVIDER_DEFAULTS.get(provider, PROVIDER_DEFAULTS["openai_compatible"])


def model_for(task: str) -> str:
    s = get_settings()
    tier = TASK_TIER.get(task, "execution")
    _, default_reasoning, default_execution = _provider_defaults(s.llm_provider)
    if tier == "reasoning":
        return s.model_reasoning or default_reasoning
    return s.model_execution or default_execution


def complete(task: str, prompt: str, *, offline_stub: str | None = None) -> str:
    """Run a completion for `task`, routed to the correct tier/model.

    `offline_stub` is the deterministic text returned when LLM is offline; callers
    build it from grounded numbers so the Trust Layer's grounding check passes.
    """
    s = get_settings()
    if s.llm_offline or not s.api_key():
        return offline_stub if offline_stub is not None else prompt

    model = model_for(task)
    if s.llm_provider == "anthropic":
        return _complete_anthropic(model, prompt, s.api_key())
    base_url = s.llm_base_url or _provider_defaults(s.llm_provider)[0]
    return _complete_openai_compatible(model, prompt, s.api_key(), base_url)


def _complete_anthropic(model: str, prompt: str, api_key: str) -> str:
    from anthropic import Anthropic

    client = Anthropic(api_key=api_key)
    msg = client.messages.create(
        model=model, max_tokens=300, system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}],
    )
    return "".join(b.text for b in msg.content if getattr(b, "type", "") == "text")


def _complete_openai_compatible(model: str, prompt: str, api_key: str, base_url: str) -> str:
    from openai import OpenAI

    client = OpenAI(api_key=api_key, base_url=base_url or None)
    resp = client.chat.completions.create(
        model=model, max_tokens=300,
        messages=[{"role": "system", "content": SYSTEM_PROMPT},
                  {"role": "user", "content": prompt}],
    )
    return resp.choices[0].message.content or ""
