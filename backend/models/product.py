"""models/product.py — Product catalog table."""
from sqlalchemy import Float, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from core.database import Base


class Product(Base):
    """A single catalog item, seeded from the Shwapno scrape."""

    __tablename__ = "products"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
    name_en: Mapped[str] = mapped_column(String, nullable=False, index=True)
    name_bn: Mapped[str | None] = mapped_column(String, nullable=True)
    category: Mapped[str] = mapped_column(String, nullable=False, index=True)
    # Numeric for DB-level fixed-precision money storage; asdecimal=False keeps
    # the Python-side value a plain float, since agent/matcher.py and
    # agent/pipeline.py already do float arithmetic on this field.
    price_bdt: Mapped[float] = mapped_column(Numeric(10, 2, asdecimal=False), nullable=False)
    unit: Mapped[str] = mapped_column(String, nullable=False)
    unit_value: Mapped[float] = mapped_column(Float, nullable=False)
    stock_qty: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    image_url: Mapped[str | None] = mapped_column(String, nullable=True)
