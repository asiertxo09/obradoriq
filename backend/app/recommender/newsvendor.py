"""Newsvendor model — the profit-optimal answer to "how many should we bake?".

For a perishable product, the optimal order quantity balances the cost of baking one
too many (overage, Co) against the cost of baking one too few (underage, Cu):

    critical ratio  CR = Cu / (Cu + Co)
    optimal qty     q* = F^-1(CR)        (the CR-quantile of the demand distribution)

with, per unit:
    Cu = price - unit_cost   (lost margin when we sell out)
    Co = unit_cost           (money sunk into a leftover; no salvage)

So high-margin items (Cu >> Co) get baked above the mean to protect availability, while
low-margin items hug the mean. This is a genuine profit optimization, not a heuristic —
and it makes `risk_preference` a principled tilt on CR rather than a +/- one-batch hack.
Demand is modelled as Normal(mean, sigma); q* = mean + z(CR) * sigma.
"""
from __future__ import annotations

from statistics import NormalDist

_N = NormalDist()
CR_CLAMP = (0.05, 0.95)


def critical_ratio(price: float, unit_cost: float, risk_preference: str = "waste") -> float:
    cu = max(price - unit_cost, 0.0)  # underage: lost margin
    co = max(unit_cost, 0.01)         # overage: cost of a leftover
    cr = cu / (cu + co) if (cu + co) > 0 else 0.5
    # Owner tilt: lean toward availability (higher CR) or toward less waste (lower CR).
    if risk_preference == "availability":
        cr = cr + (1 - cr) * 0.25
    elif risk_preference == "waste":
        cr = cr * 0.85
    return min(max(cr, CR_CLAMP[0]), CR_CLAMP[1])


def newsvendor_quantity(mean: float, sigma: float, cr: float) -> float:
    """Unrounded profit-optimal quantity for a Normal(mean, sigma) demand."""
    if sigma <= 0:
        return max(0.0, mean)
    return max(0.0, mean + _N.inv_cdf(cr) * sigma)


def expected_leftover(qty: float, mean: float, sigma: float) -> float:
    """E[max(0, qty - demand)] for Normal demand — the expected number binned."""
    if sigma <= 0:
        return max(0.0, qty - mean)
    z = (qty - mean) / sigma
    return (qty - mean) * _N.cdf(z) + sigma * _pdf(z)


def _pdf(z: float) -> float:
    from math import exp, pi, sqrt

    return exp(-0.5 * z * z) / sqrt(2 * pi)
