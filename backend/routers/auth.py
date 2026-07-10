"""
routers/auth.py — The current-user endpoint.

No signup/login here — the frontend calls Supabase's own Auth API directly
(supabase-js) for those. This backend only ever sees an already-issued
bearer token and verifies it (core/security.py); this endpoint just
returns what it resolved that token to.
"""
from fastapi import APIRouter, Depends

from core.security import get_current_user
from models.profile import Profile
from schemas.profile import ProfileRead

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/me", response_model=ProfileRead)
async def read_me(current_user: Profile = Depends(get_current_user)) -> Profile:
    return current_user
