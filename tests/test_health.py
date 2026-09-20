import asyncio
import time

import pytest
from fastapi import Depends, FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

from myone_auth.core.config import get_settings
from myone_auth.core.database import engine, session_factory
from myone_auth.deps import get_db
from myone_auth.main import app

# One event loop for the whole file: the module-level engine pool outlives
# per-test loops, so a pooled connection would otherwise belong to a closed loop.
pytestmark = pytest.mark.asyncio(loop_scope="session")

# Throwaway app that exists only to exercise get_db. It is not the real app.
throwaway_app = FastAPI()


@throwaway_app.get("/db-ping")
async def db_ping(db: AsyncSession = Depends(get_db), number: int = 1):
    result = await db.execute(text("SELECT 1"))
    return {"value": result.scalar_one()}


@throwaway_app.get("/echo")
async def echo(n: int, db: AsyncSession = Depends(get_db)):
    # CAST because asyncpg can't infer the type of a bare bound parameter.
    result = await db.execute(text("SELECT CAST(:n AS INTEGER)"), {"n": n})
    return {"n": result.scalar_one()}


# Deliberately WRONG: one session created at import time and shared by every
# request. Exists only so test_module_global_session_breaks_under_concurrency
# can watch it fail.
global_session = session_factory()


@throwaway_app.get("/broken")
async def broken(n: int):
    result = await global_session.execute(
        text("SELECT CAST(:n AS INTEGER) FROM pg_sleep(0.05)"), {"n": n}
    )
    return {"n": result.scalar_one()}


async def test_sleep_returns():
    await asyncio.sleep(0)
    assert True


async def test_root():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        response = await ac.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


async def test_get_db_gives_a_working_session():
    async with AsyncClient(
        transport=ASGITransport(app=throwaway_app), base_url="http://test"
    ) as ac:
        response = await ac.get("/db-ping")
    assert response.status_code == 200
    assert response.json() == {"value": 1}


async def test_50_concurrent_requests_each_get_their_own_value():
    async with AsyncClient(
        transport=ASGITransport(app=throwaway_app), base_url="http://test"
    ) as ac:
        responses = await asyncio.gather(
            *(ac.get("/echo", params={"n": i}) for i in range(50))
        )
    assert all(r.status_code == 200 for r in responses)
    assert [r.json()["n"] for r in responses] == list(range(50))


async def test_module_global_session_breaks_under_concurrency():
    try:
        async with AsyncClient(
            transport=ASGITransport(app=throwaway_app), base_url="http://test"
        ) as ac:
            results = await asyncio.gather(
                *(ac.get("/broken", params={"n": i}) for i in range(50)),
                return_exceptions=True,
            )
    finally:
        await global_session.rollback()
        await global_session.close()

    failures = [
        r for r in results if isinstance(r, Exception) or r.status_code != 200
    ]
    # A cold shared session is caught by SQLAlchemy's own concurrency guard.
    # (A warm one doesn't crash: the driver adapter serializes calls on the one
    # connection, so 50 requests silently queue instead. Still wrong, just slower.)
    assert any("concurrent operations are not permitted" in str(f) for f in failures)


# --- Acceptance 3: pool exhaustion -----------------------------------------

HOLD_SECONDS = 1


async def test_exhausted_pool_makes_requests_wait_in_line():
    # Two connections, no overflow. Five requests each hold a session for 1s.
    small_engine = create_async_engine(
        get_settings().database_url.get_secret_value(),
        pool_size=2,
        max_overflow=0,
    )
    small_factory = async_sessionmaker(small_engine, expire_on_commit=False)
    pool_app = FastAPI()

    async def small_get_db():
        async with small_factory() as session:
            yield session

    @pool_app.get("/hold")
    async def hold(db: AsyncSession = Depends(small_get_db)):
        await db.execute(text("SELECT 1"))
        await asyncio.sleep(HOLD_SECONDS)  # session (and its connection) held
        return {"ok": True}

    try:
        async with AsyncClient(
            transport=ASGITransport(app=pool_app), base_url="http://test"
        ) as ac:
            start = time.monotonic()
            responses = await asyncio.gather(*(ac.get("/hold") for _ in range(5)))
            elapsed = time.monotonic() - start
    finally:
        await small_engine.dispose()

    assert all(r.status_code == 200 for r in responses)
    # 5 requests through 2 connections = 3 waves of 1s. Nobody fails (the wait is
    # well under pool_timeout=30s); they queue instead.
    assert elapsed >= 3 * HOLD_SECONDS - 0.1


# --- Acceptance 4: recovery after the database drops our connections -------


async def _open_and_return_connections(eng, n=3):
    """Fill the pool with n live connections; return their Postgres backend pids."""
    conns = [await eng.connect() for _ in range(n)]
    pids = [
        (await c.execute(text("SELECT pg_backend_pid()"))).scalar_one() for c in conns
    ]
    for c in conns:
        await c.close()  # back to the pool, still open
    return pids


async def _kill_backends(pids):
    """Simulate an outage: the server drops exactly these connections."""
    killer = create_async_engine(
        get_settings().database_url.get_secret_value(), poolclass=NullPool
    )
    try:
        async with killer.connect() as c:
            for pid in pids:
                await c.execute(
                    text("SELECT pg_terminate_backend(CAST(:pid AS INTEGER))"),
                    {"pid": pid},
                )
    finally:
        await killer.dispose()
    await asyncio.sleep(0.3)  # let the client side notice the closures


async def test_pool_pre_ping_recovers_after_connections_die():
    pids = await _open_and_return_connections(engine)
    await _kill_backends(pids)

    async with session_factory() as session:  # the app's real engine, pre_ping=True
        result = await session.execute(text("SELECT 1"))
    assert result.scalar_one() == 1


async def test_without_pre_ping_first_request_after_outage_fails():
    eng = create_async_engine(
        get_settings().database_url.get_secret_value(),
        pool_size=5,
        pool_pre_ping=False,
    )
    try:
        pids = await _open_and_return_connections(eng)
        await _kill_backends(pids)

        with pytest.raises(DBAPIError):  # first request eats the dead connection
            async with async_sessionmaker(eng)() as session:
                await session.execute(text("SELECT 1"))

        async with async_sessionmaker(eng)() as session:  # pool has recovered
            assert (await session.execute(text("SELECT 1"))).scalar_one() == 1
    finally:
        await eng.dispose()
