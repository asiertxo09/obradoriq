"""Seed the demo bakery chain from data/*.csv. Idempotent.

Run: python -m app.seed   (used locally, in tests, and as the Render first-deploy step)
"""
from __future__ import annotations

import csv
import os

from app.core.security import hash_password
from app.data_hub.ingest import import_sales, import_waste
from app.models import Bakery, Product, SessionLocal, Site, User, init_db

DEMO_EMAIL = "owner@obradoriq.demo"
DEMO_PASSWORD = "bakery123"
DATA_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "data"))


def seed(data_dir: str = DATA_DIR) -> dict:
    init_db()
    db = SessionLocal()
    try:
        existing = db.query(Bakery).filter_by(name="Obrador Demo").first()
        if existing:
            return {"status": "already-seeded", "bakery_id": existing.id}

        bakery = Bakery(name="Obrador Demo", risk_preference="waste")
        db.add(bakery)
        db.flush()

        db.add(User(bakery_id=bakery.id, email=DEMO_EMAIL,
                    password_hash=hash_password(DEMO_PASSWORD), role="owner"))

        for row in csv.DictReader(open(os.path.join(data_dir, "sites.csv"))):
            db.add(Site(bakery_id=bakery.id, name=row["name"], location=row["location"]))
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


if __name__ == "__main__":
    print(seed())
