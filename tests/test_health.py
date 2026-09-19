import asyncio
import pytest



@pytest.mark.asyncio
async def test_sleep_returns():
    await asyncio.sleep(0)
    assert True
