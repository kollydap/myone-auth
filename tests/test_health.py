import asyncio
import pytest
from httpx import ASGITransport, AsyncClient
from myone_auth.main import app


@pytest.mark.asyncio
async def test_sleep_returns():
    await asyncio.sleep(0)
    assert True


@pytest.mark.asyncio
async def test_root():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://0.0.0.0:8000"
    ) as ac:
        response = await ac.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
