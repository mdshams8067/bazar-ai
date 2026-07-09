"""
tests/conftest.py — Shared fixtures for the API test suite.

Every test runs against a fresh in-memory SQLite database, isolated from
the real seeded dev/prod database (core/database.py's own engine is never
touched here) — the FastAPI get_db dependency is overridden per test.
"""
from collections.abc import AsyncIterator

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

import models  # noqa: F401 — registers every model class with Base.metadata
from core.database import Base, get_db
from main import app
from models.product import Product


@pytest_asyncio.fixture
async def db_session() -> AsyncIterator[AsyncSession]:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        yield session

    await engine.dispose()


@pytest_asyncio.fixture
async def client(db_session: AsyncSession) -> AsyncIterator[AsyncClient]:
    async def _override_get_db() -> AsyncIterator[AsyncSession]:
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def seeded_products(db_session: AsyncSession) -> list[Product]:
    """A small, deterministic catalog for product/cart/order tests —
    independent of the real seed_data.json."""
    products = [
        Product(
            id=1, name_en="Test Chinigura Rice 1kg", name_bn=None, category="Rice",
            price_bdt=190.0, unit="kg", unit_value=1.0, stock_qty=10, image_url=None,
        ),
        Product(
            id=2, name_en="Test Soyabean Oil 1Ltr", name_bn=None, category="Soybean Oil",
            price_bdt=199.0, unit="ltr", unit_value=1.0, stock_qty=0, image_url=None,
        ),
        Product(
            id=3, name_en="Test Eggs 12Pcs", name_bn=None, category="Eggs",
            price_bdt=150.0, unit="pcs", unit_value=12.0, stock_qty=5, image_url=None,
        ),
    ]
    db_session.add_all(products)
    await db_session.commit()
    return products


async def signup_user(client: AsyncClient, email: str = "test@example.com") -> str:
    """Convenience helper: signs up a fresh user, returns their access token."""
    r = await client.post(
        "/auth/signup",
        json={"email": email, "password": "password123", "name": "Test User"},
    )
    assert r.status_code == 200, r.text
    return r.json()["access_token"]
