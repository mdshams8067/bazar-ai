"""routers/products.py — Product catalog listing and admin-style CRUD."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from core.security import get_current_user
from models.product import Product
from models.profile import Profile
from schemas.product import CategoryCount, ProductCreate, ProductListRead, ProductRead, ProductUpdate

router = APIRouter(prefix="/products", tags=["products"])


@router.get("/categories", response_model=list[CategoryCount])
async def list_categories(db: AsyncSession = Depends(get_db)) -> list[CategoryCount]:
    """Distinct category list with counts — powers the frontend category
    grid/sidebar so it never has to hardcode category names."""
    rows = (
        await db.execute(
            select(Product.category, func.count(Product.id))
            .group_by(Product.category)
            .order_by(Product.category)
        )
    ).all()
    return [CategoryCount(category=cat, count=count) for cat, count in rows]


@router.get("", response_model=ProductListRead)
async def list_products(
    category: str | None = None,
    search: str | None = None,
    in_stock_only: bool = False,
    sort: str = Query("relevance", pattern="^(price_asc|price_desc|relevance)$"),
    page: int = Query(1, ge=1),
    page_size: int = Query(24, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
) -> ProductListRead:
    query = select(Product)
    if category:
        query = query.where(Product.category == category)
    if search:
        query = query.where(Product.name_en.ilike(f"%{search}%"))
    if in_stock_only:
        query = query.where(Product.stock_qty > 0)

    total = await db.scalar(select(func.count()).select_from(query.subquery()))

    if sort == "price_asc":
        query = query.order_by(Product.price_bdt.asc())
    elif sort == "price_desc":
        query = query.order_by(Product.price_bdt.desc())
    elif search:
        # Relevance: names starting with the search term outrank names
        # that merely contain it elsewhere.
        starts_with_rank = case((Product.name_en.ilike(f"{search}%"), 0), else_=1)
        query = query.order_by(starts_with_rank, Product.name_en.asc())
    else:
        query = query.order_by(Product.id.asc())

    query = query.offset((page - 1) * page_size).limit(page_size)
    items = (await db.execute(query)).scalars().all()

    return ProductListRead(items=list(items), total=total or 0, page=page, page_size=page_size)


@router.get("/{product_id}", response_model=ProductRead)
async def get_product(product_id: int, db: AsyncSession = Depends(get_db)) -> Product:
    product = await db.get(Product, product_id)
    if product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
    return product


@router.post("", response_model=ProductRead, status_code=status.HTTP_201_CREATED)
async def create_product(
    payload: ProductCreate,
    db: AsyncSession = Depends(get_db),
    _current_user: Profile = Depends(get_current_user),
) -> Product:
    """Admin-style create, included for CRUD completeness. Gated behind
    "any authenticated user" only — a real role/admin system is out of
    scope for a 3-day take-home; documented limitation, not an oversight.

    IDs are assigned manually (max(id)+1) rather than via DB autoincrement:
    the seeded catalog already occupies a fixed, meaningful ID range
    (1..2807), and mixing that with a Postgres SERIAL sequence risks a
    future collision once the sequence counter catches up to a
    manually-seeded value.
    """
    next_id = (await db.scalar(select(func.max(Product.id)))) or 0
    product = Product(id=next_id + 1, **payload.model_dump())
    db.add(product)
    await db.commit()
    await db.refresh(product)
    return product


@router.patch("/{product_id}", response_model=ProductRead)
async def update_product(
    product_id: int,
    payload: ProductUpdate,
    db: AsyncSession = Depends(get_db),
    _current_user: Profile = Depends(get_current_user),
) -> Product:
    product = await db.get(Product, product_id)
    if product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(product, field, value)

    await db.commit()
    await db.refresh(product)
    return product


@router.delete("/{product_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_product(
    product_id: int,
    db: AsyncSession = Depends(get_db),
    _current_user: Profile = Depends(get_current_user),
) -> None:
    product = await db.get(Product, product_id)
    if product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
    await db.delete(product)
    await db.commit()
