import logging
from contextlib import asynccontextmanager
from dataclasses import dataclass

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import geocode, hazards
from app.config import Settings, get_settings
from app.db.mongo import create_client, ensure_indexes
from app.db.repositories import MongoResultRepo, MongoWeatherRepo, ResultRepo, WeatherRepo
from app.errors import register_error_handlers
from app.limiter import limiter
from app.regions import CITIES
from app.services.analysis import AnalysisService
from app.services.open_meteo import OpenMeteoClient

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


@dataclass
class Deps:
    """Injectable dependencies; tests pass fakes instead of Mongo and Open-Meteo."""

    weather: WeatherRepo
    results: ResultRepo
    upstream: OpenMeteoClient


def create_app(settings: Settings | None = None, deps: Deps | None = None) -> FastAPI:
    settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        client = None
        d = deps
        if d is None:
            client = create_client(settings)
            db = client[settings.mongodb_db]
            await ensure_indexes(db)
            d = Deps(MongoWeatherRepo(db), MongoResultRepo(db), OpenMeteoClient(settings))
        app.state.upstream = d.upstream
        app.state.analysis = AnalysisService(settings, d.weather, d.results, d.upstream)
        yield
        if client is not None:
            await d.upstream.aclose()
            await client.close()

    app = FastAPI(title="Climate Hazard Trend Analyzer", version=settings.algo_version,
                  lifespan=lifespan)
    app.state.limiter = limiter
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.origins,
        allow_methods=["GET"],
        allow_headers=["*"],
    )
    register_error_handlers(app)
    app.include_router(hazards.router)
    app.include_router(geocode.router)

    @app.get("/health", tags=["meta"])
    async def health() -> dict:
        return {"status": "ok", "algo_version": settings.algo_version}

    @app.get("/api/regions", tags=["meta"])
    async def regions() -> dict:
        """Preset cities: the main cities of every Indian state and union territory."""
        return {"cities": CITIES}

    return app


app = create_app()
