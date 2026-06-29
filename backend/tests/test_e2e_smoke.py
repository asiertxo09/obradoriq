"""End-to-end smoke: seed the demo chain, then walk the full HTTP path the demo uses."""
from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient

from app import main as app_main
from app.main import app
from app.seed import DEMO_EMAIL, DEMO_PASSWORD, seed

client = TestClient(app)
DAILY = "2026-06-29"
WEEK_END = "2026-06-28"


@pytest.fixture(scope="module", autouse=True)
def _seed():
    seed()


def _token() -> str:
    r = client.post("/api/auth/login", json={"email": DEMO_EMAIL, "password": DEMO_PASSWORD})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


def test_full_demo_flow():
    h = {"Authorization": f"Bearer {_token()}"}

    sites = client.get("/api/sites", headers=h).json()
    assert {s["name"] for s in sites} == {"Centro", "Barrio"}

    recs = client.get(f"/api/recommendations/{DAILY}", headers=h).json()
    assert len(recs) == 12  # 6 products x 2 sites
    assert all(r["recommended_qty"] > 0 for r in recs)

    # accept one recommendation -> logged
    d = client.post(f"/api/recommendations/{recs[0]['id']}/decision",
                    json={"decision": "accepted", "final_qty": recs[0]["recommended_qty"]}, headers=h)
    assert d.status_code == 201

    reallocs = client.get(f"/api/recommendations/{DAILY}/reallocation", headers=h).json()
    almond = [r for r in reallocs if r["product_name"] == "Almond Croissant"]
    assert almond and almond[0]["eur_waste_avoided"] > 0

    weekly = client.get(f"/api/summary/weekly?week_end={WEEK_END}", headers=h).json()
    assert weekly["total_waste_eur"] > 0
    assert weekly["margins"]


@pytest.mark.skipif(
    not os.path.isdir(app_main._FRONTEND_DIST),
    reason="frontend not built (frontend/dist absent) — built only in the deploy image",
)
def test_frontend_is_served():
    # The built React app is mounted at / (frontend/dist must exist from `npm run build`).
    r = client.get("/")
    assert r.status_code == 200
    assert "<div id=\"root\">" in r.text
