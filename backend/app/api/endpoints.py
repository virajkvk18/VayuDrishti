"""FastAPI endpoints for the VayuDRISHTI forecast-bust diagnostic API.

Every response model here is declared to cover the full engine output. Pydantic
drops undeclared fields silently, so a model that lags behind the engine
quietly deletes deliverables — which is exactly how the error-prone-area and
historical-comparison outputs went missing from the wire format before. The
test suite asserts the presence of each field for that reason.
"""
from datetime import datetime, timezone
from typing import Any, Dict, List, Literal, Optional

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field

from app.core.config import settings
from app.core.ml_engine import ModelArtifactsUnavailable, ml_engine

router = APIRouter()

RiskLevel = Literal["LOW", "MODERATE", "HIGH"]


# --------------------------------------------------------------------------- #
# Shared components
# --------------------------------------------------------------------------- #


class HistoricalErrorContext(BaseModel):
    """Comparison of the live forecast against the region's verification record."""

    hist_bust_frequency_pct: float
    hist_bust_frequency_at_lead_pct: float
    hist_mean_absolute_error_mm: float
    hist_p90_absolute_error_mm: float
    archive_samples: int
    historically_worst_lead_day: int
    historical_peak_event_type: str
    current_vs_historical_ratio: float
    historical_comparison_signal: str
    archive_provenance: str


class WeatherEventClassification(BaseModel):
    event_type: str
    classification_confidence: str
    regime_scores: Dict[str, float]


class TopDriver(BaseModel):
    feature: str
    feature_key: str
    impact_pct: float
    shap_value: float
    direction: str
    observed_value: str
    scientific_explanation: str


class ShapAttribution(BaseModel):
    feature: str
    name: str
    unit: str
    value: float
    display_value: str
    shap_value: float
    relative_impact_pct: float
    direction: str
    explanation: str


class ModelDeviation(BaseModel):
    precipitation_mm: float
    slp_hpa: float
    temperature_c: float


class DomainBounds(BaseModel):
    lat_bounds: List[float]
    lon_bounds: List[float]
    total_stations: int


class BustDefinition(BaseModel):
    variable: str
    error_threshold_mm: float


# --------------------------------------------------------------------------- #
# Health
# --------------------------------------------------------------------------- #


class HealthResponse(BaseModel):
    status: str
    service: str
    version: str
    nwp_model_base: str
    timestamp_utc: str
    telemetry_state: str
    model_ready: bool
    model_detail: Optional[str] = None


# --------------------------------------------------------------------------- #
# Forecast grid
# --------------------------------------------------------------------------- #


class GridCellSummary(BaseModel):
    grid_id: str
    name: str
    subdivision: str
    lat: float
    lon: float
    climate_type: str
    lead_day: int
    bust_probability: float
    bust_risk_score: float
    risk_level: RiskLevel
    risk_color: str
    reliability_flag: str
    confidence_percentage: float
    event_type: str
    historical_error_context: HistoricalErrorContext
    slp_hpa: float
    precipitable_water_mm: float
    wind_shear_divergence: float
    temp_gradient_k: float
    cape_j_kg: float
    ensemble_spread_std: float
    nwp_forecast_precip_mm: float
    expected_model_deviation: ModelDeviation
    top_atmospheric_drivers: List[TopDriver]


class ErrorProneArea(BaseModel):
    """A region whose forecast should be treated as unreliable at this lead time."""

    grid_id: str
    name: str
    subdivision: str
    lat: float
    lon: float
    bust_probability: float
    confidence_percentage: float
    risk_level: RiskLevel
    risk_color: str
    reliability_flag: str
    event_type: str
    hist_bust_freq_pct: float
    current_vs_historical_ratio: float
    historical_comparison_signal: str
    expected_precip_error_mm: float
    primary_driver: Optional[str] = None


