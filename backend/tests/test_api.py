"""API + auth + tenant-isolation tests using FastAPI's TestClient."""
from __future__ import annotations

import datetime as dt

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models import init_db

client = TestClient(app)


@pytest.fixture(scope="module", autouse=True)
def _db():
    init_db()


def _register(email: str, bakery: str) -> str:
    r = client.post("/api/auth/register", json={
        "bakery_name": bakery, "email": email, "password": "bakery123"})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def test_health():
    assert client.get("/api/health").json() == {"status": "ok"}


def test_register_login_and_protected_route():
    token = _register("a@a.com", "Chain A")
    # login works too
    r = client.post("/api/auth/login", json={"email": "a@a.com", "password": "bakery123"})
    assert r.status_code == 200
    # protected route rejects anonymous
    assert client.get("/api/sites").status_code == 401
    # and accepts the token
    assert client.get("/api/sites", headers=_auth(token)).status_code == 200


def test_login_bad_password():
    _register("b@b.com", "Chain B")
    r = client.post("/api/auth/login", json={"email": "b@b.com", "password": "wrongpass"})
    assert r.status_code == 401


def test_tenant_isolation_on_decision():
    """A user from bakery B must not act on bakery A's recommendation."""
    token_a = _register("owner-a@x.com", "Alpha Bakers")
    token_b = _register("owner-b@x.com", "Beta Bakers")

    # Bakery A: two sites, one product, sales history -> a recommendation with an id.
    client.post("/api/sites", json={"name": "A1"}, headers=_auth(token_a))
    client.post("/api/products", json={"name": "Bun", "price": 2.0,
                "ingredient_cost": 0.5, "batch_size": 4}, headers=_auth(token_a))
    sites = client.get("/api/sites", headers=_auth(token_a)).json()
    prods = client.get("/api/products", headers=_auth(token_a)).json()
    sid, pid = sites[0]["id"], prods[0]["id"]
    rows = "site,product,date,quantity_sold,sold_out\n" + "\n".join(
        f"A1,Bun,{(dt.date(2026,1,1)+dt.timedelta(days=i)).isoformat()},20,false"
        for i in range(40))
    client.post("/api/uploads/sales", files={"file": ("s.csv", rows, "text/csv")},
                headers=_auth(token_a))
    recs = client.get("/api/recommendations/2026-02-15", headers=_auth(token_a)).json()
    assert recs and recs[0]["id"]
    rec_id = recs[0]["id"]

    # Bakery B tries to decide on A's recommendation -> 404 (not leaked).
    r = client.post(f"/api/recommendations/{rec_id}/decision",
                    json={"decision": "accepted"}, headers=_auth(token_b))
    assert r.status_code == 404

    # Owner A can.
    r = client.post(f"/api/recommendations/{rec_id}/decision",
                    json={"decision": "accepted", "final_qty": 20}, headers=_auth(token_a))
    assert r.status_code == 201


def test_chat_endpoint_returns_grounded_tool_result():
    token = _register("chat@x.com", "Chat Bakers")
    client.post("/api/sites", json={"name": "S1"}, headers=_auth(token))
    client.post("/api/products", json={"name": "Bun", "price": 2.0, "ingredient_cost": 0.5,
                "batch_size": 4}, headers=_auth(token))
    rows = "site,product,date,quantity_sold,sold_out\n" + "\n".join(
        f"S1,Bun,{(dt.date(2026,1,1)+dt.timedelta(days=i)).isoformat()},20,false"
        for i in range(40))
    client.post("/api/uploads/sales", files={"file": ("s.csv", rows, "text/csv")},
                headers=_auth(token))
    r = client.post("/api/chat", json={"message": "How much should I bake on 2026-02-15?"},
                    headers=_auth(token))
    assert r.status_code == 200
    body = r.json()
    assert body["reply"]
    assert body["tool_results"][0]["tool"] == "get_recommendations"


