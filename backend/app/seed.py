"""Seed the demo bakery chain from data/*.csv. Idempotent.

Run: python -m app.seed   (used locally, in tests, and as the Render first-deploy step)
"""
from __future__ import annotations

import csv
import datetime as dt
import os
import random

from app.core.security import hash_password
from app.data_hub.ingest import import_sales, import_waste
from app.models import (
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

DEMO_EMAIL = "owner@obradoriq.demo"
DEMO_PASSWORD = "bakery123"
DATA_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "data"))

# Hourly footfall distribution (07..19): morning rush, lunch bump, quiet afternoon.
HOURLY = {7: 0.6, 8: 1.5, 9: 1.7, 10: 1.2, 11: 0.9, 12: 0.8, 13: 1.0,
          14: 0.9, 15: 0.7, 16: 0.7, 17: 0.9, 18: 1.0, 19: 0.6}
_HOURS = list(HOURLY)
_HWEIGHTS = list(HOURLY.values())


def backfill_sale_events(db, bakery_id: int, days: int = 30, seed_val: int = 7) -> int:
    """Populate intraday SaleEvent rows from daily SalesRecord aggregates.

    For the bakery's most recent `days` of SalesRecord rows (per product+site),
    split each day's quantity_sold into individual SaleEvent rows across opening
    hours 07..19 using realistic hourly footfall weights. Timestamps are
    randomized to the minute. Uses deterministic seeding for reproducibility.

    Args:
        db: SQLAlchemy session
        bakery_id: Bakery ID to backfill
        days: Number of recent days to backfill (default 30)
        seed_val: Random seed for determinism (default 7)

    Returns:
        Number of SaleEvent rows created
    """
    random.seed(seed_val)

    # Fetch products (needed for unit_price lookup)
    products = {p.id: p for p in db.query(Product).filter_by(bakery_id=bakery_id)}
    if not products:
        return 0

    # Get the most recent `days` of SalesRecord rows.
    # Strategy: get max date, then filter for dates in [max_date - days, max_date]
    max_date_row = db.query(SalesRecord).order_by(SalesRecord.date.desc()).first()
    if not max_date_row:
        return 0

    max_date = max_date_row.date
    start_date = max_date - dt.timedelta(days=days - 1)  # inclusive range

    # Fetch all SalesRecord rows in the date range for this bakery's products
    sales_records = db.query(SalesRecord).filter(
        SalesRecord.product_id.in_(products.keys()),
        SalesRecord.date >= start_date,
        SalesRecord.date <= max_date
    ).all()

    # Bulk insert events
    events = []
    n_events = 0
    for sr in sales_records:
        product = products[sr.product_id]
        remaining = sr.quantity_sold

        while remaining > 0:
            # Pick an hour according to footfall weights
            hour = random.choices(_HOURS, weights=_HWEIGHTS)[0]
            # Pick a quantity: [1, 1, 1, 2, 2, 3] distribution
            qty = min(remaining, random.choice([1, 1, 1, 2, 2, 3]))

            events.append({
                "product_id": sr.product_id,
                "site_id": sr.site_id,
                "quantity": qty,
                "unit_price": product.price,
                "ts": dt.datetime(sr.date.year, sr.date.month, sr.date.day, hour,
                                  random.randint(0, 59), random.randint(0, 59))
            })
            remaining -= qty
            n_events += 1

            # Bulk insert in batches to avoid memory bloat
            if len(events) >= 5000:
                db.bulk_insert_mappings(SaleEvent, events)
                events.clear()

    # Flush final batch
    if events:
        db.bulk_insert_mappings(SaleEvent, events)
        events.clear()

    db.commit()
    return n_events


def seed(data_dir: str = DATA_DIR, force: bool = False) -> dict:
    init_db()
    db = SessionLocal()
    try:
        existing = db.query(Bakery).filter_by(name="Obrador Demo").first()
        if existing and not force:
            return {"status": "already-seeded", "bakery_id": existing.id}
        if existing and force:
            # Wipe the demo chain so it re-seeds with the latest fixture (e.g. to backfill
            # the weather/holiday columns on an older deployment).
            _wipe_bakery(db, existing.id)

        bakery = Bakery(name="Obrador Demo", risk_preference="waste")
        db.add(bakery)
        db.flush()

        db.add(User(bakery_id=bakery.id, email=DEMO_EMAIL,
                    password_hash=hash_password(DEMO_PASSWORD), role="owner"))

        for row in csv.DictReader(open(os.path.join(data_dir, "sites.csv"))):
            db.add(Site(bakery_id=bakery.id, name=row["name"], location=row["location"],
                        latitude=float(row.get("latitude") or 0),
                        longitude=float(row.get("longitude") or 0)))
        for row in csv.DictReader(open(os.path.join(data_dir, "products.csv"))):
            db.add(Product(bakery_id=bakery.id, name=row["name"], category=row["category"],
                           price=float(row["price"]), ingredient_cost=float(row["ingredient_cost"]),
                           batch_size=int(row["batch_size"])))
        db.commit()

        sales_csv = open(os.path.join(data_dir, "sales.csv")).read()
        waste_csv = open(os.path.join(data_dir, "waste.csv")).read()
        s = import_sales(db, bakery.id, sales_csv)
        w = import_waste(db, bakery.id, waste_csv)
        # Backfill intraday sale_event rows so the demo chain has minute-level data
        # out-of-the-box (the daily CSV import populates none).
        sale_events = backfill_sale_events(db, bakery.id)
        return {
            "status": "seeded", "bakery_id": bakery.id,
            "login": {"email": DEMO_EMAIL, "password": DEMO_PASSWORD},
            "sales_inserted": s.inserted, "waste_inserted": w.inserted,
            "sale_events_inserted": sale_events,
        }
    finally:
        db.close()


def _wipe_bakery(db, bakery_id: int) -> None:
    """Delete all data for a bakery (demo reset). Order respects FKs."""
    site_ids = [s.id for s in db.query(Site).filter_by(bakery_id=bakery_id)]
    product_ids = [p.id for p in db.query(Product).filter_by(bakery_id=bakery_id)]
    rec_ids = [r.id for r in db.query(Recommendation).filter(
        Recommendation.site_id.in_(site_ids or [-1]))]
    db.query(RecommendationDecision).filter(
        RecommendationDecision.recommendation_id.in_(rec_ids or [-1])).delete(synchronize_session=False)
    for model in (Recommendation, Reallocation, SalesRecord, WasteRecord, InventoryRecord,
                  SaleEvent):
        col = model.site_id if hasattr(model, "site_id") else model.bakery_id
        ids = site_ids if hasattr(model, "site_id") else [bakery_id]
        db.query(model).filter(col.in_(ids or [-1])).delete(synchronize_session=False)
    db.query(Product).filter_by(bakery_id=bakery_id).delete(synchronize_session=False)
    db.query(Site).filter_by(bakery_id=bakery_id).delete(synchronize_session=False)
    db.query(User).filter_by(bakery_id=bakery_id).delete(synchronize_session=False)
    db.query(Bakery).filter_by(id=bakery_id).delete(synchronize_session=False)
    db.commit()
    # The bulk deletes ran with synchronize_session=False, so the wiped rows linger in the
    # session's identity map. Clear it before the caller re-inserts a Bakery with the same PK,
    # otherwise the flush warns about replacing an existing identity.
    db.expunge_all()


if __name__ == "__main__":
    import sys

    print(seed(force="--force" in sys.argv))
