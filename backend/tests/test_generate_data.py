"""The full-dataset generator fills all tables, with minute-resolution sale events."""
from __future__ import annotations

from app.generate_data import generate
from app.models import (
    AuditLog,
    InventoryRecord,
    Reallocation,
    Recommendation,
    RecommendationDecision,
    SaleEvent,
    SalesRecord,
    SessionLocal,
    WasteRecord,
)


def test_generate_populates_all_tables(tmp_path):
    counts = generate(days=20, use_weather=False)  # offline + small for CI
    # exact counts come from the generator (other test suites also write to the shared DB)
    assert counts["sales_record"] == 20 * 2 * 6  # days x sites x products
    assert counts["inventory_record"] == 20 * 2 * 6
    assert counts["sale_event"] > 0
    assert counts["waste_record"] > 0

    db = SessionLocal()
    try:
        assert db.query(SaleEvent).count() > 0
        assert db.query(Recommendation).count() > 0
        assert db.query(RecommendationDecision).count() > 0
        assert db.query(AuditLog).count() > 0

        # sale events carry minute-resolution timestamps within opening hours
        ev = db.query(SaleEvent).first()
        assert 7 <= ev.ts.hour < 20
        assert ev.quantity >= 1
    finally:
        db.close()
