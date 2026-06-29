"""Integration: seed the demo chain, then run the service layer end to end."""
from __future__ import annotations

import datetime as dt

import pytest

from app.models import SessionLocal, init_db
from app.seed import seed
from app.service import generate_reallocations, generate_recommendations, weekly_summary

TARGET = dt.date(2026, 6, 29)  # day after the fixture's last day


@pytest.fixture(scope="module")
def seeded():
    init_db()
    info = seed()
    assert info["status"] in {"seeded", "already-seeded"}
    return info["bakery_id"]


def test_recommendations_generated_per_site(seeded):
    db = SessionLocal()
    try:
        recs = generate_recommendations(db, seeded, TARGET, persist=False)
        # 6 products x 2 sites
        assert len(recs) == 12
        for r in recs:
            assert r.recommended_qty > 0
            assert r.confidence in {"HIGH", "LOW"}
            assert str(r.recommended_qty) in r.reason or r.product_name in r.reason
    finally:
        db.close()


def test_reallocation_moves_almond_croissant_barrio_to_centro(seeded):
    db = SessionLocal()
    try:
        from app.models.entities import Site

        sites = {s.name: s.id for s in db.query(Site).filter_by(bakery_id=seeded)}
        reallocs = generate_reallocations(db, seeded, TARGET)
        almond = [r for r in reallocs if r.product_name == "Almond Croissant"]
        assert almond, "expected an Almond Croissant reallocation (the engineered story)"
        r = almond[0]
        assert r.from_site_id == sites["Barrio"]  # the over-producer
        assert r.to_site_id == sites["Centro"]    # the sell-out site
        assert r.eur_waste_avoided > 0
        assert "Barrio" in r.justification and "Centro" in r.justification
    finally:
        db.close()


def test_weekly_summary_has_true_margin(seeded):
    db = SessionLocal()
    try:
        summary = weekly_summary(db, seeded, dt.date(2026, 6, 28))
        assert summary.total_waste_units > 0
        assert summary.margins
        # True margin should be below naive margin where there is waste.
        almond = next(m for m in summary.margins if m.product_name == "Almond Croissant")
        assert almond.true_margin_pct < almond.naive_margin_pct
    finally:
        db.close()
