"""Intraday "living plan" — pure Python, deterministic, no I/O, no LLM.

As the day sells through, project each (product, site)'s end-of-day outcome from a learned
*pace curve* (cumulative fraction of the day's demand arrived by each hour), then recommend
a mid-day action before the money is lost:

    projected_demand > on_hand  -> bake_more (if the site can par-bake and time remains)
                                    else move (if a HIGH-confidence surplus sibling exists)
                                    else hold
    on_hand > projected_demand  -> markdown (clear the surplus)
    otherwise                   -> hold

Every € figure is recommender-computed (grounded); the Trust Layer phrases it, never the LLM.

CONTRACT (frozen by Track 0). Track A implements the bodies; Tracks B (backtest) and D
(service/API) import these signatures. Do not change signatures without re-freezing.
"""
from __future__ import annotations

import datetime as dt

from app.recommender.production import round_to_batch
from app.recommender.types import (
    Confidence,
    Forecast,
    IntradaySignal,
    ProductInfo,
    SiteCapability,
    SiteState,
)

OPEN_HOUR = 7
CLOSE_HOUR = 20  # last transactions land in hour 19; the shop closes at 20:00
MIN_PACE_DAYS = 5  # need this many prior days to trust a learned curve; else DEFAULT_PACE

# Cumulative fraction of a day's demand sold by the END of each hour (07..19), derived from
# the data generator's HOURLY footfall shape (generate_data.py). Monotone up to 1.0 at close.
# Used as the fallback when a (product, site) has too little sale_event history to learn.
DEFAULT_PACE: dict[int, float] = {
    7: 0.048, 8: 0.168, 9: 0.304, 10: 0.400, 11: 0.472, 12: 0.536, 13: 0.616,
    14: 0.688, 15: 0.744, 16: 0.800, 17: 0.872, 18: 0.952, 19: 1.000,
}


# Smallest fraction we ever report as "sold" — keeps divisions safe before the shop warms up.
_EPS = 1e-3


def _hours() -> range:
    """Trading hours whose *end* the pace curve marks: OPEN_HOUR..CLOSE_HOUR-1."""
    return range(OPEN_HOUR, CLOSE_HOUR)


def pace_curve(hourly_counts_by_day: list[dict[int, int]]) -> dict[int, float]:
    """Learn the cumulative arrival curve from prior days' hourly sale counts.

    Args:
        hourly_counts_by_day: one dict per prior day, {hour: units_sold_in_that_hour}.
    Returns:
        {hour: cumulative_fraction_sold_by_end_of_hour} for hours OPEN_HOUR..CLOSE_HOUR-1,
        monotone non-decreasing and ending at 1.0. Falls back to DEFAULT_PACE when there are
        fewer than MIN_PACE_DAYS days of usable history.
    """
    # Per-day cumulative fractions; skip empty days and days that sold nothing.
    per_day: list[dict[int, float]] = []
    for day in hourly_counts_by_day or []:
        total = sum(max(0, int(day.get(h, 0))) for h in _hours())
        if total <= 0:
            continue
        cum = 0
        frac: dict[int, float] = {}
        for h in _hours():
            cum += max(0, int(day.get(h, 0)))
            frac[h] = cum / total
        per_day.append(frac)

    if len(per_day) < MIN_PACE_DAYS:
        return dict(DEFAULT_PACE)

    # Average across days, then force monotone non-decreasing and a clean 1.0 at close.
    curve: dict[int, float] = {}
    prev = 0.0
    for h in _hours():
        avg = sum(d[h] for d in per_day) / len(per_day)
        prev = curve[h] = max(avg, prev)
    curve[CLOSE_HOUR - 1] = 1.0
    return curve


def cumulative_fraction(pace: dict[int, float], as_of: dt.datetime) -> float:
    """Fraction of the day expected sold by `as_of`, linearly interpolated within the current
    hour. Returns a value in (0, 1]; clamps before open / after close."""
    hour = as_of.hour
    if hour < OPEN_HOUR:
        return _EPS
    if hour >= CLOSE_HOUR:
        return 1.0
    minute_frac = (as_of.minute + as_of.second / 60.0) / 60.0
    prev = pace.get(hour - 1, 0.0) if hour > OPEN_HOUR else 0.0
    cur = pace.get(hour, prev)
    val = prev + (cur - prev) * minute_frac
    return min(1.0, max(_EPS, val))


def project_end_of_day(
    sold_so_far: int,
    as_of: dt.datetime,
    pace: dict[int, float],
    daily_forecast: Forecast | None = None,
) -> tuple[float, float]:
    """Project full-day (demand, sigma).

    Base estimate = sold_so_far / cumulative_fraction(as_of). When a daily_forecast prior is
    given, shrink toward it (more weight to the prior early in the day when the pace signal is
    noisy) for stability. Returns (projected_demand, sigma).
    """
    cf = cumulative_fraction(pace, as_of)
    base = max(0, sold_so_far) / cf  # naive full-day run-rate from what's sold so far

    if daily_forecast is not None:
        prior = max(0.0, daily_forecast.expected_demand)
        # Early (cf small) the pace signal is thin, so lean on the prior; blend toward the
        # observed run-rate as the day fills in.
        w_pace = cf
        projected = w_pace * base + (1.0 - w_pace) * prior
        # Uncertainty shrinks as the day resolves; keep a small floor so it's never zero.
        sigma = max(daily_forecast.sigma * (1.0 - cf), 0.05 * projected)
    else:
        projected = base
        sigma = (0.10 + 0.15 * (1.0 - cf)) * projected

    return projected, sigma


