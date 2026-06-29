"""Data Hub — validate and normalize per-site CSV uploads into the data model.

Bad rows are rejected with a clear message, never silently dropped. All writes are
scoped to one bakery (tenant); product/site names are resolved within that bakery.
"""
from __future__ import annotations

import csv
import datetime as dt
import io

from sqlalchemy.orm import Session

from app.models.entities import Product, SalesRecord, Site, WasteRecord
from app.schemas.schemas import UploadResult

SALES_COLUMNS = {"site", "product", "date", "quantity_sold"}
WASTE_COLUMNS = {"site", "product", "date", "quantity_wasted"}


def _maps(db: Session, bakery_id: int) -> tuple[dict, dict]:
    products = {p.name: p for p in db.query(Product).filter_by(bakery_id=bakery_id)}
    sites = {s.name: s.id for s in db.query(Site).filter_by(bakery_id=bakery_id)}
    return products, sites


def import_sales(db: Session, bakery_id: int, csv_text: str) -> UploadResult:
    products, sites = _maps(db, bakery_id)
    reader = csv.DictReader(io.StringIO(csv_text))
    if not reader.fieldnames or not SALES_COLUMNS.issubset(set(reader.fieldnames)):
        return UploadResult(inserted=0, rejected=0,
                            errors=[f"missing columns; need {sorted(SALES_COLUMNS)}"])

    inserted, errors = 0, []
    for i, row in enumerate(reader, start=2):  # row 1 is the header
        try:
            site_id = sites[row["site"].strip()]
            product = products[row["product"].strip()]
            date = dt.date.fromisoformat(row["date"].strip())
            qty = int(row["quantity_sold"])
            if qty < 0:
                raise ValueError("quantity_sold is negative")
            revenue = float(row["revenue"]) if row.get("revenue") else qty * product.price
            sold_out = str(row.get("sold_out", "")).strip().lower() in {"true", "1", "yes"}
            db.add(SalesRecord(product_id=product.id, site_id=site_id, date=date,
                               quantity_sold=qty, revenue=revenue, sold_out=sold_out))
            inserted += 1
        except KeyError as e:
            errors.append(f"row {i}: unknown {e}")
        except ValueError as e:
            errors.append(f"row {i}: {e}")
    db.commit()
    return UploadResult(inserted=inserted, rejected=len(errors), errors=errors[:50])


def import_waste(db: Session, bakery_id: int, csv_text: str) -> UploadResult:
    products, sites = _maps(db, bakery_id)
    reader = csv.DictReader(io.StringIO(csv_text))
    if not reader.fieldnames or not WASTE_COLUMNS.issubset(set(reader.fieldnames)):
        return UploadResult(inserted=0, rejected=0,
                            errors=[f"missing columns; need {sorted(WASTE_COLUMNS)}"])

    inserted, errors = 0, []
    for i, row in enumerate(reader, start=2):
        try:
            site_id = sites[row["site"].strip()]
            product = products[row["product"].strip()]
            date = dt.date.fromisoformat(row["date"].strip())
            qty = int(row["quantity_wasted"])
            if qty < 0:
                raise ValueError("quantity_wasted is negative")
            db.add(WasteRecord(product_id=product.id, site_id=site_id, date=date,
                               quantity_wasted=qty))
            inserted += 1
        except KeyError as e:
            errors.append(f"row {i}: unknown {e}")
        except ValueError as e:
            errors.append(f"row {i}: {e}")
    db.commit()
    return UploadResult(inserted=inserted, rejected=len(errors), errors=errors[:50])
