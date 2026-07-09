"""schemas/product.py — Request/response shapes for the products resource."""
from pydantic import BaseModel, ConfigDict, computed_field


class ProductBase(BaseModel):
    name_en: str
    name_bn: str | None = None
    category: str
    price_bdt: float
    unit: str
    unit_value: float
    stock_qty: int
    image_url: str | None = None


class ProductCreate(ProductBase):
    pass


class ProductUpdate(BaseModel):
    name_en: str | None = None
    name_bn: str | None = None
    category: str | None = None
    price_bdt: float | None = None
    unit: str | None = None
    unit_value: float | None = None
    stock_qty: int | None = None
    image_url: str | None = None


class ProductRead(ProductBase):
    model_config = ConfigDict(from_attributes=True)

    id: int

    @computed_field
    @property
    def in_stock(self) -> bool:
        return self.stock_qty > 0


class ProductListRead(BaseModel):
    items: list[ProductRead]
    total: int
    page: int
    page_size: int


class CategoryCount(BaseModel):
    category: str
    count: int