def projected_sellout_time(
    on_hand: int,
    pace: dict[int, float],
    projected_demand: float,
) -> dt.time | None:
    """Clock time at which `on_hand` units are exhausted, given the pace curve and projected
    full-day demand. None when on_hand covers the whole day (no stockout projected)."""
    if projected_demand <= 0 or on_hand >= projected_demand:
        return None

    target = on_hand / projected_demand  # cumulative fraction at which stock runs out
    prev = 0.0
    for h in _hours():
        cur = pace.get(h, prev)
        if cur >= target:
            span = cur - prev
            frac = (target - prev) / span if span > 0 else 0.0
            minute = min(59, int(frac * 60))
            return dt.time(hour=h, minute=minute)
        prev = cur
    # Pace ends at 1.0, so a target < 1 is always reached; fall back to the last minute.
    return dt.time(hour=CLOSE_HOUR - 1, minute=59)


def intraday_signal(
    product: ProductInfo,
    site_id: int,
    as_of: dt.datetime,
    sold_so_far: int,
    on_hand: int,
    pace: dict[int, float],
    daily_forecast: Forecast | None = None,
    capability: SiteCapability | None = None,
    sibling_states: list[SiteState] | None = None,
    confidence: Confidence = "LOW",
) -> IntradaySignal:
    """Decide the mid-day action for one (product, site). Deterministic; see module docstring.

    €-at-risk semantics (grounded):
      shortfall -> lost margin  = (product.price - product.unit_waste_cost) * unmet_gap
      surplus   -> leftover cost = product.unit_waste_cost * surplus
    `sibling_states` are the same-product SiteStates at other sites (for the `move` option);
    only a HIGH-confidence surplus sibling may be chosen as a `move` source. `capability`
    gates bake_more/move (defaults to fully capable). Never acts on LOW confidence except to
    surface a `hold` with the projection.
    """
    capability = capability or SiteCapability()
    siblings = sibling_states or []
    batch = max(1, product.batch_size)
    # A move/bake is only worth suggesting once the gap is a meaningful part of a batch.
    threshold = batch * 0.5

    projected_demand, _sigma = project_end_of_day(sold_so_far, as_of, pace, daily_forecast)
    projected_demand = round(projected_demand, 1)
    sellout_time = projected_sellout_time(on_hand, pace, projected_demand)

    price = product.price
    uwc = product.unit_waste_cost
    unit_margin = max(price - uwc, 0.0)

    from_site_id: int | None = None
    when = _fmt_time(sellout_time)

    if projected_demand > on_hand + threshold:
        # --- shortfall: we're pacing hot and will run out before close ---
        gap = projected_demand - on_hand
        eur_at_risk = round(unit_margin * gap, 2)
        qty = round_to_batch(gap, batch)
        baking_time_left = as_of.hour < CLOSE_HOUR - 1

        if capability.can_bake_off and baking_time_left:
            action, action_qty = "bake_more", qty
            reason = (
                f"{product.name} is pacing hot at site {site_id} — projected to sell out "
                f"~{when}. Bake {action_qty} more now to protect ~€{eur_at_risk:.0f} of sales."
            )
        else:
            source = _best_surplus_sibling(siblings, batch) if capability.can_move else None
            if source is not None:
                action, action_qty = "move", qty
                from_site_id = source.site_id
                reason = (
                    f"{product.name}: projected to sell out ~{when} at site {site_id}. "
                    f"Move {action_qty} from site {from_site_id} to protect "
                    f"~€{eur_at_risk:.0f} of sales."
                )
            else:
                action, action_qty = "hold", 0
                reason = (
                    f"{product.name}: projected short by ~{gap:.0f} at site {site_id} "
                    f"(sell out ~{when}), but no bake time or surplus sibling is available — "
                    f"holding. ~€{eur_at_risk:.0f} at risk."
                )

    elif on_hand > projected_demand + threshold:
        # --- surplus: more on hand than the day will take ---
        surplus = on_hand - projected_demand
        action = "markdown"
        action_qty = int(round(surplus))
        eur_at_risk = round(uwc * surplus, 2)
        sellout_time = None  # on-hand covers the day; nothing sells out
        reason = (
            f"{product.name}: projected surplus of ~{action_qty} at site {site_id}. "
            f"Mark down now to recover from ~€{eur_at_risk:.0f} of leftover cost."
        )

    else:
        # --- balanced: on track ---
        action, action_qty, eur_at_risk = "hold", 0, 0.0
        reason = (
            f"{product.name} is on track at site {site_id} "
            f"(projected {projected_demand:.0f} vs {on_hand} on hand). Hold."
        )

    if confidence == "LOW":
        reason += " Low confidence — treat as a projection, not a promise."

    return IntradaySignal(
        product_id=product.product_id,
        site_id=site_id,
        as_of=as_of,
        sold_so_far=sold_so_far,
        on_hand=on_hand,
        projected_demand=projected_demand,
        projected_sellout_time=sellout_time,
        action=action,
        action_qty=action_qty,
        from_site_id=from_site_id,
        eur_at_risk=eur_at_risk,
        confidence=confidence,
        reason=reason,
    )


def _best_surplus_sibling(siblings: list[SiteState], batch: int) -> SiteState | None:
    """The HIGH-confidence sibling with the largest usable surplus (>= one batch), or None."""
    best: SiteState | None = None
    best_surplus = 0.0
    for s in siblings:
        surplus = s.planned_production - s.forecast_demand
        if s.confidence == "HIGH" and surplus >= batch and surplus > best_surplus:
            best, best_surplus = s, surplus
    return best


def _fmt_time(t: dt.time | None) -> str:
    return "—" if t is None else f"{t.hour:02d}:{t.minute:02d}"
