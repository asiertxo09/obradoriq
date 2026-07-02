"""Intraday backtest — quantifies the value of a mid-morning ("11:00 check-in") action.

Walk-forward, per (product, site, day): learn a pace curve from strictly-PRIOR days'
hourly sale counts (`intraday.pace_curve`), project the day's end-of-day outcome from
what had sold by the decision hour (`intraday.intraday_signal`), and evaluate the
recommended action against that day's TRUE (uncensored) demand — the same
sold-out-day uncensoring convention as the daily backtest (backtest.py / forecast.py's
SOLD_OUT_UPLIFT).

    bake_more / move -> recovered = min(action_qty, max(0, true_demand - on_hand)) * unit_margin
    markdown          -> recovered = min(action_qty, max(0, on_hand - true_demand))
                                      * unit_waste_cost * SALVAGE_RECOVERY_FRACTION
    hold              -> 0

Aggregated across the chain this produces the submission's intraday headline: € recovered
by an 11:00 check-in, vs. a €0 do-nothing baseline.

Pure Python; deterministic given the same data (no randomness in evaluation).
`load_from_db` / `main` are an optional, standalone-friendly convenience layer — the core
harness (`evaluate_intraday_day`, `run_intraday_backtest`) takes plain in-memory structures
and needs no DB.
"""
from __future__ import annotations

import datetime as dt
from collections import defaultdict
from dataclasses import dataclass, field

from app.recommender.forecast import SOLD_OUT_UPLIFT
from app.recommender.intraday import MIN_PACE_DAYS, pace_curve, intraday_signal
from app.recommender.types import IntradaySignal, ProductInfo, SiteCapability, SiteState

DECISION_HOUR = 11  # the mid-morning check-in hour this backtest evaluates
SALVAGE_RECOVERY_FRACTION = 0.5  # a markdown clears leftover stock at ~half its waste cost


@dataclass
class IntradayDayRecord:
    """One (product, site) day of intraday activity — the backtest's input unit.

    `hourly_counts` are THIS day's own units sold per hour (07..19), used both to learn
    prior days' pace curves and to derive `sold_so_far` at the decision hour.
    """

    date: dt.date
    hourly_counts: dict[int, int]
    waste: int = 0        # units binned that day (0 on sold-out days)
    sold_out: bool = False  # True when demand exceeded production (data is censored)

    @property
    def sold(self) -> int:
        return sum(max(0, q) for q in self.hourly_counts.values())

    @property
    def production(self) -> int:
        """Units baked that day — sold + waste. This is `on_hand` at the decision hour:
        the backtest evaluates against what was physically available that morning."""
        return self.sold + self.waste

    @property
    def true_demand(self) -> float:
        """Uncensored full-day demand. On sold-out days the recorded `sold` undercounts
        demand (everyone who wanted one didn't get one), so we uplift it — the same
        correction `forecast.effective_demand` applies for the daily backtest."""
        return self.sold * SOLD_OUT_UPLIFT if self.sold_out else float(self.sold)

    def sold_so_far(self, decision_hour: int = DECISION_HOUR) -> int:
        """Units sold strictly before `decision_hour` (e.g. hours 07..10 for 11:00)."""
        return sum(max(0, q) for h, q in self.hourly_counts.items() if h < decision_hour)


@dataclass
class IntradayEvaluation:
    """The recommended action for one (product, site, day) and the € it recovered."""

    product_id: int
    product_name: str
    site_id: int
    date: dt.date
    action: str
    action_qty: int
    eur_recovered: float
    signal: IntradaySignal


@dataclass
class IntradayBacktestResult:
    evaluations: list[IntradayEvaluation] = field(default_factory=list)

    @property
    def days_evaluated(self) -> int:
        return len(self.evaluations)

    @property
    def actionable_signals(self) -> int:
        """Signals that recommended something other than hold."""
        return sum(1 for e in self.evaluations if e.action != "hold")

    @property
    def total_eur_recovered(self) -> float:
        return round(sum(e.eur_recovered for e in self.evaluations), 2)

    @property
    def baseline_eur_recovered(self) -> float:
        """Do-nothing baseline: no mid-day intervention is ever taken."""
        return 0.0

    @property
    def by_action(self) -> dict[str, tuple[int, float]]:
        """{action: (count, total € recovered)} — for the printed breakdown."""
        totals: dict[str, list] = defaultdict(lambda: [0, 0.0])
        for e in self.evaluations:
            row = totals[e.action]
            row[0] += 1
            row[1] += e.eur_recovered
        return {action: (n, round(eur, 2)) for action, (n, eur) in totals.items()}


