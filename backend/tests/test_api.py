import httpx
import pandas as pd
import pytest

from app.config import Settings
from app.limiter import limiter
from app.main import Deps, create_app
from app.services.open_meteo import UpstreamError
from tests.fakes import FakeOpenMeteo, MemoryResultRepo, MemoryWeatherRepo


@pytest.fixture
async def ctx():
    limiter.reset()
    upstream = FakeOpenMeteo()
    app = create_app(Settings(), Deps(MemoryWeatherRepo(), MemoryResultRepo(), upstream))
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            yield client, upstream


async def test_health(ctx):
    client, _ = ctx
    r = await client.get("/health")
    assert r.status_code == 200


async def test_list_hazards_defaults_to_heatwave(ctx):
    client, _ = ctx
    r = await client.get("/api/hazards")
    assert r.json()["default"] == "heatwave"


async def test_heatwave_point_analysis_and_cache(ctx):
    client, upstream = ctx
    params = {"lat": 18.52, "lon": 73.86, "start": 1980, "end": 2020}
    r = await client.get("/api/hazards/heatwave", params=params)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["cache"] == "miss"
    assert body["region"]["cell"] == {"lat": 18.5, "lon": 73.75}
    assert len(body["yearly"]) == 41
    assert body["threshold"]["baseline"] == [1991, 2020]
    assert "insight" in body and body["insight"]
    assert body["data_quality"] == {"variable": "tmax", "days": 14976, "missing_days": 0,
                                    "incomplete_years": [], "out_of_range_removed": 0,
                                    "duplicates_removed": 0}
    # Synthetic data warms steadily, so the trend should be significant and upward.
    assert body["trend"]["direction"] == "increasing"
    calls = upstream.calls

    r2 = await client.get("/api/hazards/heatwave", params=params)
    assert r2.json()["cache"] == "hit"
    assert upstream.calls == calls  # cache hit makes no upstream call

    # Different range, same cell: raw data already cached, so still no upstream call.
    r3 = await client.get("/api/hazards/heatwave", params={**params, "start": 1995})
    assert r3.json()["cache"] == "miss"
    assert upstream.calls == calls


async def test_bbox_analysis(ctx):
    client, _ = ctx
    r = await client.get("/api/hazards/heatwave",
                         params={"bbox": "73.5,18.25,74.0,18.75", "start": 1990, "end": 2020})
    assert r.status_code == 200, r.text
    assert r.json()["region"]["type"] == "bbox"


@pytest.mark.parametrize("params,needle", [
    ({"lat": 18.5, "lon": 73.8, "start": 2010, "end": 2000}, "before"),
    ({"lat": 18.5, "lon": 73.8, "start": 2015, "end": 2020}, "at least 10"),
    ({"lat": 99, "lon": 73.8}, "less than or equal"),
    ({"lat": 18.5}, "together"),
    ({"lat": 18.5, "lon": 73.8, "bbox": "1,1,2,2"}, "exactly one"),
    ({"bbox": "70,10,75,15"}, "at most"),
    ({"lat": 18.5, "lon": 73.8, "start": 1930}, "greater than or equal"),
    ({"lat": 18.5, "lon": 73.8, "foo": "$ne"}, "Extra inputs"),
])
async def test_validation_errors_return_422(ctx, params, needle):
    client, _ = ctx
    r = await client.get("/api/hazards/heatwave", params=params)
    assert r.status_code == 422
    err = r.json()["error"]
    assert err["code"] == "VALIDATION_ERROR"
    assert needle in err["message"]


async def test_unknown_hazard_404(ctx):
    client, _ = ctx
    r = await client.get("/api/hazards/tornado", params={"lat": 1, "lon": 1})
    assert r.status_code == 404


async def test_csv_export(ctx):
    client, _ = ctx
    r = await client.get("/api/hazards/heatwave/export.csv",
                         params={"lat": 18.5, "lon": 73.8, "start": 1990, "end": 2020})
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/csv")
    assert "year,complete,event_count" in r.text


async def test_rate_limit_returns_429(ctx):
    client, _ = ctx
    statuses = [
        (await client.get("/api/geocode", params={"q": "pune"})).status_code for _ in range(61)
    ]
    assert statuses[-1] == 429


