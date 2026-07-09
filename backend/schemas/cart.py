"""schemas/cart.py — Request/response shapes for the cart resource."""
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, computed_field

from models.cart_item import AddedVia
from schemas.product import ProductRead


class CartItemCreate(BaseModel):
    product_id: int
    quantity: int = Field(gt=0, default=1)
    added_via: AddedVia = AddedVia.manual
    substitution_note: str | None = None


class CartItemUpdate(BaseModel):
    # quantity <= 0 deletes the row — see routers/cart.py.
    quantity: int


class CartItemRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    product: ProductRead
    quantity: int
    added_via: AddedVia
    substitution_note: str | None
    created_at: datetime

    @computed_field
    @property
    def line_total_bdt(self) -> float:
        return round(self.product.price_bdt * self.quantity, 2)


class CartRead(BaseModel):
    items: list[CartItemRead]
    subtotal_bdt: float
    item_count: int