def evaluate_intraday_day(
    product: ProductInfo,
    site_id: int,
    day: IntradayDayRecord,
    prior_days: list[IntradayDayRecord],
    decision_hour: int = DECISION_HOUR,
    capability: SiteCapability | None = None,
    sibling_states: list[SiteState] | None = None,
    confidence: str | None = None,
) -> IntradayEvaluation:
    """Evaluate the decision-hour signal for one (product, site, day) against the day's
    true demand. `prior_days` must be strictly before `day` (walk-forward)."""
    as_of = dt.datetime.combine(day.date, dt.time(hour=decision_hour))
    sold_so_far = day.sold_so_far(decision_hour)
    on_hand = day.production
    pace = pace_curve([d.hourly_counts for d in prior_days])
    conf = confidence or ("HIGH" if len(prior_days) >= MIN_PACE_DAYS else "LOW")

    signal = intraday_signal(
        product=product,
        site_id=site_id,
        as_of=as_of,
        sold_so_far=sold_so_far,
        on_hand=on_hand,
        pace=pace,
        capability=capability,
        sibling_states=sibling_states,
        confidence=conf,
    )

    true_demand = day.true_demand
    unit_margin = max(product.price - product.unit_waste_cost, 0.0)

    if signal.action in ("bake_more", "move"):
        recovered = min(signal.action_qty, max(0.0, true_demand - on_hand)) * unit_margin
    elif signal.action == "markdown":
        recovered = (
            min(signal.action_qty, max(0.0, on_hand - true_demand))
            * product.unit_waste_cost
            * SALVAGE_RECOVERY_FRACTION
        )
    else:
        recovered = 0.0

    return IntradayEvaluation(
        product_id=product.product_id,
        product_name=product.name,
        site_id=site_id,
        date=day.date,
        action=signal.action,
        action_qty=signal.action_qty,
        eur_recovered=round(recovered, 2),
        signal=signal,
    )


def run_intraday_backtest(
    series: dict[tuple[str, int], list[IntradayDayRecord]],
    products: dict[str, ProductInfo],
    decision_hour: int = DECISION_HOUR,
    capability: SiteCapability | None = None,
) -> IntradayBacktestResult:
    """series keyed by (product_name, site_id) -> chronological IntradayDayRecords.

    Walk-forward: each day is evaluated using only the days strictly before it as pace
    history. Deterministic — identical input yields identical output.
    """
    result = IntradayBacktestResult()
    for (pname, site_id), days in series.items():
        product = products[pname]
        days = sorted(days, key=lambda d: d.date)
        for idx, today in enumerate(days):
            prior = days[:idx]
            result.evaluations.append(
                evaluate_intraday_day(
                    product, site_id, today, prior, decision_hour, capability
                )
            )
    return result


# ---- DB loading (optional convenience for the standalone harness / demo) ----
def load_from_db(bakery_name: str = "Obrador Demo") -> tuple[dict, dict]:
    """Build (series, products) from the app's minute-stamped sale_event data.

    Returns ({}, {}) if the bakery or its intraday data isn't present, so callers can
    fall back to a self-contained scenario without a DB.
    """
    from app.models import (
        Bakery,
        Product,
        SaleEvent,
        SalesRecord,
        SessionLocal,
        Site,
        WasteRecord,
        init_db,
    )

    init_db()
    db = SessionLocal()
    try:
        bakery = db.query(Bakery).filter_by(name=bakery_name).first()
        if bakery is None:
            return {}, {}

        product_rows = db.query(Product).filter_by(bakery_id=bakery.id).all()
        products: dict[str, ProductInfo] = {
            p.name: ProductInfo(
                product_id=p.id, name=p.name, batch_size=p.batch_size,
                price=p.price, ingredient_cost=p.ingredient_cost,
            )
            for p in product_rows
        }
        product_name_by_id = {p.id: p.name for p in product_rows}
        site_ids = [s.id for s in db.query(Site).filter_by(bakery_id=bakery.id).all()]
        if not products or not site_ids:
            return {}, {}

        waste_lookup: dict[tuple[int, int, dt.date], int] = {
            (w.product_id, w.site_id, w.date): w.quantity_wasted
            for w in db.query(WasteRecord).filter(WasteRecord.site_id.in_(site_ids)).all()
        }
        sold_out_lookup: dict[tuple[int, int, dt.date], bool] = {
            (sr.product_id, sr.site_id, sr.date): sr.sold_out
            for sr in db.query(SalesRecord).filter(SalesRecord.site_id.in_(site_ids)).all()
        }

        hourly: dict[tuple[int, int, dt.date], dict[int, int]] = defaultdict(
            lambda: defaultdict(int)
        )
        events = db.query(SaleEvent).filter(SaleEvent.site_id.in_(site_ids)).all()
        for ev in events:
            hourly[(ev.product_id, ev.site_id, ev.ts.date())][ev.ts.hour] += ev.quantity
        if not events:
            return {}, {}

        series: dict[tuple[str, int], list[IntradayDayRecord]] = defaultdict(list)
        for (pid, sid, date), counts in hourly.items():
            pname = product_name_by_id.get(pid)
            if pname is None:
                continue
            series[(pname, sid)].append(
                IntradayDayRecord(
                    date=date,
                    hourly_counts=dict(counts),
                    waste=waste_lookup.get((pid, sid, date), 0),
                    sold_out=sold_out_lookup.get((pid, sid, date), False),
                )
            )
        for key in series:
            series[key].sort(key=lambda d: d.date)
        return dict(series), products
    finally:
        db.close()


