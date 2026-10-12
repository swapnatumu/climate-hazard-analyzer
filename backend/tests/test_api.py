import httpx
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


async def test_presets_are_valid_regions(ctx):
    client, _ = ctx
    body = (await client.get("/api/regions")).json()
    assert {c["id"] for c in body["cities"]} >= {"hyderabad", "visakhapatnam"}
    # Every preset area must pass the API's own bbox validation.
    for a in body["areas"]:
        r = await client.get("/api/hazards/heatwave",
                             params={"bbox": ",".join(map(str, a["bbox"])), "start": 1990, "end": 2020})
        assert r.status_code == 200, (a["id"], r.text)


async def test_upstream_rate_limit_returns_503_with_retry_after(ctx):
    client, upstream = ctx

    async def limited(*args, **kwargs):
        raise UpstreamError("quota used up", rate_limited=True)

    upstream.fetch_daily = limited
    r = await client.get("/api/hazards/heatwave", params={"lat": 18.5, "lon": 73.75})
    assert r.status_code == 503
    assert r.headers["retry-after"] == "60"
    assert r.json()["error"]["code"] == "UPSTREAM_RATE_LIMITED"
