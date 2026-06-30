"""Seed the demo bakery chain from data/*.csv. Idempotent.

Run: python -m app.seed   (used locally, in tests, and as the Render first-deploy step)
"""
from __future__ import annotations

import csv
import os

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
        return {
            "status": "seeded", "bakery_id": bakery.id,
            "login": {"email": DEMO_EMAIL, "password": DEMO_PASSWORD},
            "sales_inserted": s.inserted, "waste_inserted": w.inserted,
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


if __name__ == "__main__":
    import sys

    print(seed(force="--force" in sys.argv))
