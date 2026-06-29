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
