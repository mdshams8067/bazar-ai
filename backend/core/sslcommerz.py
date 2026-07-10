"""
core/sslcommerz.py — Thin wrapper around SSLCommerz's payment gateway REST
API (session init + transaction validation).

Defaults to SSLCommerz's own publicly documented sandbox demo-store
credentials (store_id=testbox, store_passwd=qwerty) — a real, working test
account, not a fabricated placeholder. No merchant registration is needed
for sandbox use; only their live/production gateway requires that.
"""
from __future__ import annotations

import httpx

from core.config import SSLCOMMERZ_API_URL, SSLCOMMERZ_STORE_ID, SSLCOMMERZ_STORE_PASSWORD, SSLCOMMERZ_VALIDATION_URL


class SslcommerzError(Exception):
    """Raised when SSLCommerz rejects a session-init call."""


async def create_session(
    *,
    tran_id: str,
    amount: float,
    success_url: str,
    fail_url: str,
    cancel_url: str,
    ipn_url: str,
    customer_name: str,
    customer_email: str,
    customer_phone: str,
) -> str:
    """Initiates a payment session; returns the GatewayPageURL to redirect
    the customer's browser to."""
    payload = {
        "store_id": SSLCOMMERZ_STORE_ID,
        "store_passwd": SSLCOMMERZ_STORE_PASSWORD,
        "total_amount": f"{amount:.2f}",
        "currency": "BDT",
        "tran_id": tran_id,
        "success_url": success_url,
        "fail_url": fail_url,
        "cancel_url": cancel_url,
        "ipn_url": ipn_url,
        "shipping_method": "NO",
        "product_name": "Bazar AI grocery order",
        "product_category": "Grocery",
        "product_profile": "general",
        "cus_name": customer_name,
        "cus_email": customer_email,
        "cus_add1": "Dhaka",
        "cus_city": "Dhaka",
        "cus_postcode": "1000",
        "cus_country": "Bangladesh",
        "cus_phone": customer_phone,
    }
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(SSLCOMMERZ_API_URL, data=payload)
    resp.raise_for_status()
    data = resp.json()
    if data.get("status") != "SUCCESS":
        raise SslcommerzError(data.get("failedreason") or f"SSLCommerz session init failed: {data}")
    return data["GatewayPageURL"]


async def validate_transaction(val_id: str) -> dict:
    """Server-to-server confirmation that a transaction is genuine — never
    trust a success/IPN callback alone, since the redirect URL and its form
    fields are trivially replayable/forgeable by a client. This call is
    authenticated with our own store_passwd, which an attacker can't supply."""
    params = {
        "val_id": val_id,
        "store_id": SSLCOMMERZ_STORE_ID,
        "store_passwd": SSLCOMMERZ_STORE_PASSWORD,
        "format": "json",
    }
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(SSLCOMMERZ_VALIDATION_URL, params=params)
    resp.raise_for_status()
    return resp.json()
