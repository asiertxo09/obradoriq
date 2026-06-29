"""Password hashing and JWT helpers."""
from __future__ import annotations

import datetime as dt

import bcrypt
from jose import JWTError, jwt

from app.core.config import get_settings


def _to_bytes(password: str) -> bytes:
    # bcrypt hard-limits input to 72 bytes; truncate explicitly (standard practice).
    return password.encode("utf-8")[:72]


def hash_password(password: str) -> str:
    return bcrypt.hashpw(_to_bytes(password), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(_to_bytes(password), hashed.encode("utf-8"))
    except ValueError:
        return False


def create_access_token(*, user_id: int, bakery_id: int) -> str:
    s = get_settings()
    expire = dt.datetime.now(dt.timezone.utc) + dt.timedelta(minutes=s.access_token_minutes)
    payload = {"sub": str(user_id), "bakery_id": bakery_id, "exp": expire}
    return jwt.encode(payload, s.jwt_secret, algorithm=s.jwt_algorithm)


def decode_token(token: str) -> dict | None:
    s = get_settings()
    try:
        return jwt.decode(token, s.jwt_secret, algorithms=[s.jwt_algorithm])
    except JWTError:
        return None
