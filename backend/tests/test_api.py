"""
tests/test_api.py — Integration tests for the core commerce CRUD backend.

Covers: signup -> login -> /auth/me; product list pagination/category/search;
cart add -> update -> over-stock rejection -> checkout -> cart cleared;
and the order-ownership isolation guarantee.
"""
from httpx import AsyncClient

from models.product import Product
from tests.conftest import signup_user


async def test_signup_login_me_round_trip(client: AsyncClient) -> None:
    signup_resp = await client.post(
        "/auth/signup",
        json={"email": "shopper@example.com", "password": "password123", "name": "Shopper"},
    )
    assert signup_resp.status_code == 200
    assert signup_resp.json()["token_type"] == "bearer"

    login_resp = await client.post(
        "/auth/login",
        data={"username": "shopper@example.com", "password": "password123"},
    )
    assert login_resp.status_code == 200
    token = login_resp.json()["access_token"]

    me_resp = await client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me_resp.status_code == 200
    assert me_resp.json()["email"] == "shopper@example.com"


async def test_login_rejects_wrong_password(client: AsyncClient) -> None:
    await signup_user(client, email="wrongpass@example.com")
    resp = await client.post(
        "/auth/login", data={"username": "wrongpass@example.com", "password": "not-the-password"}
    )
    assert resp.status_code == 401


async def test_product_list_pagination_category_and_search(
    client: AsyncClient, seeded_products: list[Product]
) -> None:
    all_resp = await client.get("/products", params={"page": 1, "page_size": 2})
    assert all_resp.status_code == 200
    body = all_resp.json()
    assert body["total"] == 3
    assert len(body["items"]) == 2  # page_size respected at the DB level

    category_resp = await client.get("/products", params={"category": "Rice"})
    cat_items = category_resp.json()["items"]
    assert len(cat_items) == 1
    assert cat_items[0]["name_en"] == "Test Chinigura Rice 1kg"

    search_resp = await client.get("/products", params={"search": "Eggs"})
    search_items = search_resp.json()["items"]
    assert len(search_items) == 1
    assert search_items[0]["name_en"] == "Test Eggs 12Pcs"

    in_stock_resp = await client.get("/products", params={"in_stock_only": True})
    in_stock_items = in_stock_resp.json()["items"]
    assert all(item["in_stock"] for item in in_stock_items)
    assert len(in_stock_items) == 2  # the 0-stock oil is excluded


async def test_categories_endpoint(client: AsyncClient, seeded_products: list[Product]) -> None:
    resp = await client.get("/products/categories")
    assert resp.status_code == 200
    categories = {row["category"]: row["count"] for row in resp.json()}
    assert categories == {"Rice": 1, "Soybean Oil": 1, "Eggs": 1}


async def test_cart_add_update_overstock_checkout_clears_cart(
    client: AsyncClient, seeded_products: list[Product]
) -> None:
    token = await signup_user(client)
    headers = {"Authorization": f"Bearer {token}"}

    # Adding more than in stock (product 2 has stock_qty=0) is rejected.
    overstock_resp = await client.post(
        "/cart/items", json={"product_id": 2, "quantity": 1}, headers=headers
    )
    assert overstock_resp.status_code == 400
    assert "in stock" in overstock_resp.json()["detail"]

    # Add an in-stock item.
    add_resp = await client.post(
        "/cart/items", json={"product_id": 1, "quantity": 2}, headers=headers
    )
    assert add_resp.status_code == 201
    cart = add_resp.json()
    assert cart["item_count"] == 1
    assert cart["subtotal_bdt"] == 380.0  # 2 x 190.0

    # Adding the same product again increments quantity (upsert), not a duplicate row.
    add_again_resp = await client.post(
        "/cart/items", json={"product_id": 1, "quantity": 1}, headers=headers
    )
    cart_after_second_add = add_again_resp.json()
    assert cart_after_second_add["item_count"] == 1
    assert cart_after_second_add["items"][0]["quantity"] == 3

    item_id = cart_after_second_add["items"][0]["id"]

    # Requesting more than stock (10) via update is rejected.
    over_update_resp = await client.patch(
        f"/cart/items/{item_id}", json={"quantity": 999}, headers=headers
    )
    assert over_update_resp.status_code == 400

    # Update to a valid quantity.
    update_resp = await client.patch(
        f"/cart/items/{item_id}", json={"quantity": 5}, headers=headers
    )
    assert update_resp.json()["items"][0]["quantity"] == 5

    # Checkout: creates an order, decrements stock, clears the cart.
    checkout_resp = await client.post("/orders", headers=headers)
    assert checkout_resp.status_code == 201
    order = checkout_resp.json()
    assert order["status"] == "pending"
    assert order["total_bdt"] == 950.0  # 5 x 190.0
    assert order["items"][0]["product_name_snapshot"] == "Test Chinigura Rice 1kg"

    empty_cart_resp = await client.get("/cart", headers=headers)
    assert empty_cart_resp.json()["item_count"] == 0

    product_resp = await client.get("/products/1")
    assert product_resp.json()["stock_qty"] == 5  # 10 - 5


async def test_checkout_with_empty_cart_is_rejected(client: AsyncClient) -> None:
    token = await signup_user(client, email="emptycart@example.com")
    resp = await client.post("/orders", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 400


async def test_order_status_progression(client: AsyncClient, seeded_products: list[Product]) -> None:
    token = await signup_user(client, email="progression@example.com")
    headers = {"Authorization": f"Bearer {token}"}
    await client.post("/cart/items", json={"product_id": 3, "quantity": 1}, headers=headers)
    order = (await client.post("/orders", headers=headers)).json()

    confirm_resp = await client.patch(
        f"/orders/{order['id']}/status", json={"status": "confirmed"}, headers=headers
    )
    assert confirm_resp.status_code == 200
    assert confirm_resp.json()["status"] == "confirmed"

    # Skipping a step (confirmed -> delivered is fine, but not pending -> delivered again) is rejected.
    invalid_resp = await client.patch(
        f"/orders/{order['id']}/status", json={"status": "pending"}, headers=headers
    )
    assert invalid_resp.status_code == 400


async def test_order_ownership_isolation(client: AsyncClient, seeded_products: list[Product]) -> None:
    """User A cannot read (or enumerate the existence of) User B's order."""
    token_a = await signup_user(client, email="user_a@example.com")
    token_b = await signup_user(client, email="user_b@example.com")

    headers_a = {"Authorization": f"Bearer {token_a}"}
    headers_b = {"Authorization": f"Bearer {token_b}"}

    await client.post("/cart/items", json={"product_id": 1, "quantity": 1}, headers=headers_a)
    order_a = (await client.post("/orders", headers=headers_a)).json()

    # 404, not 403 — must not confirm the order id exists to a non-owner.
    resp = await client.get(f"/orders/{order_a['id']}", headers=headers_b)
    assert resp.status_code == 404

    # The real owner can still read it.
    own_resp = await client.get(f"/orders/{order_a['id']}", headers=headers_a)
    assert own_resp.status_code == 200
