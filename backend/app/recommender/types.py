"""Frozen contract types for the recommender core.

These dataclasses are the boundary every track codes against. The recommender is
PURE PYTHON: deterministic, no I/O, no LLM. The LLM never computes these numbers.
"""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field

Confidence = str  # "HIGH" | "LOW"


@dataclass(frozen=True)
class SaleObservation:
    """One historical day of sales for a (product, site)."""

    date: dt.date
    quantity_sold: int
    sold_out: bool = False
    rainy: bool = False
    holiday: bool = False


@dataclass(frozen=True)
class ProductInfo:
    product_id: int
    name: str
    batch_size: int = 1
    price: float = 0.0
    ingredient_cost: float = 0.0

    @property
    def unit_waste_cost(self) -> float:
        """Cost of binning one unit. Prefer ingredient cost; fall back to a
        conservative fraction of price when cost is unknown."""
        if self.ingredient_cost > 0:
            return self.ingredient_cost
        return round(self.price * 0.35, 2)


@dataclass(frozen=True)
class Forecast:
    product_id: int
    site_id: int
    target_date: dt.date
    expected_demand: float
    confidence: Confidence
    sample_size: int
    sigma: float = 0.0  # demand std-dev — drives the newsvendor safety buffer
    missing: str = ""  # what data is missing, when confidence is LOW


@dataclass(frozen=True)
class Recommendation:
    product_id: int
    site_id: int
    target_date: dt.date
    forecast_qty: float
    recommended_qty: int
    confidence: Confidence
    predicted_waste_eur: float
    reason: str


@dataclass(frozen=True)
class SiteState:
    """A site's supply/demand picture for one product+date — input to reallocation."""

    site_id: int
    forecast_demand: float
    planned_production: float  # what this site habitually bakes (recent avg)
    sold_out_rate: float  # 0..1 over recent history
    confidence: Confidence


@dataclass(frozen=True)
class Reallocation:
    product_id: int
    target_date: dt.date
    from_site_id: int
    to_site_id: int
    quantity: int
    eur_waste_avoided: float
    justification: str


@dataclass
class BacktestResult:
    days_evaluated: int = 0
    products_evaluated: int = 0
    # waste (units / €) for each strategy
    baseline_waste_units: int = 0
    naive_waste_units: int = 0
    model_waste_units: int = 0
    baseline_waste_eur: float = 0.0
    naive_waste_eur: float = 0.0
    model_waste_eur: float = 0.0
    # realised profit for each strategy (the honest metric)
    baseline_profit: float = 0.0
    naive_profit: float = 0.0
    model_profit: float = 0.0
    mape: float = 0.0  # forecast error WITH weather/holiday signals (all days)
    mape_weather_naive: float = 0.0  # forecast error WITHOUT them (all days)
    mape_context: float = 0.0  # error on rainy/holiday days, WITH signals
    mape_context_naive: float = 0.0  # error on those same days, WITHOUT signals
    context_days: int = 0
    details: list[dict] = field(default_factory=list)

    # ---- waste avoided (model vs the bakery's historical baseline) ----
    @property
    def waste_avoided_units(self) -> int:
        return self.baseline_waste_units - self.model_waste_units

    @property
    def waste_avoided_eur(self) -> float:
        return round(self.baseline_waste_eur - self.model_waste_eur, 2)

    @property
    def waste_avoided_pct(self) -> float:
        if self.baseline_waste_units == 0:
            return 0.0
        return round(100 * self.waste_avoided_units / self.baseline_waste_units, 1)

    # ---- profit uplift (newsvendor vs a naive bake-to-forecast rule) ----
    @property
    def profit_uplift_vs_naive_eur(self) -> float:
        return round(self.model_profit - self.naive_profit, 2)

    @property
    def profit_uplift_vs_baseline_eur(self) -> float:
        return round(self.model_profit - self.baseline_profit, 2)

    @property
    def profit_uplift_vs_naive_pct(self) -> float:
        if self.naive_profit <= 0:
            return 0.0
        return round(100 * (self.model_profit - self.naive_profit) / self.naive_profit, 1)