async def test_rate_limit_ignores_forged_forwarded_for(ctx):
    client, _ = ctx
    last = None
    for i in range(61):
        last = await client.get("/api/geocode", params={"q": "pune"},
                                headers={"X-Forwarded-For": f"10.0.0.{i}"})
    assert last.status_code == 429
    assert last.headers["retry-after"] == "60"


def test_client_ip_prefers_configured_proxy_header(monkeypatch):
    from starlette.requests import Request

    from app import limiter as lim

    scope = {"type": "http", "client": ("10.1.1.1", 1234),
             "headers": [(b"cf-connecting-ip", b"203.0.113.7"), (b"x-forwarded-for", b"6.6.6.6")]}
    assert lim.client_ip(Request(scope)) == "10.1.1.1"
    monkeypatch.setattr(lim, "get_settings", lambda: Settings(client_ip_header="CF-Connecting-IP"))
    assert lim.client_ip(Request(scope)) == "203.0.113.7"


async def test_presets_cover_every_state(ctx):
    client, _ = ctx
    body = (await client.get("/api/regions")).json()
    cities = body["cities"]
    assert {c["id"] for c in cities} >= {"hyderabad", "visakhapatnam", "mumbai", "new-delhi"}
    assert len({c["id"] for c in cities}) == len(cities)
    assert len({c["state"] for c in cities}) == 36  # 28 states + 8 union territories
    # Rough bounding box of India, including the island territories.
    assert all(6 <= c["lat"] <= 36 and 68 <= c["lon"] <= 98 for c in cities)


async def test_upstream_rate_limit_returns_503_with_retry_after(ctx):
    client, upstream = ctx

    async def limited(*args, **kwargs):
        raise UpstreamError("quota used up", rate_limited=True)

    upstream.fetch_daily = limited
    r = await client.get("/api/hazards/heatwave", params={"lat": 18.5, "lon": 73.75})
    assert r.status_code == 503
    assert r.headers["retry-after"] == "60"
    assert r.json()["error"]["code"] == "UPSTREAM_RATE_LIMITED"


@pytest.mark.parametrize("hazard,metric", [("drought", "max_dry_spell"), ("rainfall", "heavy_days")])
async def test_other_hazards_analyze_and_export(ctx, hazard, metric):
    client, _ = ctx
    params = {"lat": 18.5, "lon": 73.8, "start": 1990, "end": 2020}
    r = await client.get(f"/api/hazards/{hazard}", params=params)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["primary_metric"] == metric
    assert body["yearly"][0][metric] is not None
    assert len(body["seasonality"]["periods"]) == 2
    assert len(body["seasonality"]["periods"][0]["values"]) == 12
    csv = await client.get(f"/api/hazards/{hazard}/export.csv", params=params)
    assert f"year,complete,{metric}" in csv.text


async def test_unused_params_share_one_cached_result(ctx):
    client, _ = ctx
    base = {"lat": 18.5, "lon": 73.8, "start": 1990, "end": 2020}
    first = (await client.get("/api/hazards/drought", params=base)).json()
    # Drought ignores percentile and min_days, so changing them must not recompute.
    second = (await client.get("/api/hazards/drought", params={**base, "percentile": 99, "min_days": 5})).json()
    assert second["cache"] == "hit"
    assert second["id"] == first["id"]


async def test_data_quality_reports_removed_and_missing_values(ctx):
    client, upstream = ctx
    clean = upstream.fetch_daily

    async def noisy(lat, lon, start, end):
        df = await clean(lat, lon, start, end)
        df.loc[df["date"] == "2000-06-01", "tmax"] = 99.0   # outlier -> NaN
        df.loc[df["date"] == "2001-06-01", "tmax"] = None   # gap
        dup = df[df["date"] == "2002-06-01"]
        return pd.concat([df, dup], ignore_index=True)       # duplicate date

    upstream.fetch_daily = noisy
    params = {"lat": 18.5, "lon": 73.75, "start": 1995, "end": 2010}
    dq = (await client.get("/api/hazards/heatwave", params=params)).json()["data_quality"]
    assert dq["out_of_range_removed"] == 1
    assert dq["duplicates_removed"] == 1
    assert dq["missing_days"] == 2  # the gap plus the removed outlier
    # Served again from the raw cache: the counts come from the stored documents.
    dq2 = (await client.get("/api/hazards/heatwave", params={**params, "start": 1996})).json()["data_quality"]
    assert dq2["out_of_range_removed"] == 1 and dq2["duplicates_removed"] == 1
