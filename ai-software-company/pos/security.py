from __future__ import annotations

import os
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import bcrypt
import jwt

JWT_SECRET = os.getenv("JWT_SECRET", "dev-pos-secret-change-me-32bytes-min!!")
JWT_ALG = "HS256"
ACCESS_MINUTES = int(os.getenv("JWT_ACCESS_MINUTES", "60"))
REFRESH_DAYS = int(os.getenv("JWT_REFRESH_DAYS", "7"))


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except ValueError:
        return False


def create_access_token(sub: str, extra: dict[str, Any] | None = None) -> str:
    payload = {
        "sub": sub,
        "type": "access",
        "jti": str(uuid.uuid4()),
        "exp": datetime.now(UTC) + timedelta(minutes=ACCESS_MINUTES),
        **(extra or {}),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALG)


def create_refresh_token(sub: str) -> str:
    payload = {
        "sub": sub,
        "type": "refresh",
        "jti": str(uuid.uuid4()),
        "exp": datetime.now(UTC) + timedelta(days=REFRESH_DAYS),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALG)


def decode_token(token: str) -> dict[str, Any]:
    return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALG])
