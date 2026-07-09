"""schemas/user.py — Request/response shapes for auth/users."""
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class UserBase(BaseModel):
    email: EmailStr
    name: str
    phone: str | None = None


class UserCreate(UserBase):
    password: str = Field(min_length=8, max_length=72)  # bcrypt truncates beyond 72 bytes


class UserRead(UserBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    is_active: bool
    created_at: datetime


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
