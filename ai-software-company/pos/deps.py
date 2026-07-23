from __future__ import annotations

from dataclasses import dataclass

from fastapi import Depends, Header, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from pos.db import get_db
from pos.models.auth import Role, User, UserStoreRole
from pos.security import decode_token

bearer = HTTPBearer(auto_error=False)


@dataclass
class AuthContext:
    user: User
    store_id: str
    role: Role


def get_current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: Session = Depends(get_db),
) -> User:
    if creds is None or not creds.credentials:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    try:
        payload = decode_token(creds.credentials)
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token") from exc
    if payload.get("type") != "access":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token type")
    user = db.get(User, payload["sub"])
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User inactive")
    return user


def get_auth_context(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    x_store_id: str | None = Header(default=None, alias="X-Store-Id"),
) -> AuthContext:
    if not x_store_id:
        raise HTTPException(status_code=400, detail="X-Store-Id header required")
    membership = (
        db.query(UserStoreRole)
        .filter(UserStoreRole.user_id == user.id, UserStoreRole.store_id == x_store_id)
        .first()
    )
    if not membership:
        raise HTTPException(status_code=403, detail="No access to this store")
    return AuthContext(user=user, store_id=x_store_id, role=membership.role)


def require_roles(*roles: Role):
    allowed = set(roles)

    def _dep(ctx: AuthContext = Depends(get_auth_context)) -> AuthContext:
        if ctx.role not in allowed and Role.admin not in {ctx.role}:
            # admin always allowed if listed, else check membership
            if ctx.role != Role.admin and ctx.role not in allowed:
                raise HTTPException(status_code=403, detail=f"Requires role: {[r.value for r in roles]}")
        if ctx.role != Role.admin and ctx.role not in allowed:
            raise HTTPException(status_code=403, detail="Forbidden")
        return ctx

    return _dep


# Simpler: admin bypasses; else role must be in allowed
def require_any(*roles: str):
    allowed = {Role(r) if not isinstance(r, Role) else r for r in roles}

    def _dep(ctx: AuthContext = Depends(get_auth_context)) -> AuthContext:
        if ctx.role == Role.admin or ctx.role in allowed:
            return ctx
        raise HTTPException(status_code=403, detail="Forbidden for this role")

    return _dep
