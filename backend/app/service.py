"""Service layer — assembles DB data, runs the recommender core, persists results.

This is the seam between Track A (data) and Track B (the pure recommender). It keeps
the recommender pure: it does the querying, hands plain values to the core, and writes
the grounded outputs back.
"""
from __future__ import annotations

import datetime as dt
from collections import defaultdict
from dataclasses import replace

from sqlalchemy.orm import Session

from app.llm import agents
from app.models.entities import (
    Bakery,
    Product,
    Reallocation,
    Recommendation,
    SalesRecord,
    Site,
    WasteRecord,
)
from app.recommender.forecast import forecast
from app.recommender.production import recommend_production
from app.recommender.reallocation import reallocate_across_sites
from app.recommender.types import ProductInfo, SaleObservation, SiteState
from app.schemas.schemas import (
    ProductMargin,
    ReallocationOut,
    RecommendationOut,
    WeeklySummary,
)

RECENT_WINDOW = 14


def _product_info(p: Product) -> ProductInfo:
    return ProductInfo(product_id=p.id, name=p.name, batch_size=p.batch_size,
                       price=p.price, ingredient_cost=p.ingredient_cost)


def _history(db: Session, product_id: int, site_id: int, before: dt.date) -> list[SaleObservation]:
    rows = (db.query(SalesRecord)
            .filter(SalesRecord.product_id == product_id, SalesRecord.site_id == site_id,
                    SalesRecord.date < before)
            .order_by(SalesRecord.date).all())
    return [SaleObservation(r.date, r.quantity_sold, r.sold_out,
                            rainy=(r.precip_mm or 0) >= 2.0, holiday=bool(r.is_holiday))
            for r in rows]


def _recent_stats(db: Session, product_id: int, site_id: int, before: dt.date):
    """Recent waste-rate, sold-out rate, and average daily production for a (product, site)."""
    since = before - dt.timedelta(days=RECENT_WINDOW)
    sales = (db.query(SalesRecord)
             .filter(SalesRecord.product_id == product_id, SalesRecord.site_id == site_id,
                     SalesRecord.date >= since, SalesRecord.date < before).all())
    waste = (db.query(WasteRecord)
             .filter(WasteRecord.product_id == product_id, WasteRecord.site_id == site_id,
                     WasteRecord.date >= since, WasteRecord.date < before).all())
    waste_by_day = defaultdict(int)
    for w in waste:
        waste_by_day[w.date] += w.quantity_wasted
    total_sold = sum(s.quantity_sold for s in sales)
    total_waste = sum(waste_by_day.values())
    total_prod = total_sold + total_waste
    n = len(sales) or 1
    waste_rate = total_waste / total_prod if total_prod else 0.0
    sold_out_rate = sum(1 for s in sales if s.sold_out) / n
    avg_production = total_prod / n
    return waste_rate, sold_out_rate, avg_production


def generate_recommendations(db: Session, bakery_id: int, target_date: dt.date,
                             persist: bool = True,
                             demand_adjustment_pct: float = 0.0,
                             rainy: bool = False) -> list[RecommendationOut]:
    """demand_adjustment_pct: an explicit, owner-attributable nudge to forecast demand
    (e.g. +30 for a festival the model can't know about). It is surfaced in the reason,
    never applied silently — the agent sets it from the owner's stated context.
    rainy: whether the target day is forecast rainy (the owner/agent supplies this).
    Holiday is detected automatically from the calendar."""
    from app.data_hub.calendar import is_holiday

    products = db.query(Product).filter_by(bakery_id=bakery_id).all()
    sites = db.query(Site).filter_by(bakery_id=bakery_id).all()
    risk = db.get(Bakery, bakery_id).risk_preference
    factor = 1.0 + demand_adjustment_pct / 100.0
    holiday = is_holiday(target_date)

    out: list[RecommendationOut] = []
    for p in products:
        pinfo = _product_info(p)
        for s in sites:
            hist = _history(db, p.id, s.id, target_date)
            if not hist:
                continue
            f = forecast(p.id, s.id, target_date, hist,
                         target_rainy=rainy, target_holiday=holiday)
            if factor != 1.0:
                f = replace(f, expected_demand=round(f.expected_demand * factor, 1),
                            sigma=round(f.sigma * factor, 2))
            waste_rate, sold_out_rate, _ = _recent_stats(db, p.id, s.id, target_date)
            rec = recommend_production(f, pinfo, waste_rate,
                                       sold_out_recently=sold_out_rate > 0,
                                       risk_preference=risk)
            reason = agents.phrase_recommendation(rec, p.name)
            if demand_adjustment_pct:
                reason += (f" (Adjusted {demand_adjustment_pct:+.0f}% for the context "
                           f"you mentioned.)")
            row = RecommendationOut(
                product_id=p.id, product_name=p.name, site_id=s.id,
                target_date=target_date, forecast_qty=rec.forecast_qty,
                recommended_qty=rec.recommended_qty, confidence=rec.confidence,
                predicted_waste_eur=rec.predicted_waste_eur, reason=reason)
            if persist:
                db.add(Recommendation(
                    product_id=p.id, site_id=s.id, target_date=target_date,
                    forecast_qty=rec.forecast_qty, recommended_qty=rec.recommended_qty,
                    confidence=rec.confidence, predicted_waste_eur=rec.predicted_waste_eur,
                    reason=reason))
            out.append(row)
    if persist:
        db.commit()
        # backfill ids for the rows we just stored
        stored = {(r.product_id, r.site_id): r.id for r in
                  db.query(Recommendation).filter_by(target_date=target_date)}
        for row in out:
            row.id = stored.get((row.product_id, row.site_id))
    return out


