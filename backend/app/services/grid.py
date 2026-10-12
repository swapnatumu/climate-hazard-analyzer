"""Snapping coordinates to the ERA5 0.25° grid so nearby requests share cache entries."""

from dataclasses import dataclass

import numpy as np

GRID_STEP = 0.25
MAX_BBOX_POINTS_PER_AXIS = 5  # at most 5x5 = 25 sampled cells


@dataclass(frozen=True, order=True)
class Cell:
    lat: float
    lon: float

    @property
    def key(self) -> str:
        return f"{self.lat:.2f}_{self.lon:.2f}"

    def to_dict(self) -> dict[str, float]:
        return {"lat": self.lat, "lon": self.lon}


def snap(value: float) -> float:
    return round(round(value / GRID_STEP) * GRID_STEP, 2)


def snap_point(lat: float, lon: float) -> Cell:
    return Cell(lat=snap(lat), lon=snap(lon))


def bbox_cells(min_lon: float, min_lat: float, max_lon: float, max_lat: float) -> list[Cell]:
    """Sample up to 5x5 evenly spaced points in the box, snapped and de-duplicated."""
    lats = np.linspace(min_lat, max_lat, MAX_BBOX_POINTS_PER_AXIS)
    lons = np.linspace(min_lon, max_lon, MAX_BBOX_POINTS_PER_AXIS)
    cells = {snap_point(float(la), float(lo)) for la in lats for lo in lons}
    return sorted(cells)
