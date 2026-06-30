"""All API routes. Every tenant-scoped query filters by the caller's bakery_id."""
from __future__ import annotations

import datetime as dt

import hmac

from fastapi import APIRouter, Depends, Header, HTTPException, Query, UploadFile, status
from sqlalchemy.orm import Session

from app.api.deps import current_bakery_id, get_current_user
from app.core.config import get_settings
from app.core.security import create_access_token, hash_password, verify_password
from app.data_hub.ingest import import_sales, import_waste
from app.models import (
    Bakery,
    Product,
    Recommendation,
    RecommendationDecision,
    Site,
    User,
    WasteRecord,
    get_db,
)
from app.schemas.schemas import (
    ChatRequest,
    ChatResponse,
    DecisionRequest,
    IngestTextRequest,
    LoginRequest,
    ProductCreate,
    ProductOut,
    RegisterRequest,
    ReallocationOut,
    RecommendationOut,
    SimulateRequest,
    SimulateResult,
    SiteCreate,
    SiteOut,
    TokenResponse,
    UploadResult,
    WasteEntry,
    WeeklySummary,
)
from app.llm import orchestrator
from app.service import (
    generate_reallocations,
    generate_recommendations,
    weekly_summary,
)

router = APIRouter()


# ---- auth ----
@router.post("/auth/register", response_model=TokenResponse)
def register(body: RegisterRequest, db: Session = Depends(get_db)):
    if db.query(User).filter_by(email=body.email).first():
        raise HTTPException(status.HTTP_409_CONFLICT, "email already registered")
    bakery = Bakery(name=body.bakery_name, risk_preference=body.risk_preference)
    db.add(bakery)
    db.flush()
    user = User(bakery_id=bakery.id, email=body.email,
                password_hash=hash_password(body.password), role="owner")
    db.add(user)
    db.commit()
    return TokenResponse(access_token=create_access_token(user_id=user.id, bakery_id=bakery.id))


@router.post("/auth/login", response_model=TokenResponse)
def login(body: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter_by(email=body.email).first()
    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "bad credentials")
    return TokenResponse(access_token=create_access_token(user_id=user.id, bakery_id=user.bakery_id))


# ---- sites ----
@router.get("/sites", response_model=list[SiteOut])
def list_sites(bakery_id: int = Depends(current_bakery_id), db: Session = Depends(get_db)):
    return db.query(Site).filter_by(bakery_id=bakery_id).order_by(Site.id).all()


@router.post("/sites", response_model=SiteOut, status_code=201)
def add_site(body: SiteCreate, bakery_id: int = Depends(current_bakery_id),
             db: Session = Depends(get_db)):
    site = Site(bakery_id=bakery_id, name=body.name, location=body.location)
    db.add(site); db.commit()
    return site


# ---- products ----
@router.get("/products", response_model=list[ProductOut])
def list_products(bakery_id: int = Depends(current_bakery_id), db: Session = Depends(get_db)):
    return db.query(Product).filter_by(bakery_id=bakery_id).order_by(Product.id).all()


@router.post("/products", response_model=ProductOut, status_code=201)
def add_product(body: ProductCreate, bakery_id: int = Depends(current_bakery_id),
                db: Session = Depends(get_db)):
    product = Product(bakery_id=bakery_id, **body.model_dump())
    db.add(product); db.commit()
    return product


# ---- ingestion ----
@router.post("/uploads/sales", response_model=UploadResult)
async def upload_sales(file: UploadFile, bakery_id: int = Depends(current_bakery_id),
                       db: Session = Depends(get_db)):
    text = (await file.read()).decode("utf-8")
    return import_sales(db, bakery_id, text)


@router.post("/uploads/waste", response_model=UploadResult)
async def upload_waste(file: UploadFile, bakery_id: int = Depends(current_bakery_id),
                       db: Session = Depends(get_db)):
    text = (await file.read()).decode("utf-8")
    return import_waste(db, bakery_id, text)


@router.post("/waste", status_code=201)
def add_waste(body: WasteEntry, bakery_id: int = Depends(current_bakery_id),
              db: Session = Depends(get_db)):
    _assert_site(db, bakery_id, body.site_id)
    _assert_product(db, bakery_id, body.product_id)
    db.add(WasteRecord(product_id=body.product_id, site_id=body.site_id,
                       date=body.date, quantity_wasted=body.quantity_wasted))
    db.commit()
    return {"status": "ok"}


# ---- recommendations ----
@router.get("/recommendations/{target_date}", response_model=list[RecommendationOut])
def get_recommendations(target_date: dt.date, bakery_id: int = Depends(current_bakery_id),
                        db: Session = Depends(get_db)):
    return generate_recommendations(db, bakery_id, target_date, persist=True)


