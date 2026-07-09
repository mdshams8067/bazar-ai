"""routers/cart.py — The current user's shopping cart. All routes require
auth; the user id always comes from the token, never the request body."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from core.database import get_db
from core.security import get_current_user
from models.cart_item import AddedVia, CartItem
from models.product import Product
from models.user import User
from schemas.cart import CartItemCreate, CartItemRead, CartItemUpdate, CartRead

router = APIRouter(prefix="/cart", tags=["cart"])


async def load_cart(db: AsyncSession, user_id: int) -> list[CartItem]:
    """Reused by routers/chat.py to return the cart's post-merge state."""
    result = await db.execute(
        select(CartItem)
        .where(CartItem.user_id == user_id)
        .options(selectinload(CartItem.product))
        .order_by(CartItem.created_at)
    )
    return list(result.scalars().all())


def to_cart_read(items: list[CartItem]) -> CartRead:
    """Reused by routers/chat.py to return the cart's post-merge state."""
    item_reads = [CartItemRead.model_validate(i) for i in items]
    subtotal = round(sum(i.line_total_bdt for i in item_reads), 2)
    return CartRead(items=item_reads, subtotal_bdt=subtotal, item_count=len(item_reads))


async def upsert_cart_item(
    db: AsyncSession,
    *,
    user_id: int,
    product_id: int,
    quantity: int,
    added_via: AddedVia = AddedVia.manual,
    substitution_note: str | None = None,
) -> CartItem:
    """Adds `quantity` of `product_id` to `user_id`'s cart, incrementing if
    already present (the (user_id, product_id) unique constraint is what
    makes this upsert instead of a duplicate row). Raises HTTPException on
    a missing product or insufficient stock. Does NOT commit — callers
    (this router's add_cart_item, and routers/chat.py adding several
    matched ingredients at once) commit once after all their upserts, so a
    multi-item add stays a single transaction.

    Reused by routers/chat.py: Bazar Buddy's matched ingredients merge into
    the user's real cart through this exact same path, not a parallel one.
    """
    product = await db.get(Product, product_id)
    if product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")

    existing = await db.scalar(
        select(CartItem).where(CartItem.user_id == user_id, CartItem.product_id == product_id)
    )
    new_quantity = (existing.quantity if existing else 0) + quantity
    if new_quantity > product.stock_qty:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Only {product.stock_qty} of {product.name_en} in stock",
        )

    if existing:
        existing.quantity = new_quantity
        existing.added_via = added_via
        if substitution_note:
            existing.substitution_note = substitution_note
        return existing

    item = CartItem(
        user_id=user_id,
        product_id=product_id,
        quantity=quantity,
        added_via=added_via,
        substitution_note=substitution_note,
    )
    db.add(item)
    return item


@router.get("", response_model=CartRead)
async def get_cart(
    db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)
) -> CartRead:
    return to_cart_read(await load_cart(db, current_user.id))


@router.post("/items", response_model=CartRead, status_code=status.HTTP_201_CREATED)
async def add_cart_item(
    payload: CartItemCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> CartRead:
    await upsert_cart_item(
        db,
        user_id=current_user.id,
        product_id=payload.product_id,
        quantity=payload.quantity,
        added_via=payload.added_via,
        substitution_note=payload.substitution_note,
    )
    await db.commit()
    return to_cart_read(await load_cart(db, current_user.id))


@router.patch("/items/{item_id}", response_model=CartRead)
async def update_cart_item(
    item_id: int,
    payload: CartItemUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> CartRead:
    item = await db.get(CartItem, item_id)
    if item is None or item.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cart item not found")

    if payload.quantity <= 0:
        # Documented behavior: quantity <= 0 deletes the row.
        await db.delete(item)
    else:
        product = await db.get(Product, item.product_id)
        if payload.quantity > product.stock_qty:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Only {product.stock_qty} of {product.name_en} in stock",
            )
        item.quantity = payload.quantity

    await db.commit()
    return to_cart_read(await load_cart(db, current_user.id))


@router.delete("/items/{item_id}", response_model=CartRead)
async def delete_cart_item(
    item_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> CartRead:
    item = await db.get(CartItem, item_id)
    if item is None or item.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cart item not found")

    await db.delete(item)
    await db.commit()
    return to_cart_read(await load_cart(db, current_user.id))


@router.delete("", status_code=status.HTTP_204_NO_CONTENT)
async def clear_cart(
    db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)
) -> None:
    for item in await load_cart(db, current_user.id):
        await db.delete(item)
    await db.commit()
