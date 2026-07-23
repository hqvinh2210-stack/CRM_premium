from __future__ import annotations

import hashlib
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from pos.db import get_db
from pos.deps import get_current_user
from pos.models.auth import RefreshToken, Role, Store, User, UserStoreRole
from pos.schemas import (
    LoginRequest,
    MeResponse,
    RefreshRequest,
    StoreCreate,
    StoreOut,
    TokenResponse,
    UserOut,
)
from pos.security import (
    REFRESH_DAYS,
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)

router = APIRouter(prefix="/auth")


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == body.email).first()
    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    if not user.is_active:
        raise HTTPException(status_code=401, detail="User inactive")

    memberships = db.query(UserStoreRole).filter(UserStoreRole.user_id == user.id).all()
    if not memberships:
        raise HTTPException(status_code=403, detail="User has no store access")

    store_id = body.store_id
    role: Role | None = None
    if store_id:
        m = next((x for x in memberships if x.store_id == store_id), None)
        if not m:
            raise HTTPException(status_code=403, detail="No access to store")
        role = m.role
    else:
        m = memberships[0]
        store_id = m.store_id
        role = m.role

    access = create_access_token(user.id, {"store_id": store_id, "role": role.value})
    refresh = create_refresh_token(user.id)
    db.add(
        RefreshToken(
            user_id=user.id,
            token_hash=_token_hash(refresh),
            expires_at=datetime.now(UTC) + timedelta(days=REFRESH_DAYS),
        )
    )
    db.commit()
    return TokenResponse(
        access_token=access,
        refresh_token=refresh,
        store_id=store_id,
        role=role.value if role else None,
    )


@router.post("/refresh", response_model=TokenResponse)
def refresh(body: RefreshRequest, db: Session = Depends(get_db)):
    try:
        payload = decode_token(body.refresh_token)
    except Exception as exc:
        raise HTTPException(status_code=401, detail="Invalid refresh token") from exc
    if payload.get("type") != "refresh":
        raise HTTPException(status_code=401, detail="Invalid token type")
    th = _token_hash(body.refresh_token)
    row = db.query(RefreshToken).filter(RefreshToken.token_hash == th, RefreshToken.revoked.is_(False)).first()
    if not row:
        raise HTTPException(status_code=401, detail="Refresh revoked or unknown")
    user = db.get(User, payload["sub"])
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="User inactive")
    membership = db.query(UserStoreRole).filter(UserStoreRole.user_id == user.id).first()
    store_id = membership.store_id if membership else None
    role = membership.role.value if membership else None
    access = create_access_token(user.id, {"store_id": store_id, "role": role})
    return TokenResponse(access_token=access, refresh_token=body.refresh_token, store_id=store_id, role=role)


@router.get("/me", response_model=MeResponse)
def me(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    links = db.query(UserStoreRole).filter(UserStoreRole.user_id == user.id).all()
    stores = []
    for link in links:
        store = db.get(Store, link.store_id)
        if store:
            stores.append(
                {
                    "store_id": store.id,
                    "code": store.code,
                    "name": store.name,
                    "role": link.role.value,
                }
            )
    return MeResponse(user=UserOut.model_validate(user), stores=stores)


@router.get("/stores", response_model=list[StoreOut])
def list_stores(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    links = db.query(UserStoreRole).filter(UserStoreRole.user_id == user.id).all()
    store_ids = [l.store_id for l in links]
    if not store_ids:
        return []
    return db.query(Store).filter(Store.id.in_(store_ids), Store.is_active.is_(True)).all()


@router.post("/stores", response_model=StoreOut)
def create_store(
    body: StoreCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # only existing admin of some store can create
    is_admin = (
        db.query(UserStoreRole)
        .filter(UserStoreRole.user_id == user.id, UserStoreRole.role == Role.admin)
        .first()
    )
    if not is_admin:
        raise HTTPException(status_code=403, detail="Admin only")
    if db.query(Store).filter(Store.code == body.code).first():
        raise HTTPException(status_code=400, detail="Store code exists")
    store = Store(code=body.code, name=body.name, address=body.address, timezone=body.timezone)
    db.add(store)
    db.flush()
    db.add(UserStoreRole(user_id=user.id, store_id=store.id, role=Role.admin))
    db.commit()
    db.refresh(store)
    return store