class DomainTelemetry(BaseModel):
    mean_bust_risk: float
    mean_confidence_pct: float
    high_risk_cells: int
    moderate_risk_cells: int
    low_risk_cells: int
    error_prone_cells: int
    max_bust_probability: float
    min_bust_probability: float
    active_lead_day: int


class ForecastGridResponse(BaseModel):
    status: str
    model_version: str
    issuing_agency: str
    generated_utc: str
    lead_day: int
    lead_hour: int
    bust_definition: BustDefinition
    domain: DomainBounds
    domain_telemetry: DomainTelemetry
    error_prone_areas: List[ErrorProneArea]
    grid_cells: List[GridCellSummary]


# --------------------------------------------------------------------------- #
# Lead-time profile
# --------------------------------------------------------------------------- #


class LeadTimeEntry(BaseModel):
    lead_day: int
    lead_hour: int
    mean_bust_probability: float
    mean_confidence_pct: float
    max_bust_probability: float
    high_risk_cells: int
    error_prone_cells: int
    mean_expected_precip_error_mm: float


class RegionLeadPoint(BaseModel):
    lead_day: int
    lead_hour: int
    bust_probability: float
    confidence_percentage: float
    risk_level: RiskLevel
    expected_precip_error_mm: float


class RegionLeadProfile(BaseModel):
    grid_id: str
    name: str
    subdivision: str
    lat: float
    lon: float
    mean_bust_probability: float
    peak_bust_probability: float
    peak_lead_day: int
    first_high_risk_lead_day: Optional[int] = None
    series: List[RegionLeadPoint]


class LeadTimeProfileResponse(BaseModel):
    status: str
    model_version: str
    generated_utc: str
    lead_day_range: List[int]
    domain_profile: List[LeadTimeEntry]
    highest_risk_lead_day: int
    lowest_risk_lead_day: int
    regions: List[RegionLeadProfile]


# --------------------------------------------------------------------------- #
# Explain
# --------------------------------------------------------------------------- #


class ExplainBustRequest(BaseModel):
    grid_id: str = Field(
        ..., description="Target region identifier, e.g. IND-E-16", min_length=1, max_length=64
    )
    lead_day: int = Field(
        settings.LEAD_DAY_MIN,
        ge=settings.LEAD_DAY_MIN,
        le=settings.LEAD_DAY_MAX,
        description="Forecast lead day index",
    )
    custom_features: Optional[Dict[str, float]] = Field(
        None, description="Optional overridden atmospheric parameters for a what-if run"
    )


class ModelSkill(BaseModel):
    roc_auc: Optional[float] = None
    roc_auc_cluster_ci90: Optional[List[float]] = None
    brier_score: Optional[float] = None
    brier_skill_score: Optional[float] = None
    log_loss: Optional[float] = None
    expected_calibration_error: Optional[float] = None
    error_model_mae_mm: Optional[float] = None
    error_model_mae_climatology_mm: Optional[float] = None
    error_model_skill_vs_climatology_pct: Optional[float] = None


class ModelMetadata(BaseModel):
    ready: bool
    model_version: Optional[str] = None
    algorithm: Optional[str] = None
    error_model_algorithm: Optional[str] = None
    attribution_method: Optional[str] = None
    trained_utc: Optional[str] = None
    feature_names: Optional[List[str]] = None
    feature_schema: Optional[Dict[str, Any]] = None
    bust_definition: Optional[Dict[str, Any]] = None
    archive: Optional[Dict[str, Any]] = None
    held_out_skill: Optional[ModelSkill] = None
    reliability: Optional[List[Dict[str, Any]]] = None
    skill_by_lead_day: Optional[Dict[str, Any]] = None
    environment: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


