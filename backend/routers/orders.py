"""routers/orders.py — Checkout (cart -> order) and order history. All
routes require auth."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from core.database import get_db
from core.security import get_current_user
from models.cart_item import CartItem
from models.order import Order, OrderStatus
from models.order_item import OrderItem
from models.user import User
from schemas.order import OrderListRead, OrderRead, OrderStatusUpdate

router = APIRouter(prefix="/orders", tags=["orders"])

# Simulated fulfillment progression — not wired to a real courier.
_NEXT_STATUS = {
    OrderStatus.pending: OrderStatus.confirmed,
    OrderStatus.confirmed: OrderStatus.delivered,
}


@router.post("", response_model=OrderRead, status_code=status.HTTP_201_CREATED)
async def create_order(
    db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)
) -> Order:
    """Creates an order from the current cart: validates stock, snapshots
    price/name and decrements stock, clears the cart — all in one
    transaction (a single commit at the end), so a failed step never
    leaves a half-created order alongside a full cart, or an emptied cart
    with nothing to show for it."""
    cart_items = (
        (
            await db.execute(
                select(CartItem)
                .where(CartItem.user_id == current_user.id)
                .options(selectinload(CartItem.product))
            )
        )
        .scalars()
        .all()
    )
    if not cart_items:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cart is empty")

    # Validate everything before mutating anything.
    for item in cart_items:
        if item.quantity > item.product.stock_qty:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Only {item.product.stock_qty} of {item.product.name_en} in stock",
            )

    order = Order(user_id=current_user.id, status=OrderStatus.pending, total_bdt=0.0)
    db.add(order)

    total = 0.0
    for item in cart_items:
        item.product.stock_qty -= item.quantity
        total += round(item.product.price_bdt * item.quantity, 2)
        order.items.append(
            OrderItem(
                product_id=item.product_id,
                product_name_snapshot=item.product.name_en,
                quantity=item.quantity,
                unit_price_bdt=item.product.price_bdt,
            )
        )
        await db.delete(item)

    order.total_bdt = round(total, 2)

    await db.commit()
    await db.refresh(order, attribute_names=["items"])
    return order


@router.get("", response_model=OrderListRead)
async def list_orders(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> OrderListRead:
    base_query = select(Order).where(Order.user_id == current_user.id)
    total = await db.scalar(select(func.count()).select_from(base_query.subquery()))

    result = await db.execute(
        base_query.options(selectinload(Order.items))
        .order_by(Order.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    return OrderListRead(items=list(result.scalars().all()), total=total or 0, page=page, page_size=page_size)


@router.get("/{order_id}", response_model=OrderRead)
async def get_order(
    order_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Order:
    order = await db.get(Order, order_id, options=[selectinload(Order.items)])
    # 404, not 403, on a mismatched owner — don't confirm the ID exists to
    # a user who doesn't own it.
    if order is None or order.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")
    return order


@router.patch("/{order_id}/status", response_model=OrderRead)
async def update_order_status(
    order_id: int,
    payload: OrderStatusUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Order:
    """Simulates status progression (pending -> confirmed -> delivered).
    No real fulfillment behind this — a demo transition endpoint, not
    wired to a courier."""
    order = await db.get(Order, order_id, options=[selectinload(Order.items)])
    if order is None or order.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")

    if payload.status != _NEXT_STATUS.get(order.status):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot move order from {order.status.value} to {payload.status.value}",
        )

    order.status = payload.status
    await db.commit()
    await db.refresh(order, attribute_names=["items"])
    return order
