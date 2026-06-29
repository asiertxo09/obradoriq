"""Model package — re-export entities and a table-creation helper."""
from app.models.base import Base, SessionLocal, engine, get_db
from app.models.entities import (  # noqa: F401
    AuditLog,
    Bakery,
    InventoryRecord,
    Product,
    Reallocation,
    Recommendation,
    RecommendationDecision,
    SalesRecord,
    Site,
    User,
    WasteRecord,
)


def init_db() -> None:
    """Create all tables. Idempotent; used for sqlite dev and as the Render release step."""
    Base.metadata.create_all(bind=engine)


__all__ = ["Base", "SessionLocal", "engine", "get_db", "init_db"]