class ExplainBustResponse(BaseModel):
    grid_id: str
    name: str
    subdivision: str
    lat: float
    lon: float
    climate_type: str
    lead_day: int
    bust_probability: float
    bust_risk_score: float
    shap_base_value: float = Field(
        ...,
        description=(
            "Interventional Shapley v(empty set) baseline. "
            "shap_base_value + sum(shap_attributions[*].shap_value) "
            "reconstructs bust_probability."
        ),
    )
    risk_level: RiskLevel
    risk_color: str
    reliability_flag: str
    confidence_percentage: float
    weather_event_classification: WeatherEventClassification
    historical_error_context: HistoricalErrorContext
    expected_model_deviation: ModelDeviation
    top_atmospheric_drivers: List[TopDriver]
    shap_attributions: List[ShapAttribution]
    operational_advisory: str
    ai_synoptic_briefing: Optional[str] = None
    observed_features: Dict[str, float]
    ignored_custom_features: List[str] = Field(default_factory=list)
    model_metadata: ModelMetadata


# --------------------------------------------------------------------------- #
# Endpoints
# --------------------------------------------------------------------------- #


def _unavailable(exc: Exception) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
    )


@router.get("/health", response_model=HealthResponse, tags=["Telemetry & Health"])
def get_health() -> HealthResponse:
    """Operational health telemetry, including whether the trained models loaded."""
    ready = ml_engine.is_ready
    return HealthResponse(
        status="OPERATIONAL" if ready else "DEGRADED",
        service=settings.PROJECT_NAME,
        version=settings.VERSION,
        nwp_model_base=settings.NWP_MODEL_BASE,
        timestamp_utc=datetime.now(timezone.utc).isoformat(),
        telemetry_state="NOMINAL_GREEN" if ready else "MODEL_ARTIFACTS_MISSING",
        model_ready=ready,
        model_detail=ml_engine.load_error,
    )


@router.get(
    "/forecast-grid", response_model=ForecastGridResponse, tags=["Forecast Grid Diagnostics"]
)
def get_forecast_grid(
    lead_day: int = Query(
        settings.LEAD_DAY_MIN,
        ge=settings.LEAD_DAY_MIN,
        le=settings.LEAD_DAY_MAX,
        description="Forecast lead day index",
    )
) -> ForecastGridResponse:
    """Bust probability, confidence and error-prone areas for every region.

    Addresses expected outcomes 1, 2 and 3 of the problem statement in one call.
    """
    try:
        return ForecastGridResponse(**ml_engine.get_forecast_grid(lead_day=lead_day))
    except ModelArtifactsUnavailable as exc:
        raise _unavailable(exc)


@router.get(
    "/lead-time-profile",
    response_model=LeadTimeProfileResponse,
    tags=["Forecast Grid Diagnostics"],
)
def get_lead_time_profile() -> LeadTimeProfileResponse:
    """Risk across the full Day 1 to Day 10 horizon, domain-wide and per region.

    Answers the "which regions *and lead times*" half of the challenge, which a
    single-day map cannot express.
    """
    try:
        return LeadTimeProfileResponse(**ml_engine.get_lead_time_profile())
    except ModelArtifactsUnavailable as exc:
        raise _unavailable(exc)


@router.post(
    "/explain-bust", response_model=ExplainBustResponse, tags=["XAI Model Explainability"]
)
def explain_bust(payload: ExplainBustRequest) -> ExplainBustResponse:
    """Exact Shapley attribution breakdown and operational directive for a region."""
    try:
        result = ml_engine.explain_grid_cell(
            grid_id=payload.grid_id,
            lead_day=payload.lead_day,
            custom_features=payload.custom_features,
        )
        return ExplainBustResponse(**result)
    except ModelArtifactsUnavailable as exc:
        raise _unavailable(exc)
    except (KeyError, TypeError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Could not build the explainability breakdown: {exc}",
        )


@router.get("/model-info", response_model=ModelMetadata, tags=["Model Provenance"])
def get_model_info() -> ModelMetadata:
    """Algorithm, archive provenance and held-out skill for the loaded artifacts."""
    return ModelMetadata(**ml_engine.model_metadata())
