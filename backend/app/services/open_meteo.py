"""Safe access to Open-Meteo: timeouts, bounded concurrency, retries with backoff + jitter."""

import asyncio
import logging
from datetime import date

import httpx
import pandas as pd
from tenacity import (
    AsyncRetrying,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential_jitter,
)

from app.config import Settings

log = logging.getLogger(__name__)

DAILY_VARS = {
    "temperature_2m_max": "tmax",
    "temperature_2m_min": "tmin",
    "precipitation_sum": "prcp",
}


class UpstreamError(Exception):
    """Upstream API failed (maps to 502) or timed out (maps to 504)."""

    def __init__(self, message: str, timeout: bool = False):
        super().__init__(message)
        self.timeout = timeout


def _retryable(exc: BaseException) -> bool:
    if isinstance(exc, (httpx.TimeoutException, httpx.TransportError)):
        return True
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code == 429 or exc.response.status_code >= 500
    return False


class OpenMeteoClient:
    def __init__(self, settings: Settings, http: httpx.AsyncClient | None = None):
        self.settings = settings
        self.http = http or httpx.AsyncClient(timeout=settings.upstream_timeout_s)
        self._sem = asyncio.Semaphore(settings.upstream_max_concurrency)

    async def aclose(self) -> None:
        await self.http.aclose()

    async def _get(self, url: str, params: dict) -> dict:
        try:
            async for attempt in AsyncRetrying(
                retry=retry_if_exception(_retryable),
                stop=stop_after_attempt(self.settings.upstream_max_retries),
                wait=wait_exponential_jitter(initial=1, max=8),
                reraise=True,
            ):
                with attempt:
                    async with self._sem:
                        resp = await self.http.get(url, params=params)
                    resp.raise_for_status()
                    return resp.json()
        except httpx.TimeoutException as e:
            raise UpstreamError("Weather data provider timed out", timeout=True) from e
        except httpx.HTTPError as e:
            log.warning("open-meteo request failed: %s", e)
            raise UpstreamError("Weather data provider is unavailable") from e
        raise AssertionError("unreachable")

    async def fetch_daily(self, lat: float, lon: float, start: date, end: date) -> pd.DataFrame:
        """Daily Tmax/Tmin/precip for one grid cell, as a frame with a `date` column."""
        params = {
            "latitude": lat,
            "longitude": lon,
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
            "daily": ",".join(DAILY_VARS),
            "timezone": "auto",
            "temperature_unit": "celsius",
            "precipitation_unit": "mm",
        }
        data = await self._get(self.settings.open_meteo_archive_url, params)
        daily = data.get("daily") or {}
        if "time" not in daily:
            raise UpstreamError("Weather data provider returned no daily data")
        df = pd.DataFrame({"date": daily["time"]})
        for src, dst in DAILY_VARS.items():
            df[dst] = daily.get(src, [None] * len(df))
        return df

    async def geocode(self, query: str, count: int = 8) -> list[dict]:
        # httpx URL-encodes params; the query is already length-capped by the schema.
        data = await self._get(
            self.settings.open_meteo_geocode_url,
            {"name": query, "count": count, "language": "en", "format": "json"},
        )
        return [
            {
                "name": r.get("name"),
                "admin1": r.get("admin1"),
                "country": r.get("country"),
                "lat": r.get("latitude"),
                "lon": r.get("longitude"),
            }
            for r in data.get("results") or []
        ]
