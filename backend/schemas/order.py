"""schemas/order.py — Request/response shapes for the orders resource."""
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict

from models.order import OrderStatus


class OrderCreate(BaseModel):
    """Optional checkout body. Omitted (or payment_method omitted) means
    "pay via SSLCommerz" — the frontend follows up with a separate
    POST /payment/sslcommerz/init/{id} call, and payment_method is only
    set once that gateway confirms a real transaction. "cod" is the one
    other case: no gateway involved at all, so we record it immediately."""

    payment_method: Literal["cod"] | None = None


class OrderItemRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    product_id: int | None
    product_name_snapshot: str
    quantity: int
    unit_price_bdt: float


class OrderRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    status: OrderStatus
    total_bdt: float
    payment_method: str | None
    created_at: datetime
    updated_at: datetime
    items: list[OrderItemRead]


class OrderListRead(BaseModel):
    items: list[OrderRead]
    total: int
    page: int
    page_size: int


class OrderStatusUpdate(BaseModel):
    status: OrderStatus
