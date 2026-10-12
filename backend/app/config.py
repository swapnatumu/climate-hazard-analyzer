from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """App settings, read from environment variables or backend/.env."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    mongodb_uri: str = "mongodb://localhost:27017"
    mongodb_db: str = "climate"
    # Comma-separated list, e.g. "http://localhost:5173,https://my-app.vercel.app"
    allowed_origins: str = "http://localhost:5173"

    # Bump this whenever hazard logic changes; it invalidates cached analyses.
    algo_version: str = "1.0.0"

    # Fixed WMO climate normal used for percentile thresholds.
    baseline_start: int = 1991
    baseline_end: int = 2020

    # Open-Meteo access
    open_meteo_archive_url: str = "https://archive-api.open-meteo.com/v1/archive"
    open_meteo_geocode_url: str = "https://geocoding-api.open-meteo.com/v1/search"
    upstream_timeout_s: float = 10.0
    upstream_max_concurrency: int = 4
    upstream_max_retries: int = 3

    # Per-client rate limits (slowapi syntax)
    rate_limit_analysis: str = "30/minute"
    rate_limit_geocode: str = "60/minute"

    @property
    def origins(self) -> list[str]:
        return [o.strip() for o in self.allowed_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
