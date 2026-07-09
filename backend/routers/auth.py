"""routers/auth.py — Signup, login, and the current-user endpoint."""
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.concurrency import run_in_threadpool
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from core.security import create_access_token, get_current_user, hash_password, verify_password
from models.user import User
from schemas.user import Token, UserCreate, UserRead

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/signup", response_model=Token)
async def signup(payload: UserCreate, db: AsyncSession = Depends(get_db)) -> Token:
    """Creates a user and auto-logs them in (no separate login step)."""
    existing = await db.scalar(select(User).where(User.email == payload.email))
    if existing is not None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email already registered")

    # hash_password is blocking bcrypt work — never call it inline in an
    # async def route, or a slow hash stalls every concurrent request.
    hashed = await run_in_threadpool(hash_password, payload.password)

    user = User(email=payload.email, hashed_password=hashed, name=payload.name, phone=payload.phone)
    db.add(user)
    await db.commit()
    await db.refresh(user)

    return Token(access_token=create_access_token(subject=str(user.id)))


@router.post("/login", response_model=Token)
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(), db: AsyncSession = Depends(get_db)
) -> Token:
    """OAuth2 password flow: `username` is the user's email."""
    user = await db.scalar(select(User).where(User.email == form_data.username))
    invalid_credentials = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Incorrect email or password",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if user is None:
        raise invalid_credentials

    # verify_password is blocking bcrypt work — see signup() above.
    valid = await run_in_threadpool(verify_password, form_data.password, user.hashed_password)
    if not valid:
        raise invalid_credentials

    return Token(access_token=create_access_token(subject=str(user.id)))


@router.get("/me", response_model=UserRead)
async def read_me(current_user: User = Depends(get_current_user)) -> User:
    return current_user
