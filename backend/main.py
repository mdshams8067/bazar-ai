"""main.py — FastAPI application entrypoint."""
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse

from core.config import CORS_ORIGINS, ENV
from core.database import Base, engine
from routers import auth, cart, chat, orders, products

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    # create_all is dev-only convenience; production relies on Alembic
    # migrations (see alembic/), never on this.
    if ENV == "local":
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    yield


app = FastAPI(title="Bazar AI API", lifespan=lifespan)

# CORS_ORIGINS is env-driven (.env) — never hardcode "*" here; local dev
# can set CORS_ORIGINS=* in its own .env if needed, but that choice lives
# in the environment, not the code.
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(products.router)
app.include_router(cart.router)
app.include_router(orders.router)
app.include_router(chat.router)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Catches anything not already handled as an HTTPException — logs the
    real error server-side, never leaks a raw traceback to the client."""
    logger.exception(f"Unhandled error on {request.method} {request.url.path}")
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Internal server error"},
    )


@app.get("/health")
async def health() -> dict[str, str]:
    """Cheap endpoint, no DB call — the frontend pings this to detect the
    free-tier cold-start wake-up (~50s after inactivity)."""
    return {"status": "ok"}


@app.get("/")
async def root() -> RedirectResponse:
    return RedirectResponse(url="/docs")
