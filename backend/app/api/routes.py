"""All API routes. Every tenant-scoped query filters by the caller's bakery_id."""
from __future__ import annotations

import datetime as dt

from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.api.deps import current_bakery_id, get_current_user
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
    DecisionRequest,
    LoginRequest,
    ProductCreate,
    ProductOut,
    RegisterRequest,
    ReallocationOut,
    RecommendationOut,
    SiteCreate,
    SiteOut,
    TokenResponse,
    UploadResult,
    WasteEntry,
    WeeklySummary,
)
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


# ---- weekly summary ----
@router.get("/summary/weekly", response_model=WeeklySummary)
def get_weekly(week_end: dt.date, bakery_id: int = Depends(current_bakery_id),
               db: Session = Depends(get_db)):
    return weekly_summary(db, bakery_id, week_end)


# ---- helpers ----
def _assert_site(db: Session, bakery_id: int, site_id: int):
    site = db.get(Site, site_id)
    if not site or site.bakery_id != bakery_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "site not found")


def _assert_product(db: Session, bakery_id: int, product_id: int):
    product = db.get(Product, product_id)
    if not product or product.bakery_id != bakery_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "product not found")
