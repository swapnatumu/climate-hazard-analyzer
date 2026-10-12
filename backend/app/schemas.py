from datetime import date
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

MIN_YEAR = 1940
MIN_SPAN_YEARS = 10
MAX_BBOX_DEGREES = 2.0


def last_complete_year() -> int:
    # ERA5 lags real time by a few days, so the current year is never complete.
    return date.today().year - 1


class AnalysisQuery(BaseModel):
    """Query parameters for /api/hazards/{hazard}. Every field is typed; nothing passes through."""

    model_config = {"extra": "forbid"}

    lat: float | None = Field(None, ge=-90, le=90)
    lon: float | None = Field(None, ge=-180, le=180)
    bbox: str | None = Field(
        None, max_length=100, description="minLon,minLat,maxLon,maxLat (max 2°×2°)"
    )
    start: int = Field(1990, ge=MIN_YEAR)
    end: int = Field(2020)
    percentile: int = Field(95, ge=90, le=99)
    min_days: int = Field(3, ge=2, le=7)
    threshold_mode: Literal["annual"] = "annual"  # "calendar_day" is a planned stretch goal

    @field_validator("bbox")
    @classmethod
    def _parse_bbox(cls, v: str | None) -> str | None:
        if v is None:
            return v
        parts = v.split(",")
        if len(parts) != 4:
            raise ValueError("bbox must be minLon,minLat,maxLon,maxLat")
        try:
            min_lon, min_lat, max_lon, max_lat = (float(p) for p in parts)
        except ValueError as e:
            raise ValueError("bbox values must be numbers") from e
        if not (-180 <= min_lon < max_lon <= 180 and -90 <= min_lat < max_lat <= 90):
            raise ValueError("bbox must have min < max and valid coordinates")
        if max_lon - min_lon > MAX_BBOX_DEGREES or max_lat - min_lat > MAX_BBOX_DEGREES:
            raise ValueError(f"bbox must be at most {MAX_BBOX_DEGREES}°×{MAX_BBOX_DEGREES}°")
        return f"{min_lon},{min_lat},{max_lon},{max_lat}"

    @model_validator(mode="after")
    def _check(self) -> "AnalysisQuery":
        has_point = self.lat is not None or self.lon is not None
        if has_point and (self.lat is None or self.lon is None):
            raise ValueError("lat and lon must be given together")
        if has_point == (self.bbox is not None):
            raise ValueError("give exactly one of lat/lon or bbox")
        if self.end > last_complete_year():
            raise ValueError(f"end must be at most {last_complete_year()}")
        if self.start >= self.end:
            raise ValueError("start must be before end")
        if self.end - self.start + 1 < MIN_SPAN_YEARS:
            raise ValueError(f"the range must span at least {MIN_SPAN_YEARS} years")
        return self

    @property
    def bbox_tuple(self) -> tuple[float, float, float, float] | None:
        if self.bbox is None:
            return None
        a, b, c, d = (float(p) for p in self.bbox.split(","))
        return a, b, c, d


class GeocodeQuery(BaseModel):
    model_config = {"extra": "forbid"}
    q: str = Field(..., min_length=2, max_length=100)
