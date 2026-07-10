"""
schemas/profile.py — Response shape for the current user's profile.

No signup/login schemas here — those happen entirely on the frontend
against Supabase's own Auth API (email format, deliverability, and
password strength are enforced there now, not by this backend).
"""
import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ProfileRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    name: str
    phone: str | None
    created_at: datetime
