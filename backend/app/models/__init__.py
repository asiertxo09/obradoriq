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
    SaleEvent,
    SalesRecord,
    Site,
    User,
    WasteRecord,
)


def init_db() -> None:
    """Create all tables, then add any new columns missing on an existing DB.
    Idempotent; used for sqlite dev and as the Render release step."""
    Base.metadata.create_all(bind=engine)
    _ensure_columns()


def _ensure_columns() -> None:
    """Lightweight forward-migration: ADD COLUMN for fields added after a table was
    first created (we use create_all, not Alembic). Works on SQLite and Postgres."""
    from sqlalchemy import inspect, text

    wanted = {
        "sales_record": {
            "precip_mm": "FLOAT DEFAULT 0",
            "is_holiday": "BOOLEAN DEFAULT FALSE",
        },
        "site": {
            "latitude": "FLOAT DEFAULT 0",
            "longitude": "FLOAT DEFAULT 0",
        },
    }
    inspector = inspect(engine)
    with engine.begin() as conn:
        for table, cols in wanted.items():
            if not inspector.has_table(table):
                continue
            existing = {c["name"] for c in inspector.get_columns(table)}
            for name, ddl in cols.items():
                if name not in existing:
                    conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {name} {ddl}"))


__all__ = ["Base", "SessionLocal", "engine", "get_db", "init_db"]
