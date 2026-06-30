"""Populate ALL tables with ~1 year of synthetic data — sales timestamped to the minute.

A bakery doesn't transact every clock-minute, so "every minute" means individual sales are
recorded at minute resolution during opening hours (07:00–20:00), following realistic
weekday / intraday / weather / holiday patterns. Daily aggregates (sales_record, waste,
inventory) are derived for the forecaster, and recommendation/decision/reallocation/audit
rows are seeded too.

Run locally / against a DB:
    python -m app.generate_data --days 365
    python -m app.generate_data --days 30 --no-weather   # offline, quick

Note: a full year is ~130k+ sale_event rows. It is NOT run on startup (too heavy for the
free tier). Generate it deliberately against your DATABASE_URL.
"""
from __future__ import annotations

import argparse
import datetime as dt
import random

from app.core.security import hash_password
from app.data_hub.calendar import is_holiday
from app.models import (
    AuditLog,
    Bakery,
    InventoryRecord,
    Product,
    Reallocation,
    Recommendation,
    RecommendationDecision,
    SaleEvent,
    SalesRecord,
    SessionLocal,
    Site,
    User,
    WasteRecord,
    init_db,
)
from app.seed import DEMO_EMAIL, DEMO_PASSWORD, _wipe_bakery

SITES = [
    {"name": "Centro", "location": "Gran Vía 28, Madrid", "latitude": 40.4203,
     "longitude": -3.7058, "demand": 1.30},
    {"name": "Barrio", "location": "Calle de Bravo Murillo 110, Madrid", "latitude": 40.4470,
     "longitude": -3.7030, "demand": 0.80},
]
PRODUCTS = [
    {"name": "Croissant", "category": "Viennoiserie", "price": 1.80, "ingredient_cost": 0.55,
     "batch_size": 6, "base": 60, "weekday": [1.0, 1.0, 1.0, 1.05, 1.2, 1.5, 1.4]},
    {"name": "Pain au Chocolat", "category": "Viennoiserie", "price": 2.10, "ingredient_cost": 0.70,
     "batch_size": 6, "base": 45, "weekday": [1.0, 1.0, 1.0, 1.05, 1.25, 1.5, 1.4]},
    {"name": "Baguette", "category": "Bread", "price": 1.20, "ingredient_cost": 0.30,
     "batch_size": 10, "base": 80, "weekday": [1.1, 1.05, 1.05, 1.1, 1.3, 1.4, 1.2]},
    {"name": "Sourdough", "category": "Bread", "price": 4.50, "ingredient_cost": 1.10,
     "batch_size": 4, "base": 24, "weekday": [0.9, 0.9, 1.0, 1.0, 1.2, 1.5, 1.3]},
    {"name": "Cinnamon Roll", "category": "Pastry", "price": 2.80, "ingredient_cost": 0.85,
     "batch_size": 6, "base": 30, "weekday": [0.8, 0.85, 0.9, 1.0, 1.2, 1.6, 1.5]},
    {"name": "Almond Croissant", "category": "Viennoiserie", "price": 2.60, "ingredient_cost": 0.95,
     "batch_size": 6, "base": 28, "weekday": [0.9, 0.9, 1.0, 1.05, 1.2, 1.5, 1.4]},
]
HABITUAL = {("Centro", "Almond Croissant"): 0.80, ("Barrio", "Almond Croissant"): 1.85}
DEFAULT_HABITUAL = 1.15
RAIN_EFFECT, HOLIDAY_EFFECT, RAIN_MM = 0.82, 1.35, 2.0
OPEN, CLOSE = 7, 20
# Relative footfall by hour (07..19): morning rush, lunch bump, quiet afternoon.
HOURLY = {7: 0.6, 8: 1.5, 9: 1.7, 10: 1.2, 11: 0.9, 12: 0.8, 13: 1.0,
          14: 0.9, 15: 0.7, 16: 0.7, 17: 0.9, 18: 1.0, 19: 0.6}
_HOURS = list(HOURLY)
_HWEIGHTS = list(HOURLY.values())


def _round_batch(x, b):
    return max(b, int(round(x / b)) * b)


def _precip(sites, start, end, use_weather):
    out = {}
    for s in sites:
        days = {}
        if use_weather:
            from app.data_hub.weather import fetch_daily_precip
            days = fetch_daily_precip(s["latitude"], s["longitude"], start, end)
        if not days:
            days = {start + dt.timedelta(days=i):
                    (round(random.uniform(2, 16), 1) if random.random() < 0.3 else 0.0)
                    for i in range((end - start).days + 1)}
        out[s["name"]] = days
    return out


