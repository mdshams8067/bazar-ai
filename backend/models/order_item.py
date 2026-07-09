"""models/order_item.py — A line item snapshot within a placed order."""
from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.database import Base

if TYPE_CHECKING:
    from models.order import Order
    from models.product import Product


class OrderItem(Base):
    __tablename__ = "order_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id", ondelete="CASCADE"), nullable=False)
    # Nullable + SET NULL: orders are historical records and must survive a
    # product being discontinued/hard-deleted later — never cascade-delete
    # an OrderItem just because its product went away.
    product_id: Mapped[int | None] = mapped_column(
        ForeignKey("products.id", ondelete="SET NULL"), nullable=True
    )
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    # Snapshots at order time — never recompute historical orders off the
    # live Product row, which can change (price) or disappear (name)
    # after the order was placed. product_name_snapshot extends the same
    # snapshot principle the price field already uses, since an order with
    # a price but no name is useless once product_id goes NULL.
    unit_price_bdt: Mapped[float] = mapped_column(Numeric(10, 2, asdecimal=False), nullable=False)
    product_name_snapshot: Mapped[str] = mapped_column(String, nullable=False)

    order: Mapped["Order"] = relationship(back_populates="items")
    product: Mapped["Product | None"] = relationship()
