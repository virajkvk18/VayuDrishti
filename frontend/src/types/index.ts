export type RiskLevel = "LOW" | "MODERATE" | "HIGH";

export type ComparisonSignal =
  | "ANOMALOUSLY_ELEVATED"
  | "CONSISTENT_WITH_ARCHIVE"
  | "BELOW_ARCHIVE_AVERAGE";

export interface HealthTelemetry {
  status: string;
  service: string;
  version: string;
  nwp_model_base: string;
  timestamp_utc: string;
  telemetry_state: string;
  model_ready: boolean;
  model_detail: string | null;
}

export interface HistoricalErrorContext {
  hist_bust_frequency_pct: number;
  hist_bust_frequency_at_lead_pct: number;
  hist_mean_absolute_error_mm: number;
  hist_p90_absolute_error_mm: number;
  archive_samples: number;
  historically_worst_lead_day: number;
  historical_peak_event_type: string;
  current_vs_historical_ratio: number;
  historical_comparison_signal: ComparisonSignal;
  archive_provenance: string;
}

export interface WeatherEventClassification {
  event_type: string;
  classification_confidence: string;
  regime_scores: Record<string, number>;
}

export interface TopDriver {
  feature: string;
  feature_key: string;
  impact_pct: number;
  shap_value: number;
  direction: "INCREASES_RISK" | "DECREASES_RISK";
  observed_value: string;
  scientific_explanation: string;
}

export interface ShapAttribution {
  feature: string;
  name: string;
  unit: string;
  value: number;
  display_value: string;
  shap_value: number;
  relative_impact_pct: number;
  direction: "INCREASES_RISK" | "DECREASES_RISK";
  explanation: string;
}

export interface ModelDeviation {
  precipitation_mm: number;
  slp_hpa: number;
  temperature_c: number;
}

export interface GridCellSummary {
  grid_id: string;
  name: string;
  subdivision: string;
  lat: number;
  lon: number;
  climate_type: string;
  lead_day: number;
  bust_probability: number;
  bust_risk_score: number;
  risk_level: RiskLevel;
  risk_color: string;
  reliability_flag: string;
  confidence_percentage: number;
  event_type: string;
  historical_error_context: HistoricalErrorContext;
  slp_hpa: number;
  precipitable_water_mm: number;
  wind_shear_divergence: number;
  temp_gradient_k: number;
  cape_j_kg: number;
  ensemble_spread_std: number;
  nwp_forecast_precip_mm: number;
  expected_model_deviation: ModelDeviation;
  top_atmospheric_drivers: TopDriver[];
}

export interface ErrorProneArea {
  grid_id: string;
  name: string;
  subdivision: string;
  lat: number;
  lon: number;
  bust_probability: number;
  confidence_percentage: number;
  risk_level: RiskLevel;
  risk_color: string;
  reliability_flag: string;
  event_type: string;
  hist_bust_freq_pct: number;
  current_vs_historical_ratio: number;
  historical_comparison_signal: ComparisonSignal;
  expected_precip_error_mm: number;
  primary_driver: string | null;
}

export interface DomainTelemetry {
  mean_bust_risk: number;
  mean_confidence_pct: number;
  high_risk_cells: number;
  moderate_risk_cells: number;
  low_risk_cells: number;
  error_prone_cells: number;
  max_bust_probability: number;
  min_bust_probability: number;
  active_lead_day: number;
}

export interface ForecastGridResponse {
  status: string;
  model_version: string;
  issuing_agency: string;
  generated_utc: string;
  lead_day: number;
  lead_hour: number;
  bust_definition: {
    variable: string;
    error_threshold_mm: number;
  };
  domain: {
    lat_bounds: [number, number];
    lon_bounds: [number, number];
    total_stations: number;
  };
  domain_telemetry: DomainTelemetry;
  error_prone_areas: ErrorProneArea[];
  grid_cells: GridCellSummary[];
}

export interface LeadTimeEntry {
  lead_day: number;
  lead_hour: number;
  mean_bust_probability: number;
  mean_confidence_pct: number;
  max_bust_probability: number;
  high_risk_cells: number;
  error_prone_cells: number;
  mean_expected_precip_error_mm: number;
}

export interface RegionLeadPoint {
  lead_day: number;
  lead_hour: number;
  bust_probability: number;
  confidence_percentage: number;
  risk_level: RiskLevel;
  expected_precip_error_mm: number;
}

export interface RegionLeadProfile {
  grid_id: string;
  name: string;
  subdivision: string;
  lat: number;
  lon: number;
  mean_bust_probability: number;
  peak_bust_probability: number;
  peak_lead_day: number;
  first_high_risk_lead_day: number | null;
  series: RegionLeadPoint[];
}

export interface LeadTimeProfileResponse {
  status: string;
  model_version: string;
  generated_utc: string;
  lead_day_range: [number, number];
  domain_profile: LeadTimeEntry[];
  highest_risk_lead_day: number;
  lowest_risk_lead_day: number;
  regions: RegionLeadProfile[];
}

export interface ModelSkill {
  roc_auc: number | null;
  roc_auc_cluster_ci90: [number, number] | null;
  brier_score: number | null;
  brier_skill_score: number | null;
  log_loss: number | null;
  expected_calibration_error: number | null;
  error_model_mae_mm: number | null;
  error_model_mae_climatology_mm: number | null;
  error_model_skill_vs_climatology_pct: number | null;
}

export interface ModelMetadata {
  ready: boolean;
  model_version: string | null;
  algorithm: string | null;
  error_model_algorithm: string | null;
  attribution_method: string | null;
  trained_utc: string | null;
  feature_names: string[] | null;
  feature_schema: Record<
    string,
    { unit: string; description: string }
  > | null;
  bust_definition: Record<string, unknown> | null;
  archive: Record<string, unknown> | null;
  held_out_skill: ModelSkill | null;
  reliability: Array<Record<string, number | null>> | null;
  skill_by_lead_day: Record<string, Record<string, number | null>> | null;
  environment: Record<string, string> | null;
  error: string | null;
}

export interface ExplainBustResponse {
  grid_id: string;
  name: string;
  subdivision: string;
  lat: number;
  lon: number;
  climate_type: string;
  lead_day: number;
  bust_probability: number;
  bust_risk_score: number;
  /** Shapley v(empty set) baseline; base + sum(shap) === bust_probability. */
  shap_base_value: number;
  risk_level: RiskLevel;
  risk_color: string;
  reliability_flag: string;
  confidence_percentage: number;
  weather_event_classification: WeatherEventClassification;
  historical_error_context: HistoricalErrorContext;
  expected_model_deviation: ModelDeviation;
  top_atmospheric_drivers: TopDriver[];
  shap_attributions: ShapAttribution[];
  operational_advisory: string;
  ai_synoptic_briefing: string | null;
  observed_features: Record<string, number>;
  ignored_custom_features: string[];
  model_metadata: ModelMetadata;
}

/** Wraps a payload with the provenance the dashboard needs to stay honest. */
export interface ApiResult<T> {
  data: T;
  source: "live" | "offline-fallback";
  error: string | null;
}
