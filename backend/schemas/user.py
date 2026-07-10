"""schemas/user.py — Request/response shapes for auth/users."""
import re
from datetime import datetime

from email_validator import EmailNotValidError, validate_email
from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

# Deliberately not full email *verification* (send-a-confirmation-link,
# gate the account on clicking it) — that's a real feature (needs an
# email-sending provider, token storage, a verify page) out of scope for
# this build; documented as a limitation, not silently skipped. This is a
# real, useful middle ground though: DNS deliverability checking rejects
# addresses whose domain can't receive mail at all (typos like
# "gmial.com", made-up domains), which plain format validation (EmailStr
# alone) does not catch — it only checks the address *looks* like an
# email, not that anything could ever be delivered to it.
_PASSWORD_RULES = (
    (r"[A-Z]", "an uppercase letter"),
    (r"[a-z]", "a lowercase letter"),
    (r"\d", "a number"),
    (r"[^A-Za-z0-9]", "a symbol"),
)


class UserBase(BaseModel):
    email: EmailStr
    name: str
    phone: str | None = None


class UserCreate(UserBase):
    """Signup input only — the DNS/complexity checks below run once, at
    account creation. They deliberately do NOT live on UserBase, since
    UserRead also inherits from it and is built from every already-valid
    stored user on every read (e.g. GET /auth/me) — re-running a live DNS
    lookup on every response would be slow and could even reject an
    already-valid, already-registered user if their domain's DNS had a
    transient blip after signup.
    """

    password: str = Field(min_length=8, max_length=72)  # bcrypt truncates beyond 72 bytes

    @field_validator("email")
    @classmethod
    def _email_domain_must_exist(cls, v: str) -> str:
        try:
            validate_email(v, check_deliverability=True)
        except EmailNotValidError as e:
            raise ValueError(str(e)) from e
        return v

    @field_validator("password")
    @classmethod
    def _password_must_be_strong(cls, v: str) -> str:
        missing = [description for pattern, description in _PASSWORD_RULES if not re.search(pattern, v)]
        if missing:
            raise ValueError(f"Password must include {', '.join(missing)}.")
        return v


class UserRead(UserBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    is_active: bool
    created_at: datetime


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