@router.get("/recommendations/{target_date}/reallocation", response_model=list[ReallocationOut])
def get_reallocations(target_date: dt.date, bakery_id: int = Depends(current_bakery_id),
                      db: Session = Depends(get_db)):
    return generate_reallocations(db, bakery_id, target_date)


@router.post("/recommendations/{rec_id}/decision", status_code=201)
def decide(rec_id: int, body: DecisionRequest, bakery_id: int = Depends(current_bakery_id),
           db: Session = Depends(get_db)):
    rec = db.get(Recommendation, rec_id)
    if not rec:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "recommendation not found")
    # Tenant guard: the recommendation's site must belong to the caller's bakery.
    site = db.get(Site, rec.site_id)
    if not site or site.bakery_id != bakery_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "recommendation not found")
    if body.decision not in {"accepted", "edited", "rejected", "deferred"}:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "invalid decision")
    db.add(RecommendationDecision(recommendation_id=rec_id, decision=body.decision,
                                  final_qty=body.final_qty, note=body.note))
    db.commit()
    return {"status": "logged"}


# ---- agent chat ----
@router.post("/chat", response_model=ChatResponse)
def chat(body: ChatRequest, bakery_id: int = Depends(current_bakery_id),
         db: Session = Depends(get_db)):
    history = [{"role": m.role, "content": m.content} for m in body.history]
    out = orchestrator.chat(db, bakery_id, body.message, history)
    return ChatResponse(**out)


@router.post("/ingest/text", response_model=UploadResult)
def ingest_text(body: IngestTextRequest, bakery_id: int = Depends(current_bakery_id),
                db: Session = Depends(get_db)):
    fn = import_sales if body.kind == "sales" else import_waste
    return fn(db, bakery_id, body.csv_text)


# ---- weekly summary ----
@router.get("/summary/weekly", response_model=WeeklySummary)
def get_weekly(week_end: dt.date, bakery_id: int = Depends(current_bakery_id),
               db: Session = Depends(get_db)):
    return weekly_summary(db, bakery_id, week_end)


# ---- public demo endpoint (no auth) ----
@router.post("/simulate", response_model=SimulateResult)
def simulate(body: SimulateRequest) -> SimulateResult:
    """No-auth demo endpoint: run a real newsvendor recommendation from raw sales history."""
    import statistics

    from app.recommender.forecast import forecast as _forecast
    from app.recommender.newsvendor import critical_ratio, newsvendor_quantity
    from app.recommender.types import SaleObservation

    cost_per_unit = 1.20
    selling_price = 2.80

    today = dt.date.today()
    n = len(body.sales_history)
    history = [
        SaleObservation(
            date=today - dt.timedelta(days=n - i),
            quantity_sold=qty,
        )
        for i, qty in enumerate(body.sales_history)
    ]

    f = _forecast(
        product_id=0,
        site_id=0,
        target_date=today,
        history=history,
        target_rainy=False,
        target_holiday=False,
    )

    forecast_qty = f.expected_demand
    if body.rainy_tomorrow:
        forecast_qty = round(forecast_qty * 0.88, 1)

    cr = critical_ratio(selling_price, cost_per_unit, "waste")
    raw_qty = newsvendor_quantity(forecast_qty, f.sigma, cr)
    recommended_qty = max(1, round(raw_qty))

    predicted_waste_eur = round(max(0.0, recommended_qty - forecast_qty) * cost_per_unit, 2)

    reason = (
        "Rain expected tomorrow — forecast adjusted down 12%."
        if body.rainy_tomorrow
        else "Based on your recent sales history."
    )

    return SimulateResult(
        product_name=body.product_name,
        forecast_qty=forecast_qty,
        recommended_qty=recommended_qty,
        predicted_waste_eur=predicted_waste_eur,
        reason=reason,
    )


# ---- admin (token-guarded one-off) ----
@router.post("/admin/generate")
def admin_generate(
    days: int = Query(default=120, ge=1, le=400),
    weather: bool = Query(default=True),
    x_admin_token: str = Header(default=""),
):
    """Populate ALL tables with `days` of synthetic data (sales timestamped to the minute).
    Guarded by the ADMIN_TOKEN env var; runs synchronously (may take ~30-60s)."""
    settings = get_settings()
    if not settings.admin_token:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "admin endpoint disabled")
    if not hmac.compare_digest(x_admin_token, settings.admin_token):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "bad admin token")
    from app.generate_data import generate

    counts = generate(days=days, use_weather=weather)
    return {"status": "ok", **counts}


# ---- helpers ----
def _assert_site(db: Session, bakery_id: int, site_id: int):
    site = db.get(Site, site_id)
    if not site or site.bakery_id != bakery_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "site not found")


def _assert_product(db: Session, bakery_id: int, product_id: int):
    product = db.get(Product, product_id)
    if not product or product.bakery_id != bakery_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "product not found")
