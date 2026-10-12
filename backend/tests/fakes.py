"""In-memory stand-ins for Mongo and Open-Meteo, used by API tests."""

from datetime import date

import numpy as np
import pandas as pd

from app.services.grid import Cell


class MemoryWeatherRepo:
    def __init__(self):
        self.docs: dict[str, dict] = {}

    async def get_years(self, cell: Cell, years: list[int]) -> dict[int, dict]:
        return {y: self.docs[f"{cell.key}_{y}"] for y in years if f"{cell.key}_{y}" in self.docs}

    async def upsert_years(self, docs: list[dict]) -> None:
        for d in docs:
            self.docs[d["_id"]] = d


class MemoryResultRepo:
    def __init__(self):
        self.docs: dict[str, dict] = {}

    async def get(self, key: str) -> dict | None:
        d = self.docs.get(key)
        return dict(d) if d else None

    async def put(self, doc: dict) -> None:
        self.docs[doc["_id"]] = dict(doc)


class FakeOpenMeteo:
    """Synthetic climate: seasonal cycle + noise + a warming trend of 0.05 °C/year."""

    def __init__(self, warming_per_year: float = 0.05):
        self.calls = 0
        self.warming = warming_per_year

    async def fetch_daily(self, lat, lon, start: date, end: date) -> pd.DataFrame:
        self.calls += 1
        dates = pd.date_range(start, end, freq="D")
        rng = np.random.default_rng(int(abs(lat * 100 + lon)) + start.year)
        doy = dates.dayofyear.to_numpy()
        seasonal = 30 + 8 * np.sin(2 * np.pi * (doy - 100) / 365)
        trend = self.warming * (dates.year.to_numpy() - 1940)
        # AR(1) noise: real weather is persistent, so hot days cluster into spells.
        eps = rng.normal(0, 1.2, len(dates))
        noise = np.empty(len(dates))
        noise[0] = eps[0]
        for i in range(1, len(dates)):
            noise[i] = 0.8 * noise[i - 1] + eps[i]
        tmax = seasonal + trend + noise
        return pd.DataFrame({
            "date": dates.strftime("%Y-%m-%d"),
            "tmax": tmax.round(1),
            "tmin": (tmax - 10).round(1),
            "prcp": np.clip(rng.gamma(0.5, 4, len(dates)), 0, None).round(1),
        })

    async def geocode(self, query: str, count: int = 8) -> list[dict]:
        self.calls += 1
        return [{"name": "Pune", "admin1": "Maharashtra", "country": "India",
                 "lat": 18.52, "lon": 73.86}]

    async def aclose(self):
        pass
