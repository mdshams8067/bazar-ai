"""
routers/payment.py — SSLCommerz sandbox payment integration.

Flow: POST /orders creates the order (pending, stock already decremented,
cart already cleared) -> frontend calls POST /payment/sslcommerz/init/{id}
-> we open an SSLCommerz session and hand back their GatewayPageURL ->
frontend does a full-page redirect there (a real SSLCommerz-hosted
checkout, not something we can render inline) -> the customer completes
(or cancels) a sandbox test payment -> SSLCommerz calls our success/fail/
cancel endpoints back (browser redirect) and, independently, our IPN
endpoint (server-to-server) -> the success/IPN handler re-validates the
transaction through SSLCommerz's Validation API before trusting it, since
a redirect URL and its POSTed fields are trivially replayable by a client
-> order flips pending -> confirmed -> browser lands back on the SPA's
order confirmation page.

These callback routes are deliberately unauthenticated (no JWT dependency)
— SSLCommerz's server can't carry our bearer token. That's safe because
the handler never trusts the callback body alone; it independently asks
SSLCommerz to confirm the transaction using our own store credentials,
which a forged request can't supply.
"""
from __future__ import annotations

import logging
import uuid

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import BACKEND_URL, FRONTEND_URL
from core.database import get_db
from core.security import get_current_user
from core.sslcommerz import SslcommerzError, create_session, validate_transaction
from models.order import Order, OrderStatus
from models.profile import Profile

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/payment/sslcommerz", tags=["payment"])


@router.post("/init/{order_id}")
async def init_payment(
    order_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: Profile = Depends(get_current_user),
) -> dict:
    order = await db.get(Order, order_id)
    if order is None or order.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Order not found")
    if order.status != OrderStatus.pending:
        raise HTTPException(
            status_code=400, detail=f"Order is already {order.status.value}, not awaiting payment"
        )
    if order.payment_method == "cod":
        raise HTTPException(status_code=400, detail="This order was placed as cash on delivery")

    # A fresh tran_id per attempt (not per order) — lets the customer retry
    # payment on the same still-pending order after a failed/cancelled try.
    tran_id = f"order{order.id}-{uuid.uuid4().hex[:10]}"
    order.tran_id = tran_id
    await db.commit()

    try:
        gateway_url = await create_session(
            tran_id=tran_id,
            amount=order.total_bdt,
            success_url=f"{BACKEND_URL}/payment/sslcommerz/success/{order.id}",
            fail_url=f"{BACKEND_URL}/payment/sslcommerz/fail/{order.id}",
            cancel_url=f"{BACKEND_URL}/payment/sslcommerz/cancel/{order.id}",
            ipn_url=f"{BACKEND_URL}/payment/sslcommerz/success/{order.id}",
            customer_name=current_user.name,
            customer_email=current_user.email,
            customer_phone=current_user.phone or "01700000000",
        )
    except (SslcommerzError, httpx.HTTPError) as e:
        logger.exception(f"[payment] SSLCommerz session init failed for order {order.id}")
        raise HTTPException(status_code=502, detail=f"Payment gateway error: {e}") from e

    return {"gateway_url": gateway_url}


async def _handle_success(order_id: int, request: Request, db: AsyncSession) -> RedirectResponse:
    form = await request.form() if request.method == "POST" else request.query_params
    val_id = form.get("val_id")

    order = await db.get(Order, order_id)
    if order is None:
        return RedirectResponse(f"{FRONTEND_URL}/checkout", status_code=303)

    # Idempotent: SSLCommerz calls both the browser-redirect success_url
    # AND the server-to-server ipn_url (we point both at this same handler)
    # — a second call for an already-confirmed order is a no-op, not an error.
    if order.status == OrderStatus.pending and val_id:
        try:
            result = await validate_transaction(str(val_id))
        except Exception:
            logger.exception(f"[payment] validation call failed for order {order_id}")
            result = {}

        valid = (
            result.get("status") in ("VALID", "VALIDATED")
            and str(result.get("tran_id")) == order.tran_id
            and float(result.get("amount", 0)) == float(order.total_bdt)
        )
        if valid:
            order.status = OrderStatus.confirmed
            order.payment_method = result.get("card_issuer") or result.get("card_type") or "sslcommerz"
            await db.commit()
            logger.info(f"[payment] order {order_id} confirmed via SSLCommerz (val_id={val_id})")
        else:
            logger.warning(f"[payment] validation failed/mismatched for order {order_id}: {result}")
            return RedirectResponse(
                f"{FRONTEND_URL}/order-confirmation/{order_id}?payment=failed", status_code=303
            )

    return RedirectResponse(f"{FRONTEND_URL}/order-confirmation/{order_id}?payment=success", status_code=303)


@router.post("/success/{order_id}")
@router.get("/success/{order_id}")
async def payment_success(order_id: int, request: Request, db: AsyncSession = Depends(get_db)) -> RedirectResponse:
    return await _handle_success(order_id, request, db)


@router.post("/fail/{order_id}")
@router.get("/fail/{order_id}")
async def payment_fail(order_id: int) -> RedirectResponse:
    return RedirectResponse(f"{FRONTEND_URL}/order-confirmation/{order_id}?payment=failed", status_code=303)


@router.post("/cancel/{order_id}")
@router.get("/cancel/{order_id}")
async def payment_cancel(order_id: int) -> RedirectResponse:
    return RedirectResponse(f"{FRONTEND_URL}/order-confirmation/{order_id}?payment=cancelled", status_code=303)
