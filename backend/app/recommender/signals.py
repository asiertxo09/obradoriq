"""External-signal elasticities — the information edge ML/gut both lack day-to-day.

We *learn* a product/site's sensitivity to rain and to holidays from its own history
(ratio of mean demand on rainy vs dry days, holiday vs normal days), then apply it to the
target day's known weather/holiday context. This is genuine learning from data — not a
hard-coded rule — so the backtest improvement is real, not circular.
"""
from __future__ import annotations

import statistics

from app.recommender.types import SaleObservation

RAIN_THRESHOLD_MM = 2.0
MIN_GROUP = 3  # need at least this many days in a group to trust an elasticity
RAIN_CLAMP = (0.60, 1.20)
HOLIDAY_CLAMP = (0.70, 1.80)


def is_rainy(precip_mm: float) -> bool:
    return precip_mm >= RAIN_THRESHOLD_MM


def _eff(o: SaleObservation) -> float:
    from app.recommender.forecast import effective_demand

    return effective_demand(o)


def context_factors(history: list[SaleObservation]) -> tuple[float, float]:
    """Return (rain_factor, holiday_factor) learned from history, relative to a
    dry/non-holiday baseline. Falls back to 1.0 when a group is too small to trust."""
    dry_normal = [o for o in history if not o.rainy and not o.holiday]
    rainy = [o for o in history if o.rainy and not o.holiday]
    holiday = [o for o in history if o.holiday]

    if len(dry_normal) < MIN_GROUP:
        return 1.0, 1.0
    base = statistics.mean(_eff(o) for o in dry_normal)
    if base <= 0:
        return 1.0, 1.0

    rain_factor = 1.0
    if len(rainy) >= MIN_GROUP:
        rain_factor = _clamp(statistics.mean(_eff(o) for o in rainy) / base, RAIN_CLAMP)
    holiday_factor = 1.0
    if len(holiday) >= MIN_GROUP:
        holiday_factor = _clamp(statistics.mean(_eff(o) for o in holiday) / base, HOLIDAY_CLAMP)
    return round(rain_factor, 3), round(holiday_factor, 3)


def _clamp(x: float, bounds: tuple[float, float]) -> float:
    return min(max(x, bounds[0]), bounds[1])
