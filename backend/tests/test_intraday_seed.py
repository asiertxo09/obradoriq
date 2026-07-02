"""Intraday seed backfill: seed() populates minute-level SaleEvent rows.

The daily CSV import creates no sale_event rows, so backfill_sale_events()
splits each day's aggregate quantity_sold into individual timestamped events.
"""
from __future__ import annotations

from collections import defaultdict

import pytest

from app.models import SaleEvent, SalesRecord, SessionLocal, init_db
from app.seed import backfill_sale_events, seed


@pytest.fixture(scope="module")
def seeded():
    init_db()
    # force a clean canonical seed (other suites may have replaced the demo bakery)
    info = seed(force=True)
    assert info["status"] == "seeded"
    return info


def test_seed_returns_sale_events_inserted(seeded):
    assert "sale_events_inserted" in seeded
    assert seeded["sale_events_inserted"] > 0
    # backward-compatible: original keys still present
    assert seeded["status"] == "seeded"
    assert "sales_inserted" in seeded and "waste_inserted" in seeded


def test_sale_events_exist_for_demo_bakery(seeded):
    db = SessionLocal()
    try:
        count = db.query(SaleEvent).count()
        assert count > 0
    finally:
        db.close()


def test_sale_events_within_opening_hours(seeded):
    db = SessionLocal()
    try:
        events = db.query(SaleEvent).all()
        assert events
        for ev in events:
            assert 7 <= ev.ts.hour <= 19, f"event at hour {ev.ts.hour} outside 07..19"
            assert ev.quantity >= 1
            assert ev.unit_price > 0
    finally:
        db.close()


def test_event_quantities_match_daily_totals(seeded):
    """Per (product, site, day) the summed event quantity equals that day's sold."""
    db = SessionLocal()
    try:
        # Sum sale_event quantities per (product, site, date)
        event_totals: dict = defaultdict(int)
        for ev in db.query(SaleEvent).all():
            key = (ev.product_id, ev.site_id, ev.ts.date())
            event_totals[key] += ev.quantity

        # Compare against SalesRecord aggregates for every backfilled day
        checked = 0
        for sr in db.query(SalesRecord).all():
            key = (sr.product_id, sr.site_id, sr.date)
            if key in event_totals:
                assert event_totals[key] == sr.quantity_sold, (
                    f"{key}: events={event_totals[key]} vs sold={sr.quantity_sold}"
                )
                checked += 1
        assert checked > 0, "expected at least one day of backfilled events to check"
    finally:
        db.close()


def test_backfill_is_deterministic(seeded):
    """Same seed_val on the same data yields the same event count."""
    db = SessionLocal()
    try:
        bakery_id = seeded["bakery_id"]
        # Clear existing events for a clean comparison, then run twice.
        db.query(SaleEvent).delete(synchronize_session=False)
        db.commit()
        n1 = backfill_sale_events(db, bakery_id, seed_val=7)

        db.query(SaleEvent).delete(synchronize_session=False)
        db.commit()
        n2 = backfill_sale_events(db, bakery_id, seed_val=7)

        assert n1 == n2
        assert n1 > 0
    finally:
        db.close()
