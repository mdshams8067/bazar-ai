"""
models/profile.py — App-specific data for a Supabase-authenticated user.

Supabase owns the actual account (email, password, id) in its own
`auth.users` table, which this app never creates or migrates — Supabase
manages that schema itself. This table holds only what Supabase's schema
has no place for (name, phone), keyed by the same id Supabase already
assigns, so it's a 1:1 extension of their table, not a parallel one.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.database import Base

if TYPE_CHECKING:
    from models.cart_item import CartItem
    from models.order import Order


class Profile(Base):
    __tablename__ = "profiles"

    # Same value as the corresponding auth.users.id Supabase assigned at
    # signup — not a separate identity, just this table's primary key.
    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    phone: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )

    cart_items: Mapped[list["CartItem"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    orders: Mapped[list["Order"]] = relationship(back_populates="user")
