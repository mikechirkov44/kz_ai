from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import settings
from app.constants import UserRole
from app.db import get_db
from app.deps import get_current_user, require_roles, write_audit
from app.models import User
from app.schemas import LoginRequest, RefreshRequest, TokenResponse, UserCreate, UserOut, UserUpdate
from app.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> TokenResponse:
    user = db.scalar(select(User).where(User.email == payload.email.lower()))
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    if user.locked_until and user.locked_until > datetime.now(timezone.utc):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account locked")

    if not verify_password(payload.password, user.password_hash):
        user.failed_login_attempts += 1
        if user.failed_login_attempts >= 5:
            user.locked_until = datetime.now(timezone.utc) + timedelta(minutes=15)
            user.failed_login_attempts = 0
        db.commit()
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    user.failed_login_attempts = 0
    user.locked_until = None
    db.commit()
    write_audit(db, user_id=user.id, action="login")
    db.commit()

    return TokenResponse(
        access_token=create_access_token(user.id),
        refresh_token=create_refresh_token(user.id),
        expires_in=settings.access_token_expire_minutes * 60,
    )


@router.post("/refresh", response_model=TokenResponse)
def refresh(payload: RefreshRequest, db: Session = Depends(get_db)) -> TokenResponse:
    data = decode_token(payload.refresh_token)
    if not data or data.get("type") != "refresh":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")

    user = db.get(User, UUID(data["sub"]))
    if not user or not user.active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid user")
    return TokenResponse(
        access_token=create_access_token(user.id),
        refresh_token=create_refresh_token(user.id),
        expires_in=settings.access_token_expire_minutes * 60,
    )


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)) -> User:
    return user


@router.post("/users", response_model=UserOut)
def create_user(
    payload: UserCreate,
    db: Session = Depends(get_db),
    actor: User = Depends(require_roles(UserRole.ADMIN)),
) -> User:
    if payload.role not in {r.value for r in UserRole}:
        raise HTTPException(status_code=400, detail="Unknown role")
    exists = db.scalar(select(User).where(User.email == payload.email.lower()))
    if exists:
        raise HTTPException(status_code=400, detail="Email already exists")
    user = User(
        email=payload.email.lower(),
        password_hash=hash_password(payload.password),
        role=payload.role,
        region=payload.region,
        full_name=payload.full_name,
    )
    db.add(user)
    db.flush()
    write_audit(
        db,
        user_id=actor.id,
        action="user_create",
        entity_type="user",
        entity_id=str(user.id),
        details={"email": user.email, "role": user.role},
    )
    db.commit()
    db.refresh(user)
    return user


@router.get("/users", response_model=list[UserOut])
def list_users(
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(UserRole.ADMIN)),
) -> list[User]:
    return list(db.scalars(select(User).order_by(User.email)).all())


@router.get("/managers", response_model=list[UserOut])
def list_managers(
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(UserRole.ADMIN, UserRole.REGIONAL_DIRECTOR, UserRole.ANALYTIC)),
) -> list[User]:
    return list(
        db.scalars(
            select(User)
            .where(User.role == UserRole.MANAGER.value, User.active.is_(True))
            .order_by(User.full_name.nulls_last(), User.email)
        ).all()
    )


def _active_admin_count(db: Session) -> int:
    return db.scalar(
        select(func.count()).select_from(User).where(User.role == UserRole.ADMIN.value, User.active.is_(True))
    ) or 0


@router.patch("/users/{user_id}", response_model=UserOut)
def update_user(
    user_id: UUID,
    payload: UserUpdate,
    db: Session = Depends(get_db),
    actor: User = Depends(require_roles(UserRole.ADMIN)),
) -> User:
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if payload.role is not None and payload.role not in {r.value for r in UserRole}:
        raise HTTPException(status_code=400, detail="Unknown role")

    becoming_inactive = payload.active is False and user.active
    leaving_admin = (
        user.role == UserRole.ADMIN.value
        and payload.role is not None
        and payload.role != UserRole.ADMIN.value
    )
    if (becoming_inactive or leaving_admin) and user.role == UserRole.ADMIN.value and _active_admin_count(db) <= 1:
        raise HTTPException(status_code=400, detail="Нельзя деактивировать или сменить роль последнего админа")

    if payload.role is not None:
        user.role = payload.role
    if payload.region is not None:
        user.region = payload.region
    if payload.full_name is not None:
        user.full_name = payload.full_name
    if payload.active is not None:
        user.active = payload.active
    if payload.password:
        user.password_hash = hash_password(payload.password)
        user.password_changed_at = datetime.now(timezone.utc)
        user.failed_login_attempts = 0
        user.locked_until = None

    write_audit(
        db,
        user_id=actor.id,
        action="user_update",
        entity_type="user",
        entity_id=str(user.id),
        details={"role": user.role, "active": user.active},
    )
    db.commit()
    db.refresh(user)
    return user