def test_upload_rejects_bad_rows():
    token = _register("c@c.com", "Chain C")
    client.post("/api/sites", json={"name": "C1"}, headers=_auth(token))
    client.post("/api/products", json={"name": "Loaf", "price": 3.0, "batch_size": 2},
                headers=_auth(token))
    bad = ("site,product,date,quantity_sold\n"
           "C1,Loaf,2026-01-01,10\n"
           "C1,Ghost,2026-01-02,5\n"        # unknown product
           "C1,Loaf,not-a-date,5\n")        # bad date
    r = client.post("/api/uploads/sales", files={"file": ("s.csv", bad, "text/csv")},
                    headers=_auth(token))
    body = r.json()
    assert body["inserted"] == 1
    assert body["rejected"] == 2
    assert len(body["errors"]) == 2


def test_reallocation_decision_and_tenant_isolation():
    """Approve/Dismiss on a reallocation logs a decision; another bakery can't act on it."""
    from app.models import SessionLocal
    from app.models.entities import Reallocation, User

    token_a = _register("realloc-a@x.com", "Realloc Alpha")
    token_b = _register("realloc-b@x.com", "Realloc Beta")
    site1 = client.post("/api/sites", json={"name": "A1"}, headers=_auth(token_a)).json()
    site2 = client.post("/api/sites", json={"name": "A2"}, headers=_auth(token_a)).json()
    prod = client.post("/api/products", json={"name": "Bun", "price": 2.0,
                       "ingredient_cost": 0.5, "batch_size": 4}, headers=_auth(token_a)).json()

    db = SessionLocal()
    try:
        bakery_id_a = db.query(User).filter_by(email="realloc-a@x.com").one().bakery_id
        row = Reallocation(bakery_id=bakery_id_a, product_id=prod["id"],
                           target_date=dt.date(2026, 1, 1), from_site_id=site1["id"],
                           to_site_id=site2["id"], quantity=5, eur_waste_avoided=4.5,
                           justification="test reallocation")
        db.add(row)
        db.commit()
        realloc_id = row.id
    finally:
        db.close()

    # Bakery B tries to decide on A's reallocation -> 404 (not leaked).
    r = client.post(f"/api/reallocations/{realloc_id}/decision",
                    json={"decision": "accepted"}, headers=_auth(token_b))
    assert r.status_code == 404

    # An invalid decision value is rejected.
    r = client.post(f"/api/reallocations/{realloc_id}/decision",
                    json={"decision": "bogus"}, headers=_auth(token_a))
    assert r.status_code == 422

    # Owner A can approve it.
    r = client.post(f"/api/reallocations/{realloc_id}/decision",
                    json={"decision": "accepted"}, headers=_auth(token_a))
    assert r.status_code == 201

    # Unknown reallocation id -> 404.
    r = client.post("/api/reallocations/999999/decision",
                    json={"decision": "dismissed"}, headers=_auth(token_a))
    assert r.status_code == 404


# ---- simulate (no-auth demo) ----

def test_simulate_page_served():
    """/simulate is a client-side route: it must serve the SPA, not 404."""
    from app.main import _FRONTEND_DIST
    import os
    if not os.path.isdir(_FRONTEND_DIST):
        pytest.skip("frontend/dist not built in this environment")
    r = client.get("/simulate")
    assert r.status_code == 200
    assert "text/html" in r.headers["content-type"]


def test_simulate_endpoint():
    payload = {
        "product_name": "Croissant",
        "sales_history": [20, 18, 22, 19, 21, 17, 20, 19, 22, 18, 21, 20, 19, 18],
        "rainy_tomorrow": False,
    }
    r = client.post("/api/simulate", json=payload)
    assert r.status_code == 200
    data = r.json()
    assert data["product_name"] == "Croissant"
    assert data["recommended_qty"] > 0
    assert data["forecast_qty"] > 0


def test_simulate_rainy_lower():
    history = [20, 18, 22, 19, 21, 17, 20, 19, 22, 18, 21, 20, 19, 18]
    dry = client.post("/api/simulate", json={"product_name": "X", "sales_history": history,
                                             "rainy_tomorrow": False}).json()
    rainy = client.post("/api/simulate", json={"product_name": "X", "sales_history": history,
                                               "rainy_tomorrow": True}).json()
    assert rainy["forecast_qty"] < dry["forecast_qty"]


def test_simulate_too_short():
    r = client.post("/api/simulate", json={"product_name": "X", "sales_history": [10, 20],
                                           "rainy_tomorrow": False})
    assert r.status_code == 422
