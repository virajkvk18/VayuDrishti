"""VayuDRISHTI FastAPI application server."""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.endpoints import router as api_router
from app.core.config import settings
from app.core.ml_engine import ml_engine

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description=(
        "AI-based forecast bust detection for Day 1 to Day 10 medium-range NWP "
        "guidance over the Indian domain. Serves a region-wise confidence map, "
        "calibrated bust probabilities, error-prone area detection and exact "
        "Shapley explanations of the meteorological drivers behind low confidence."
    ),
    docs_url="/docs",
    redoc_url="/redoc",
)

# Explicit origins only, paired with allow_credentials. A wildcard origin is
# rejected by browsers when credentials are allowed, so the config layer strips
# it rather than emitting a silently broken policy. CORS_ORIGIN_REGEX covers
# hosts that cannot be enumerated, such as per-deploy Vercel preview domains.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_origin_regex=settings.CORS_ORIGIN_REGEX or None,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix=settings.API_V1_STR)


@app.get("/")
def root():
    return {
        "engine": "VayuDRISHTI Atmospheric Diagnostic Server",
        "status": "ONLINE" if ml_engine.is_ready else "DEGRADED",
        "model": settings.NWP_MODEL_BASE,
        "model_ready": ml_engine.is_ready,
        "docs": "/docs",
        "api_v1": settings.API_V1_STR,
    }
