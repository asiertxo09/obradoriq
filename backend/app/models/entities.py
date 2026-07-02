"""ORM entities. Multi-site is core: sales/waste/inventory carry a site_id.

Tenant model: a `Bakery` is the chain (the tenant). Every row traces back to a
bakery_id; every query is scoped to the authenticated user's bakery (see api/deps).
"""
from __future__ import annotations

import datetime as dt

from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class Bakery(Base):
    __tablename__ = "bakery"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    # Owner risk preference: "availability" (avoid stockouts) | "waste" (avoid leftovers)
    risk_preference: Mapped[str] = mapped_column(String(20), default="waste")
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, server_default=func.now())

    sites: Mapped[list["Site"]] = relationship(back_populates="bakery")
    products: Mapped[list["Product"]] = relationship(back_populates="bakery")


class Site(Base):
    __tablename__ = "site"
    id: Mapped[int] = mapped_column(primary_key=True)
    bakery_id: Mapped[int] = mapped_column(ForeignKey("bakery.id"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    location: Mapped[str] = mapped_column(String(200), default="")
    latitude: Mapped[float] = mapped_column(Float, default=0.0)
    longitude: Mapped[float] = mapped_column(Float, default=0.0)

    bakery: Mapped[Bakery] = relationship(back_populates="sites")


class User(Base):
    __tablename__ = "user"
    id: Mapped[int] = mapped_column(primary_key=True)
    bakery_id: Mapped[int] = mapped_column(ForeignKey("bakery.id"), index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(20), default="owner")
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, server_default=func.now())


class Product(Base):
    __tablename__ = "product"
    id: Mapped[int] = mapped_column(primary_key=True)
    bakery_id: Mapped[int] = mapped_column(ForeignKey("bakery.id"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    category: Mapped[str] = mapped_column(String(60), default="")
    price: Mapped[float] = mapped_column(Float, default=0.0)
    ingredient_cost: Mapped[float] = mapped_column(Float, default=0.0)
    batch_size: Mapped[int] = mapped_column(Integer, default=1)

    bakery: Mapped[Bakery] = relationship(back_populates="products")


class SalesRecord(Base):
    __tablename__ = "sales_record"
    id: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("product.id"), index=True)
    site_id: Mapped[int] = mapped_column(ForeignKey("site.id"), index=True)
    date: Mapped[dt.date] = mapped_column(Date, index=True)
    quantity_sold: Mapped[int] = mapped_column(Integer)
    revenue: Mapped[float] = mapped_column(Float, default=0.0)
    sold_out: Mapped[bool] = mapped_column(Boolean, default=False)
    # External signals (optional): the day's weather and whether it was a holiday.
    precip_mm: Mapped[float] = mapped_column(Float, default=0.0)
    is_holiday: Mapped[bool] = mapped_column(Boolean, default=False)


class SaleEvent(Base):
    """Transaction-level sale, timestamped to the minute (intraday detail)."""

    __tablename__ = "sale_event"
    id: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("product.id"), index=True)
    site_id: Mapped[int] = mapped_column(ForeignKey("site.id"), index=True)
    ts: Mapped[dt.datetime] = mapped_column(DateTime, index=True)
    quantity: Mapped[int] = mapped_column(Integer, default=1)
    unit_price: Mapped[float] = mapped_column(Float, default=0.0)


class WasteRecord(Base):
    __tablename__ = "waste_record"
    id: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("product.id"), index=True)
    site_id: Mapped[int] = mapped_column(ForeignKey("site.id"), index=True)
    date: Mapped[dt.date] = mapped_column(Date, index=True)
    quantity_wasted: Mapped[int] = mapped_column(Integer)


class InventoryRecord(Base):
    __tablename__ = "inventory_record"
    id: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("product.id"), index=True)
    site_id: Mapped[int] = mapped_column(ForeignKey("site.id"), index=True)
    date: Mapped[dt.date] = mapped_column(Date, index=True)
    quantity_available: Mapped[int] = mapped_column(Integer)


class Recommendation(Base):
    __tablename__ = "recommendation"
    id: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("product.id"), index=True)
    site_id: Mapped[int] = mapped_column(ForeignKey("site.id"), index=True)
    target_date: Mapped[dt.date] = mapped_column(Date, index=True)
    forecast_qty: Mapped[float] = mapped_column(Float)
    recommended_qty: Mapped[int] = mapped_column(Integer)
    confidence: Mapped[str] = mapped_column(String(10))  # HIGH | LOW
    predicted_waste_eur: Mapped[float] = mapped_column(Float, default=0.0)
    reason: Mapped[str] = mapped_column(String(600), default="")
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, server_default=func.now())


class Reallocation(Base):
    __tablename__ = "reallocation"
    id: Mapped[int] = mapped_column(primary_key=True)
    bakery_id: Mapped[int] = mapped_column(ForeignKey("bakery.id"), index=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("product.id"), index=True)
    target_date: Mapped[dt.date] = mapped_column(Date, index=True)
    from_site_id: Mapped[int] = mapped_column(ForeignKey("site.id"))
    to_site_id: Mapped[int] = mapped_column(ForeignKey("site.id"))
    quantity: Mapped[int] = mapped_column(Integer)
    eur_waste_avoided: Mapped[float] = mapped_column(Float, default=0.0)
    justification: Mapped[str] = mapped_column(String(600), default="")
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, server_default=func.now())


class RecommendationDecision(Base):
    __tablename__ = "recommendation_decision"
    id: Mapped[int] = mapped_column(primary_key=True)
    recommendation_id: Mapped[int] = mapped_column(
        ForeignKey("recommendation.id"), index=True
    )
    decision: Mapped[str] = mapped_column(String(12))  # accepted|edited|rejected|deferred
    final_qty: Mapped[int | None] = mapped_column(Integer, nullable=True)
    note: Mapped[str] = mapped_column(String(600), default="")
    decided_at: Mapped[dt.datetime] = mapped_column(DateTime, server_default=func.now())


class ReallocationDecision(Base):
    __tablename__ = "reallocation_decision"
    id: Mapped[int] = mapped_column(primary_key=True)
    reallocation_id: Mapped[int] = mapped_column(
        ForeignKey("reallocation.id"), index=True
    )
    decision: Mapped[str] = mapped_column(String(12))  # accepted|dismissed
    decided_at: Mapped[dt.datetime] = mapped_column(DateTime, server_default=func.now())


class AuditLog(Base):
    """Trust Layer audit record — every LLM interaction + decision is logged."""

    __tablename__ = "audit_log"
    id: Mapped[int] = mapped_column(primary_key=True)
    bakery_id: Mapped[int] = mapped_column(Integer, index=True)
    event: Mapped[str] = mapped_column(String(60))
    model: Mapped[str] = mapped_column(String(40), default="")
    payload_summary: Mapped[str] = mapped_column(String(1000), default="")
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, server_default=func.now())
