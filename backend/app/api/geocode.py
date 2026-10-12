import time
from collections import OrderedDict
from typing import Annotated

from fastapi import APIRouter, Query, Request

from app.config import get_settings
from app.limiter import limiter
from app.schemas import GeocodeQuery

router = APIRouter(prefix="/api", tags=["geocode"])
settings = get_settings()

_CACHE_TTL_S = 24 * 3600
_CACHE_MAX = 1000
_cache: OrderedDict[str, tuple[float, list[dict]]] = OrderedDict()


@router.get("/geocode")
@limiter.limit(settings.rate_limit_geocode)
async def geocode(request: Request, params: Annotated[GeocodeQuery, Query()]) -> dict:
    key = params.q.strip().lower()
    hit = _cache.get(key)
    if hit and time.monotonic() - hit[0] < _CACHE_TTL_S:
        _cache.move_to_end(key)
        return {"results": hit[1], "cache": "hit"}

    results = await request.app.state.upstream.geocode(params.q.strip())
    _cache[key] = (time.monotonic(), results)
    if len(_cache) > _CACHE_MAX:
        _cache.popitem(last=False)
    return {"results": results, "cache": "miss"}