def draft_production_sheet(db: Session, bakery_id: int, target_date: dt.date,
                           demand_adjustment_pct: float = 0.0, rainy: bool = False) -> dict:
    """Aggregate per-site recommendations into a chain production sheet + the estimated
    ingredient spend — a draft the owner approves (the 'take action' output)."""
    recs = generate_recommendations(db, bakery_id, target_date, persist=False,
                                    demand_adjustment_pct=demand_adjustment_pct, rainy=rainy)
    products = {p.id: p for p in db.query(Product).filter_by(bakery_id=bakery_id)}
    sites = {s.id: s.name for s in db.query(Site).filter_by(bakery_id=bakery_id)}

    lines: dict[str, dict] = {}
    spend = 0.0
    for r in recs:
        line = lines.setdefault(r.product_name, {"product": r.product_name,
                                                 "total_qty": 0, "by_site": {}})
        line["total_qty"] += r.recommended_qty
        line["by_site"][sites[r.site_id]] = r.recommended_qty
        spend += r.recommended_qty * products[r.product_id].ingredient_cost

    return {
        "target_date": target_date.isoformat(),
        "lines": sorted(lines.values(), key=lambda x: x["total_qty"], reverse=True),
        "estimated_ingredient_spend_eur": round(spend, 2),
    }


def generate_reallocations(db: Session, bakery_id: int, target_date: dt.date) -> list[ReallocationOut]:
    products = db.query(Product).filter_by(bakery_id=bakery_id).all()
    sites = db.query(Site).filter_by(bakery_id=bakery_id).all()
    site_name = {s.id: s.name for s in sites}

    out: list[ReallocationOut] = []
    for p in products:
        pinfo = _product_info(p)
        states: list[SiteState] = []
        for s in sites:
            hist = _history(db, p.id, s.id, target_date)
            if not hist:
                continue
            f = forecast(p.id, s.id, target_date, hist)
            _, sold_out_rate, avg_prod = _recent_stats(db, p.id, s.id, target_date)
            states.append(SiteState(site_id=s.id, forecast_demand=f.expected_demand,
                                    planned_production=avg_prod, sold_out_rate=sold_out_rate,
                                    confidence=f.confidence))
        for r in reallocate_across_sites(pinfo, target_date, states):
            text = agents.justify_reallocation(r, p.name, site_name[r.from_site_id],
                                                site_name[r.to_site_id])
            out.append(ReallocationOut(
                product_id=p.id, product_name=p.name, target_date=target_date,
                from_site_id=r.from_site_id, to_site_id=r.to_site_id, quantity=r.quantity,
                eur_waste_avoided=r.eur_waste_avoided, justification=text))
    return out


def weekly_summary(db: Session, bakery_id: int, week_end: dt.date) -> WeeklySummary:
    week_start = week_end - dt.timedelta(days=6)
    products = db.query(Product).filter_by(bakery_id=bakery_id).all()
    pid = {p.id: p for p in products}
    site_ids = [s.id for s in db.query(Site).filter_by(bakery_id=bakery_id)]

    sales = (db.query(SalesRecord).filter(SalesRecord.site_id.in_(site_ids),
             SalesRecord.date >= week_start, SalesRecord.date <= week_end).all())
    waste = (db.query(WasteRecord).filter(WasteRecord.site_id.in_(site_ids),
             WasteRecord.date >= week_start, WasteRecord.date <= week_end).all())

    sold_units = defaultdict(int); revenue = defaultdict(float)
    for s in sales:
        sold_units[s.product_id] += s.quantity_sold; revenue[s.product_id] += s.revenue
    waste_units = defaultdict(int)
    for w in waste:
        waste_units[w.product_id] += w.quantity_wasted

    margins, total_waste_units, total_waste_eur = [], 0, 0.0
    for product_id, p in pid.items():
        wu = waste_units.get(product_id, 0)
        su = sold_units.get(product_id, 0)
        cost = p.ingredient_cost or round(p.price * 0.35, 2)
        total_waste_units += wu
        total_waste_eur += wu * cost
        naive = ((p.price - cost) / p.price * 100) if p.price else 0.0
        produced = su + wu
        # True margin: spread total production cost over only the units actually sold.
        true = (((su * p.price) - (produced * cost)) / (su * p.price) * 100) if su and p.price else 0.0
        margins.append(ProductMargin(
            product_id=product_id, product_name=p.name,
            naive_margin_pct=round(naive, 1), true_margin_pct=round(true, 1),
            waste_units=wu, waste_eur=round(wu * cost, 2)))

    margins.sort(key=lambda m: m.waste_eur, reverse=True)
    return WeeklySummary(
        week_start=week_start, week_end=week_end,
        total_waste_units=total_waste_units, total_waste_eur=round(total_waste_eur, 2),
        eur_avoided_estimate=round(total_waste_eur * 0.28, 2),  # backtest-derived rate
        margins=margins)
