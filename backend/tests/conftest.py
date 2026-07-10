"""
tests/conftest.py — Shared fixtures for the API test suite.

Every test runs against a fresh in-memory SQLite database, isolated from
the real seeded dev/prod database (core/database.py's own engine is never
touched here) — the FastAPI get_db dependency is overridden per test.
"""
import json
import uuid
from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from jose.exceptions import JWTError

import core.security
import models  # noqa: F401 — registers every model class with Base.metadata
from core.database import Base, get_db
from main import app
from models.product import Product


@pytest.fixture(autouse=True)
def _mock_supabase_token_verification(monkeypatch: pytest.MonkeyPatch) -> None:
    """Real tokens are ES256 JWTs verified against Supabase's live JWKS
    (core/security.py) — tests never hit that real external service.
    Instead, a test "token" (see make_test_token below) is just the JSON
    payload get_current_user actually reads (sub/email/user_metadata),
    and this fixture replaces real verification with a plain parse of
    that string. Mirrors the established pattern of mocking external-
    service boundaries in tests (core/test_llm.py for the LLM provider)."""

    async def fake_verify(token: str) -> dict:
        try:
            return json.loads(token)
        except json.JSONDecodeError as e:
            # get_current_user only knows how to handle JWTError from a
            # failed verification — a garbage test token needs to fail the
            # same way a garbage real token would (real jose.jwt.decode
            # raises JWTError, not JSONDecodeError, on malformed input).
            raise JWTError("invalid test token") from e

    monkeypatch.setattr(core.security, "verify_supabase_token", fake_verify)


def make_test_token(email: str = "test@example.com", name: str = "Test User") -> str:
    """A fake bearer token for a fresh synthetic user. Real signup/login
    happen against Supabase directly now, not this backend, so there's no
    endpoint here to call — the first authenticated request carrying this
    token lazily creates the corresponding profile row (see
    core/security.get_current_user)."""
    return json.dumps({"sub": str(uuid.uuid4()), "email": email, "user_metadata": {"name": name}})


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
    """Convenience helper: returns a bearer token for a fresh synthetic
    test user (see make_test_token)."""
    return make_test_token(email=email)