def generate(days: int = 365, use_weather: bool = False, seed: int = 7) -> dict:
    random.seed(seed)
    init_db()
    db = SessionLocal()
    try:
        existing = db.query(Bakery).filter_by(name="Obrador Demo").first()
        if existing:
            _wipe_bakery(db, existing.id)

        bakery = Bakery(name="Obrador Demo", risk_preference="waste")
        db.add(bakery); db.flush()
        db.add(User(bakery_id=bakery.id, email=DEMO_EMAIL,
                    password_hash=hash_password(DEMO_PASSWORD), role="owner"))
        sites = []
        for s in SITES:
            site = Site(bakery_id=bakery.id, name=s["name"], location=s["location"],
                        latitude=s["latitude"], longitude=s["longitude"])
            db.add(site); db.flush()
            sites.append((site, s))
        products = []
        for p in PRODUCTS:
            prod = Product(bakery_id=bakery.id, name=p["name"], category=p["category"],
                           price=p["price"], ingredient_cost=p["ingredient_cost"],
                           batch_size=p["batch_size"])
            db.add(prod); db.flush()
            products.append((prod, p))
        db.commit()

        end = dt.date.today() - dt.timedelta(days=1)
        start = end - dt.timedelta(days=days - 1)
        precip = _precip(SITES, start, end, use_weather)

        events: list[dict] = []
        n_sales = n_waste = n_inv = n_events = 0
        for site, scfg in sites:
            for prod, pcfg in products:
                mean = pcfg["base"] * scfg["demand"]
                factor = HABITUAL.get((scfg["name"], pcfg["name"]), DEFAULT_HABITUAL)
                production = _round_batch(mean * factor, pcfg["batch_size"])
                for i in range(days):
                    day = start + dt.timedelta(days=i)
                    mm = precip[scfg["name"]].get(day, 0.0)
                    rainy, holiday = mm >= RAIN_MM, is_holiday(day)
                    trend = 1.0 + 0.0006 * i
                    noise = random.gauss(1.0, 0.12)
                    demand = max(0, int(round(
                        mean * pcfg["weekday"][day.weekday()] * trend * noise
                        * (RAIN_EFFECT if rainy else 1.0) * (HOLIDAY_EFFECT if holiday else 1.0))))
                    sold = min(demand, production)
                    waste = max(0, production - demand)
                    db.add(SalesRecord(product_id=prod.id, site_id=site.id, date=day,
                                       quantity_sold=sold, revenue=round(sold * pcfg["price"], 2),
                                       sold_out=demand > production, precip_mm=mm, is_holiday=holiday))
                    n_sales += 1
                    if waste:
                        db.add(WasteRecord(product_id=prod.id, site_id=site.id, date=day,
                                           quantity_wasted=waste)); n_waste += 1
                    db.add(InventoryRecord(product_id=prod.id, site_id=site.id, date=day,
                                           quantity_available=production)); n_inv += 1
                    # minute-stamped transactions until the day's units are sold
                    remaining = sold
                    while remaining > 0:
                        hour = random.choices(_HOURS, weights=_HWEIGHTS)[0]
                        qty = min(remaining, random.choice([1, 1, 1, 2, 2, 3]))
                        events.append({
                            "product_id": prod.id, "site_id": site.id, "quantity": qty,
                            "unit_price": pcfg["price"],
                            "ts": dt.datetime(day.year, day.month, day.day, hour,
                                              random.randint(0, 59), random.randint(0, 59))})
                        remaining -= qty
                        n_events += 1
                    if len(events) >= 5000:
                        db.bulk_insert_mappings(SaleEvent, events); events.clear()
            db.commit()
        if events:
            db.bulk_insert_mappings(SaleEvent, events); events.clear()
        db.commit()

        _seed_decisions_and_audit(db, bakery.id, end)
        counts = {"sales_record": n_sales, "waste_record": n_waste,
                  "inventory_record": n_inv, "sale_event": n_events,
                  "days": days, "range": f"{start}..{end}"}
        print("generated:", counts)
        return counts
    finally:
        db.close()


def _seed_decisions_and_audit(db, bakery_id: int, end: dt.date) -> None:
    """Fill recommendation / decision / reallocation / audit tables for recent days."""
    from app.service import generate_reallocations, generate_recommendations

    for d in range(7):
        day = end + dt.timedelta(days=1 - d)  # tomorrow + recent days
        recs = generate_recommendations(db, bakery_id, day, persist=True)
        stored = db.query(Recommendation).filter_by(target_date=day).all()
        for r in stored[:6]:
            choice = random.choice(["accepted", "accepted", "edited", "rejected", "deferred"])
            db.add(RecommendationDecision(
                recommendation_id=r.id, decision=choice,
                final_qty=r.recommended_qty if choice != "edited" else r.recommended_qty - r.id % 3,
                note=""))
        for rr in generate_reallocations(db, bakery_id, day):
            db.add(Reallocation(bakery_id=bakery_id, product_id=rr.product_id, target_date=day,
                                from_site_id=rr.from_site_id, to_site_id=rr.to_site_id,
                                quantity=rr.quantity, eur_waste_avoided=rr.eur_waste_avoided,
                                justification=rr.justification))
        db.add(AuditLog(bakery_id=bakery_id, event="daily_plan", model="recommender",
                        payload_summary=f"generated {len(recs)} recommendations for {day}"))
    db.commit()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=365)
    ap.add_argument("--no-weather", action="store_true", help="skip Open-Meteo (offline)")
    args = ap.parse_args()
    generate(days=args.days, use_weather=not args.no_weather)