# ---- self-contained synthetic scenario (no DB required) ----
def _flat_day(units_per_hour: int, date: dt.date, waste: int = 8) -> IntradayDayRecord:
    from app.recommender.intraday import CLOSE_HOUR, OPEN_HOUR

    counts = {h: units_per_hour for h in range(OPEN_HOUR, CLOSE_HOUR)}
    return IntradayDayRecord(date=date, hourly_counts=counts, waste=waste, sold_out=False)


def _synthetic_series() -> tuple[dict, dict]:
    """A deterministic, hand-built chain: one product across three sites pacing HOT
    (site 1), COLD/surplus (site 2), and balanced (site 3), each preceded by 5 typical
    "habitual" days so a real pace curve is learned. No randomness."""
    product = ProductInfo(product_id=1, name="Croissant", batch_size=12, price=2.0,
                           ingredient_cost=0.6)
    products = {product.name: product}
    start = dt.date(2026, 6, 1)

    def prior_days() -> list[IntradayDayRecord]:
        return [_flat_day(10, start + dt.timedelta(days=i)) for i in range(5)]

    special_date = start + dt.timedelta(days=5)

    # site 1: pacing HOT — sold out, on_hand undersupplied vs true demand.
    hot_hours = {7: 10, 8: 15, 9: 20, 10: 25, 11: 18, 12: 15, 13: 12, 14: 12, 15: 6, 16: 3}
    hot_day = IntradayDayRecord(date=special_date, hourly_counts=hot_hours, waste=0,
                                 sold_out=True)  # sum = 138 = on_hand, all baked units sold

    # site 2: pacing COLD — clear surplus, most of it never sells.
    cold_hours = {7: 3, 8: 4, 9: 4, 10: 4, 11: 8, 12: 7, 13: 6, 14: 5, 15: 4}
    cold_day = IntradayDayRecord(date=special_date, hourly_counts=cold_hours, waste=93,
                                  sold_out=False)  # sum = 45 sold, 93 wasted (on_hand 138)

    # site 3: balanced — sold_so_far tracks the learned pace exactly, so hold.
    balanced_hours = {7: 10, 8: 10, 9: 10, 10: 10, 11: 10, 12: 10, 13: 10, 14: 10,
                       15: 10, 16: 10, 17: 10, 18: 10, 19: 10}  # flat, same shape as history
    balanced_day = IntradayDayRecord(date=special_date, hourly_counts=balanced_hours,
                                      waste=0, sold_out=False)  # sum = production = 130

    series = {
        (product.name, 1): prior_days() + [hot_day],
        (product.name, 2): prior_days() + [cold_day],
        (product.name, 3): prior_days() + [balanced_day],
    }
    return series, products


def main() -> None:
    series, products = load_from_db()
    source = "seeded demo DB (app.models sale_event)"
    if not series:
        series, products = _synthetic_series()
        source = "self-contained synthetic scenario (no seeded DB data found)"

    result = run_intraday_backtest(series, products)

    print("=== ObradorIQ intraday backtest — the 11:00 check-in ===")
    print(f"Data source: {source}")
    print(f"Decision hour: {DECISION_HOUR:02d}:00\n")
    print(f"Evaluated {result.days_evaluated} site-product-days")
    print(f"Actionable signals (bake_more / move / markdown): {result.actionable_signals}\n")
    print(f"{'action':<12}{'signals':>10}{'eur recovered':>16}")
    for action, (n, eur) in sorted(result.by_action.items()):
        print(f"{action:<12}{n:>10}{eur:>16.2f}")
    print(f"\nDo-nothing baseline: €{result.baseline_eur_recovered:.2f}")
    print(
        f"HEADLINE — € recovered by an 11:00 check-in across the chain: "
        f"€{result.total_eur_recovered:.2f}"
    )


if __name__ == "__main__":
    main()
