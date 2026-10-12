import csv
import io
from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query, Request
from fastapi.responses import StreamingResponse

from app.config import get_settings
from app.errors import ApiError
from app.hazards.registry import HAZARDS
from app.limiter import limiter
from app.schemas import AnalysisQuery
from app.services.analysis import AnalysisService

router = APIRouter(prefix="/api/hazards", tags=["hazards"])
settings = get_settings()

HazardKey = Annotated[str, Path(max_length=32, pattern=r"^[a-z_]+$")]


def get_service(request: Request) -> AnalysisService:
    return request.app.state.analysis


def _check_hazard(hazard: str) -> None:
    if hazard not in HAZARDS:
        raise ApiError(404, "UNKNOWN_HAZARD", f"Unknown hazard '{hazard}'. See /api/hazards.")


def _public(result: dict) -> dict:
    out = {k: v for k, v in result.items() if k != "_id"}
    out["id"] = result.get("_id")
    return out


@router.get("")
async def list_hazards() -> dict:
    return {
        "hazards": [
            {"key": h.key, "label": h.label, "variables": h.variables,
             "defaults": h.default_params(), "uses": list(h.uses), "primary_metric": h.primary_metric}
            for h in HAZARDS.values()
        ],
        "baseline": [settings.baseline_start, settings.baseline_end],
        "default": "heatwave",
    }


@router.get("/{hazard}")
@limiter.limit(settings.rate_limit_analysis)
async def analyze(
    request: Request,
    hazard: HazardKey,
    q: Annotated[AnalysisQuery, Query()],
    svc: AnalysisService = Depends(get_service),
) -> dict:
    _check_hazard(hazard)
    return _public(await svc.analyze(hazard, q))


@router.get("/{hazard}/export.csv")
@limiter.limit(settings.rate_limit_analysis)
async def export_csv(
    request: Request,
    hazard: HazardKey,
    q: Annotated[AnalysisQuery, Query()],
    svc: AnalysisService = Depends(get_service),
) -> StreamingResponse:
    _check_hazard(hazard)
    result = await svc.analyze(hazard, q)
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow([f"# {result['insight']}"])
    th = result["threshold"]
    w.writerow([f"# threshold {th['value']} {th['unit']} ({th['description']}, "
                f"baseline {th['baseline'][0]}-{th['baseline'][1]}), source {result['source']}"])
    dq = result["data_quality"]
    w.writerow([f"# data quality: {dq['missing_days']} of {dq['days']} days missing ({dq['variable']}), "
                f"{dq['out_of_range_removed']} out-of-range values and "
                f"{dq['duplicates_removed']} duplicate dates removed"])
    rows = result["yearly"]
    w.writerow(rows[0].keys())
    for r in rows:
        w.writerow(["" if v is None else v for v in r.values()])
    buf.seek(0)
    name = f"{hazard}_{q.start}_{q.end}.csv"
    return StreamingResponse(
        iter([buf.getvalue()]), media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{name}"'},
    )
