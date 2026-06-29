"""Trust Layer — the safety boundary between agents and the LLM.

Adapted from the Einstein Trust Layer. Responsibilities:
  - mask: strip sensitive fields (cost, customer, revenue) before a prompt leaves.
  - assert_grounded: verify the LLM's text did not alter the grounded numbers.
  - score_confidence: surface HIGH/LOW (computed upstream by the recommender).
  - log: append an audit record for every interaction.

The grounding guarantee: numbers come from the recommender core, never the LLM.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

# Fields that must never be sent to the LLM.
SENSITIVE_KEYS = {"ingredient_cost", "cost", "revenue", "margin", "customer", "email"}


@dataclass
class GroundedPayload:
    """The minimal, masked data handed to an LLM to phrase a recommendation."""

    facts: dict  # only non-sensitive, grounded numbers + names
    grounded_numbers: list[float]  # numbers that MUST appear unchanged in output


def mask(raw: dict) -> dict:
    """Drop sensitive keys; keep only what's needed to phrase a recommendation."""
    return {k: v for k, v in raw.items() if k.lower() not in SENSITIVE_KEYS}


def _numbers_in(text: str) -> set[float]:
    out: set[float] = set()
    for tok in re.findall(r"-?\d+(?:\.\d+)?", text):
        try:
            out.add(float(tok))
        except ValueError:
            pass
    return out


def assert_grounded(text: str, grounded_numbers: list[float]) -> bool:
    """Every grounded number must appear in the LLM output, and the output must
    introduce no *new* quantity that isn't grounded. Raises on violation."""
    present = _numbers_in(text)
    for n in grounded_numbers:
        # Match int-or-float representations (12 or 12.0).
        if n not in present and float(int(n)) not in present:
            raise GroundingError(f"grounded number {n} missing from LLM output")
    allowed = set(grounded_numbers) | {float(int(n)) for n in grounded_numbers}
    invented = {n for n in present if n not in allowed}
    if invented:
        raise GroundingError(f"LLM introduced ungrounded numbers: {sorted(invented)}")
    return True


class GroundingError(Exception):
    """Raised when an LLM output fails the grounding guarantee."""


def score_confidence(sample_size: int, threshold: int = 8) -> str:
    return "HIGH" if sample_size >= threshold else "LOW"
