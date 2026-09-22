import asyncio
import json
import logging
import sys

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from myone_auth.core.logging import JsonFormatter, RequestIdFilter, request_id_ctx
from myone_auth.core.middleware import RequestIdMiddleware

app = FastAPI()
app.add_middleware(RequestIdMiddleware)


@app.get("/whoami")
async def whoami():
    return {"request_id": request_id_ctx.get()}


@app.get("/boom")
async def boom():
    raise RuntimeError("boom")


def client(**kwargs):
    return AsyncClient(transport=ASGITransport(app=app, **kwargs), base_url="http://test")


def make_record(msg="hello", exc_info=None, **extra):
    record = logging.LogRecord("t", logging.INFO, __file__, 1, msg, (), exc_info)
    record.__dict__.update(extra)
    return record


# --- request ID middleware ---------------------------------------------------


@pytest.mark.asyncio
async def test_every_response_carries_a_request_id_the_handler_can_see():
    async with client() as ac:
        response = await ac.get("/whoami")
    header = response.headers["x-request-id"]
    assert header
    assert response.json()["request_id"] == header


@pytest.mark.asyncio
async def test_a_well_formed_client_supplied_id_is_kept():
    async with client() as ac:
        response = await ac.get("/whoami", headers={"X-Request-ID": "trace-abc_123.4"})
    assert response.headers["x-request-id"] == "trace-abc_123.4"


@pytest.mark.parametrize(
    "bad_id",
    [
        "x" * 65,  # too long
        "has space",
        "<script>alert(1)</script>",
        'quote"inside',
        "semi;colon",
        "",
    ],
)
@pytest.mark.asyncio
async def test_a_malformed_client_supplied_id_is_replaced_not_echoed(bad_id):
    async with client() as ac:
        response = await ac.get("/whoami", headers={"X-Request-ID": bad_id})
    assert response.headers["x-request-id"] != bad_id
    assert len(response.headers["x-request-id"]) == 32  # uuid4 hex


@pytest.mark.asyncio
async def test_concurrent_requests_never_see_each_others_ids():
    async with client() as ac:
        responses = await asyncio.gather(*(ac.get("/whoami") for _ in range(50)))
    ids = [r.headers["x-request-id"] for r in responses]
    assert len(set(ids)) == 50
    assert all(r.json()["request_id"] == r.headers["x-request-id"] for r in responses)


@pytest.mark.asyncio
async def test_the_id_does_not_outlive_its_request():
    async with client() as ac:
        await ac.get("/whoami")
    assert request_id_ctx.get() is None


@pytest.mark.asyncio
async def test_the_id_is_reset_even_when_the_handler_raises():
    async with client(raise_app_exceptions=False) as ac:
        response = await ac.get("/boom")
    assert response.status_code == 500
    assert request_id_ctx.get() is None


@pytest.mark.asyncio
async def test_access_log_has_the_path_but_never_the_query_string(caplog):
    caplog.set_level(logging.INFO, logger="myone_auth.access")
    async with client() as ac:
        await ac.get("/whoami", params={"code": "SECRETCODE", "state": "SECRETSTATE"})

    records = [r for r in caplog.records if r.name == "myone_auth.access"]
    assert len(records) == 1
    assert records[0].path == "/whoami"
    assert records[0].status == 200
    assert "SECRET" not in json.dumps(records[0].__dict__, default=str)


@pytest.mark.asyncio
async def test_a_failed_request_is_still_logged_as_500(caplog):
    caplog.set_level(logging.INFO, logger="myone_auth.access")
    async with client(raise_app_exceptions=False) as ac:
        await ac.get("/boom")
    records = [r for r in caplog.records if r.name == "myone_auth.access"]
    assert [r.status for r in records] == [500]


# --- JSON formatter ----------------------------------------------------------


def test_a_log_line_is_one_json_object_with_the_expected_keys():
    line = JsonFormatter().format(make_record("hi", method="GET", status=200))
    data = json.loads(line)
    assert {"timestamp", "level", "logger", "message"} <= data.keys()
    assert data["message"] == "hi"
    assert data["method"] == "GET"
    assert data["status"] == 200


def test_newlines_in_a_message_cannot_forge_a_second_log_line():
    line = JsonFormatter().format(make_record("ok\n" + '{"level":"CRITICAL","message":"forged"}'))
    assert "\n" not in line
    assert json.loads(line)["level"] == "INFO"


def test_exceptions_are_serialised_into_the_line():
    try:
        raise ValueError("bad")
    except ValueError:
        record = make_record("failed", exc_info=sys.exc_info())
    data = json.loads(JsonFormatter().format(record))
    assert "ValueError: bad" in data["exc_info"]


def test_the_filter_stamps_the_current_id_and_null_outside_a_request():
    record = make_record()
    RequestIdFilter().filter(record)
    assert record.request_id is None

    token = request_id_ctx.set("abc123")
    try:
        RequestIdFilter().filter(record)
    finally:
        request_id_ctx.reset(token)
    assert record.request_id == "abc123"
