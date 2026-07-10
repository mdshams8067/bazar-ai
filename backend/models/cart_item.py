"""models/cart_item.py — A user's in-progress cart line items."""
from __future__ import annotations

import enum
import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.database import Base

if TYPE_CHECKING:
    from models.product import Product
    from models.profile import Profile


class AddedVia(str, enum.Enum):
    manual = "manual"
    assistant = "assistant"


class CartItem(Base):
    __tablename__ = "cart_items"
    __table_args__ = (UniqueConstraint("user_id", "product_id", name="uq_cart_user_product"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False
    )
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    added_via: Mapped[AddedVia] = mapped_column(
        Enum(AddedVia, native_enum=False), nullable=False, default=AddedVia.manual
    )
    # Carries a Bazar Buddy substitution note ("Chashi stepped in for ACI's
    # rice") through to checkout so the UI can keep showing it.
    substitution_note: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )

    user: Mapped["Profile"] = relationship(back_populates="cart_items")
    product: Mapped["Product"] = relationship()
