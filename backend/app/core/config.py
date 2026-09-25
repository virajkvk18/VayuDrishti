"""Core configuration module for VayuDRISHTI Atmospheric Diagnostic Engine."""
from typing import List

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    PROJECT_NAME: str = "VayuDRISHTI Atmospheric Diagnostic Engine"
    VERSION: str = "3.0.0"
    API_V1_STR: str = "/api/v1"
    NWP_MODEL_BASE: str = "NCMRWF-Irrespective Diagnostic v3.0"
    BACKEND_HOST: str = "0.0.0.0"
    BACKEND_PORT: int = 8000

    # CORS Configuration — explicit origins only. A wildcard origin is
    # incompatible with credentialed requests and is rejected by browsers,
    # so it is never emitted (see `cors_origin_validator`).
    CORS_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3001",
    ]

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def cors_origin_validator(cls, v):
        if isinstance(v, str):
            v = [v]
        origins = [str(o).strip() for o in v if str(o).strip()]
        wildcards = [o for o in origins if o == "*"]
        if wildcards:
            # A bare wildcard combined with allow_credentials=True is invalid
            # per the CORS spec. Fall back to the local dev origins instead of
            # silently producing a browser-rejected configuration.
            return [
                "http://localhost:3000",
                "http://127.0.0.1:3000",
                "http://localhost:3001",
                "http://127.0.0.1:3001",
            ]
        return origins

    # Optional regex for origins that cannot be enumerated ahead of time.
    # Every Vercel preview deployment gets a unique subdomain, so listing them in
    # CORS_ORIGINS is impossible. Set this to `https://.*\.vercel\.app` to allow
    # production and preview frontends to call the API. It is anchored, so it
    # cannot be abused to match an arbitrary host.
    CORS_ORIGIN_REGEX: str = ""

    # Atmospheric Domain Boundaries (India Region)
    LAT_MIN: float = 8.0
    LAT_MAX: float = 37.0
    LON_MIN: float = 68.0
    LON_MAX: float = 97.0

    # Forecast lead-time bounds (Day 1 to Day 10)
    LEAD_DAY_MIN: int = 1
    LEAD_DAY_MAX: int = 10

    # Risk classification thresholds applied to the calibrated bust probability
    BUST_RISK_HIGH_THRESHOLD: float = 0.65
    BUST_RISK_MODERATE_THRESHOLD: float = 0.35

    # Operational definition of a "forecast bust": 24h accumulated precipitation
    # verification error exceeding this many millimetres.
    BUST_ERROR_THRESHOLD_MM: float = 25.0

    # Background sample sizes for exact interventional Shapley attribution.
    # The station inspector uses the full sample; the 20-region grid uses a
    # smaller one because it re-attributes every cell on each lead-day change.
    SHAP_BACKGROUND_SAMPLES: int = 24
    GRID_SHAP_BACKGROUND_SAMPLES: int = 8

    # AI Synoptic Briefing (optional; deterministic advisory is always produced)
    ENABLE_AI_BRIEFING: bool = False
    GEMINI_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-2.5-flash"

    # Optional External Atmospheric Data Sources
    OPENWEATHER_API_KEY: str = ""
    ECMWF_API_KEY: str = ""
    NOAA_NOMADS_BASE_URL: str = "https://nomads.ncep.noaa.gov/dods/gfs_0p25"
    OPEN_METEO_BASE_URL: str = "https://api.open-meteo.com/v1/forecast"

    # Trained model artifacts. Empty string resolves to the package `ml_models`
    # directory that ships with the backend.
    MODEL_ARTIFACT_DIR: str = ""

    model_config = SettingsConfigDict(
        case_sensitive=True,
        # `.env.local` is loaded second and therefore overrides `.env`, letting
        # real credentials stay out of version control.
        env_file=(".env", ".env.local"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def resolved_artifact_dir(self) -> str:
        if self.MODEL_ARTIFACT_DIR.strip():
            return self.MODEL_ARTIFACT_DIR.strip()
        from pathlib import Path

        return str(Path(__file__).resolve().parent.parent / "ml_models")


settings = Settings()
