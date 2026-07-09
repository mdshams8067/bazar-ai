"""schemas/order.py — Request/response shapes for the orders resource."""
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from models.order import OrderStatus


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
