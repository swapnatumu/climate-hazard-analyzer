from datetime import date

import httpx
import pytest

from app.config import Settings
from app.services.open_meteo import OpenMeteoClient, UpstreamError


def _client(handler) -> OpenMeteoClient:
    return OpenMeteoClient(Settings(), httpx.AsyncClient(transport=httpx.MockTransport(handler)))


async def test_rate_limit_fails_fast_without_retry():
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(429, json={"error": True, "reason": "Minutely API request limit exceeded."})

    with pytest.raises(UpstreamError) as e:
        await _client(handler).fetch_daily(17.5, 78.5, date(2000, 1, 1), date(2000, 12, 31))
    assert e.value.rate_limited
    assert calls == 1


async def test_missing_daily_block_is_an_upstream_error():
    with pytest.raises(UpstreamError):
        await _client(lambda r: httpx.Response(200, json={})).fetch_daily(
            17.5, 78.5, date(2000, 1, 1), date(2000, 12, 31))
