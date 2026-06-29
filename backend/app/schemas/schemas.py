"""Pydantic request/response contracts for the API."""
from __future__ import annotations

import datetime as dt

from pydantic import BaseModel, ConfigDict, EmailStr, Field


# ---- auth ----
class RegisterRequest(BaseModel):
    bakery_name: str
    email: EmailStr
    password: str = Field(min_length=8)
    risk_preference: str = "waste"


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


# ---- sites & products ----
class SiteCreate(BaseModel):
    name: str
    location: str = ""


class SiteOut(BaseModel):
    id: int
    name: str
    location: str

    model_config = ConfigDict(from_attributes=True)


class ProductCreate(BaseModel):
    name: str
    category: str = ""
    price: float = 0.0
    ingredient_cost: float = 0.0
    batch_size: int = 1


class ProductOut(BaseModel):
    id: int
    name: str
    category: str
    price: float
    ingredient_cost: float
    batch_size: int

    model_config = ConfigDict(from_attributes=True)


# ---- ingestion ----
class UploadResult(BaseModel):
    inserted: int
    rejected: int
    errors: list[str] = []


class WasteEntry(BaseModel):
    product_id: int
    site_id: int
    date: dt.date
    quantity_wasted: int = Field(ge=0)


# ---- recommendations ----
class RecommendationOut(BaseModel):
    id: int | None = None
    product_id: int
    product_name: str = ""
    site_id: int
    target_date: dt.date
    forecast_qty: float
    recommended_qty: int
    confidence: str
    predicted_waste_eur: float
    reason: str

    model_config = ConfigDict(from_attributes=True)


class ReallocationOut(BaseModel):
    product_id: int
    product_name: str = ""
    target_date: dt.date
    from_site_id: int
    to_site_id: int
    quantity: int
    eur_waste_avoided: float
    justification: str


class DecisionRequest(BaseModel):
    decision: str  # accepted | edited | rejected | deferred
    final_qty: int | None = None
    note: str = ""


# ---- weekly summary ----
class ProductMargin(BaseModel):
    product_id: int
    product_name: str
    naive_margin_pct: float
    true_margin_pct: float  # after waste
    waste_units: int
    waste_eur: float


class WeeklySummary(BaseModel):
    week_start: dt.date
    week_end: dt.date
    total_waste_units: int
    total_waste_eur: float
    eur_avoided_estimate: float
    margins: list[ProductMargin]
