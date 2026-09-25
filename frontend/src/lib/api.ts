import {
  ApiResult,
  ExplainBustResponse,
  ForecastGridResponse,
  HealthTelemetry,
  LeadTimeProfileResponse,
  ModelMetadata,
} from "@/types";

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000/api/v1";

const OFFLINE_NOTICE =
  "Backend unreachable - showing offline synthetic baseline, not live model output.";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 20000);
  try {
    const res = await fetch(`${API_BASE_URL}${path}`, {
      cache: "no-store",
      signal: controller.signal,
      ...init,
    });
    if (!res.ok) {
      const detail = await res.text().catch(() => "");
      throw new Error(`${res.status} ${res.statusText}${detail ? ` - ${detail}` : ""}`);
    }
    return (await res.json()) as T;
  } finally {
    clearTimeout(timeout);
  }
}

function describe(error: unknown): string {
  if (error instanceof DOMException && error.name === "AbortError") {
    return "Request timed out after 20s";
  }
  if (error instanceof Error) return error.message;
  return String(error);
}

export async function fetchHealth(): Promise<ApiResult<HealthTelemetry>> {
  try {
    return { data: await request<HealthTelemetry>("/health"), source: "live", error: null };
  } catch (err) {
    return {
      data: {
        status: "UNREACHABLE",
        service: "VayuDRISHTI Atmospheric Diagnostic Engine",
        version: "3.0.0",
        nwp_model_base: "NCMRWF-Irrespective Diagnostic v3.0",
        timestamp_utc: new Date().toISOString(),
        telemetry_state: "BACKEND_OFFLINE",
        model_ready: false,
        model_detail: OFFLINE_NOTICE,
      },
      source: "offline-fallback",
      error: describe(err),
    };
  }
}

export async function fetchForecastGrid(
  leadDay: number = 1
): Promise<ApiResult<ForecastGridResponse>> {
  const boundedLead = Math.max(1, Math.min(10, leadDay));
  try {
    const data = await request<ForecastGridResponse>(
      `/forecast-grid?lead_day=${boundedLead}`
    );
    return { data, source: "live", error: null };
  } catch (err) {
    return {
      data: buildOfflineGrid(boundedLead),
      source: "offline-fallback",
      error: describe(err),
    };
  }
}

export async function fetchLeadTimeProfile(): Promise<
  ApiResult<LeadTimeProfileResponse>
> {
  try {
    return {
      data: await request<LeadTimeProfileResponse>("/lead-time-profile"),
      source: "live",
      error: null,
    };
  } catch (err) {
    return {
      data: buildOfflineProfile(),
      source: "offline-fallback",
      error: describe(err),
    };
  }
}

export async function fetchModelInfo(): Promise<ApiResult<ModelMetadata>> {
  try {
    return {
      data: await request<ModelMetadata>("/model-info"),
      source: "live",
      error: null,
    };
  } catch (err) {
    return {
      data: {
        ready: false,
        model_version: null,
        algorithm: null,
        error_model_algorithm: null,
        attribution_method: null,
        trained_utc: null,
        feature_names: null,
        feature_schema: null,
        bust_definition: null,
        archive: null,
        held_out_skill: null,
        reliability: null,
        skill_by_lead_day: null,
        environment: null,
        error: describe(err),
      },
      source: "offline-fallback",
      error: describe(err),
    };
  }
}

export async function explainBust(
  gridId: string,
  leadDay: number = 1,
  customFeatures?: Record<string, number>
): Promise<ApiResult<ExplainBustResponse>> {
  const boundedLead = Math.max(1, Math.min(10, leadDay));
  try {
    const data = await request<ExplainBustResponse>("/explain-bust", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        grid_id: gridId,
        lead_day: boundedLead,
        custom_features: customFeatures,
      }),
    });
    return { data, source: "live", error: null };
  } catch (err) {
    return {
      data: buildOfflineExplain(gridId, boundedLead),
      source: "offline-fallback",
      error: describe(err),
    };
  }
}

/* -------------------------------------------------------------------------- */
/* Offline fallback                                                          */
/* -------------------------------------------------------------------------- */

const OFFLINE_REGIONS = [
  ["IND-NW-01", "Kashmir & Pir Panjal Ridge", "Western Himalayas", 34.08, 74.8, "Alpine / Orographic", 1016, 24],
  ["IND-NW-02", "Northern Punjab Plains (Amritsar)", "North-West Plains", 31.63, 74.87, "Continental Semi-Arid", 1012, 32],
  ["IND-NC-03", "Indo-Gangetic Capital Zone (Delhi NCR)", "Upper Gangetic Basin", 28.61, 77.2, "Subtropical High-Density", 1009.5, 42],
  ["IND-W-04", "Thar Desert Basin (Barmer / Jodhpur)", "Western Dry Zone", 26.28, 71.5, "Hyper-Arid Thermal", 1004, 22],
  ["IND-W-05", "Gulf of Khambhat / Rann of Kutch", "Saurashtra & Kutch", 23.02, 70.8, "Coastal Arid-Marine", 1007, 48],
  ["IND-C-06", "Malwa Plateau & Narmada Valley (Bhopal)", "Central Highlands", 23.25, 77.41, "Tropical Continental", 1008, 46],
  ["IND-C-07", "Vidarbha Dryline Sector (Nagpur)", "East Central Deccan", 21.14, 79.08, "Tropical Semi-Arid Convective", 1007.5, 44],
  ["IND-E-08", "Middle Gangetic Trough (Patna)", "Bihar Plains", 25.59, 85.13, "Humid Subtropical Fluvial", 1006, 54],
  ["IND-E-09", "Bengal Deltaic Estuary (Kolkata)", "Gangetic West Bengal", 22.57, 88.36, "Tropical Wet-and-Dry Coastal", 1005, 58],
  ["IND-NE-10", "Brahmaputra Valley (Guwahati)", "Assam Valley", 26.14, 91.73, "Subtropical Valley-Trapped", 1007.8, 62],
  ["IND-NE-11", "Meghalaya Escarpment (Cherrapunji / Shillong)", "North Eastern Highlands", 25.3, 91.7, "Extreme Orographic Hyper-Pluvial", 1006.2, 68],
  ["IND-W-12", "Northern Konkan Marine Basin (Mumbai Offshore)", "Konkan Maritime", 18.92, 72.83, "Tropical Marine High-Flux", 1006.5, 60],
  ["IND-SW-13", "Malabar Ridge & Ghats (Kochi / Idukki)", "Kerala Coastal Ghats", 9.93, 76.26, "Tropical Monsoon Rainforest", 1009, 64],
  ["IND-S-14", "South Deccan Interior (Bengaluru)", "South Interior Karnataka", 12.97, 77.59, "Semi-Arid Plateau Elevated", 1011, 40],
  ["IND-SE-15", "Coromandel Coastal Arc (Chennai)", "Tamil Nadu Coastal", 13.08, 80.27, "Tropical Marine Maritime", 1008.2, 56],
  ["IND-E-16", "Odisha Coastal Cyclone Corridor (Paradip)", "Odisha Coastal", 20.31, 86.61, "Tropical Low Pressure Corridor", 1002.5, 66],
  ["IND-M-17", "Central Bay of Bengal Deep Ocean Buoy", "Bay of Bengal Marine", 15.0, 88.5, "Open Ocean Tropical Cyclogenesis", 1001, 72],
  ["IND-M-18", "Arabian Sea Deep Moored Array", "Arabian Sea Offshore", 16.5, 68.8, "Marine Somali Jet Confluence", 1005, 59],
  ["IND-S-19", "Palk Strait Inter-Basin Channel (Kanyakumari)", "Southern Maritime Boundary", 8.08, 77.53, "Equatorial Ocean Gateway", 1009.8, 52],
  ["IND-N-20", "Ladakh Cold Steppe & Trans-Himalayas (Leh)", "High Altitude Arid", 34.15, 77.57, "Polar / Alpine Desert", 1019, 12],
] as const;

const OFFLINE_EVENTS = [
  "Monsoon Depression / Heavy Rainfall",
  "Orographic Extreme Rainfall",
  "Stable / Non-eventive",
  "Western Disturbance / Upper Trough",
];

const OFFLINE_DRIVERS = [
  {
    feature: "Forecast lead time",
    feature_key: "lead_day",
    direction: "INCREASES_RISK" as const,
    scientific_explanation:
      "Long lead time leaves the control run deep in the nonlinear growth phase.",
  },
  {
    feature: "Regional historical bust frequency",
    feature_key: "hist_bust_freq_pct",
    direction: "INCREASES_RISK" as const,
    scientific_explanation:
      "The region's own verification record shows an elevated historical bust rate.",
  },
  {
    feature: "Column precipitable water (PWAT)",
    feature_key: "precipitable_water_mm",
    direction: "INCREASES_RISK" as const,
    scientific_explanation:
      "A deep moisture reservoir makes accumulated precipitation hypersensitive to moisture flux error.",
  },
];

function riskLevel(p: number): "LOW" | "MODERATE" | "HIGH" {
  return p >= 0.65 ? "HIGH" : p >= 0.35 ? "MODERATE" : "LOW";
}

function riskColor(level: "LOW" | "MODERATE" | "HIGH"): string {
  return level === "HIGH" ? "#ef4444" : level === "MODERATE" ? "#eab308" : "#10b981";
}

function reliabilityFlag(level: "LOW" | "MODERATE" | "HIGH"): string {
  return level === "HIGH"
    ? "ERROR_PRONE"
    : level === "MODERATE"
    ? "ELEVATED_UNCERTAINTY"
    : "RELIABLE";
}

/** Deterministic stand-in used only when the backend cannot be reached. */
function offlineProbability(
  index: number,
  leadDay: number,
  baseSlp: number,
  basePwat: number
): number {
  const lead = 0.16 * (leadDay - 1);
  const instability = (60 - basePwat) / 90 + (1013 - baseSlp) / 60;
  const wave = 0.05 * Math.sin(index * 1.7 + leadDay * 0.6);
  const raw = 0.16 + lead + instability * 0.22 + wave;
  return Number(Math.min(0.95, Math.max(0.03, raw)).toFixed(3));
}

function buildOfflineGrid(leadDay: number): ForecastGridResponse {
  const cells = OFFLINE_REGIONS.map((r, index) => {
    const [grid_id, name, subdivision, lat, lon, climate_type, baseSlp, basePwat] = r;
    const probability = offlineProbability(index, leadDay, baseSlp, basePwat);
    const level = riskLevel(probability);
    const histFreq = Number((12 + (60 - basePwat) * 0.55).toFixed(2));
    const ratio = Number(((probability * 100) / Math.max(histFreq, 0.5)).toFixed(2));
    const expectedError = Number((probability * 60 + leadDay * 1.5).toFixed(1));

    return {
      grid_id,
      name,
      subdivision,
      lat,
      lon,
      climate_type,
      lead_day: leadDay,
      bust_probability: probability,
      bust_risk_score: probability,
      risk_level: level,
      risk_color: riskColor(level),
      reliability_flag: reliabilityFlag(level),
      confidence_percentage: Number(((1 - probability) * 100).toFixed(1)),
      event_type: OFFLINE_EVENTS[index % OFFLINE_EVENTS.length],
      historical_error_context: {
        hist_bust_frequency_pct: histFreq,
        hist_bust_frequency_at_lead_pct: histFreq,
        hist_mean_absolute_error_mm: Number((histFreq * 0.9).toFixed(1)),
        hist_p90_absolute_error_mm: Number((histFreq * 2.1).toFixed(1)),
        archive_samples: 0,
        historically_worst_lead_day: Math.min(9, 2 + (index % 5)),
        historical_peak_event_type: "Offline synthetic baseline",
        current_vs_historical_ratio: ratio,
        historical_comparison_signal:
          ratio >= 1.5
            ? ("ANOMALOUSLY_ELEVATED" as const)
            : ratio >= 0.8
            ? ("CONSISTENT_WITH_ARCHIVE" as const)
            : ("BELOW_ARCHIVE_AVERAGE" as const),
        archive_provenance: "offline synthetic baseline (backend unreachable)",
      },
      slp_hpa: Number((baseSlp - leadDay * 0.4).toFixed(1)),
      precipitable_water_mm: Number((basePwat + leadDay * 0.8).toFixed(1)),
      wind_shear_divergence: Number((4.5 + leadDay * 0.3).toFixed(2)),
      temp_gradient_k: Number((6.3 + leadDay * 0.08).toFixed(2)),
      cape_j_kg: Math.round(basePwat * 40 + leadDay * 90),
      ensemble_spread_std: Number((1.2 + leadDay * 1.4).toFixed(2)),
      nwp_forecast_precip_mm: Number((Math.max(0, basePwat - 30) * 1.2).toFixed(1)),
      expected_model_deviation: {
        precipitation_mm: expectedError,
        slp_hpa: Number((expectedError * 0.16).toFixed(2)),
        temperature_c: Number((expectedError * 0.075).toFixed(1)),
      },
      top_atmospheric_drivers: OFFLINE_DRIVERS.map((d, i) => ({
        ...d,
        impact_pct: [38.4, 29.1, 18.7][i],
        shap_value: [0.19, 0.14, 0.09][i],
        observed_value: ["", `${histFreq}%`, `${basePwat.toFixed(1)} mm`][i],
      })),
    };
  });

  const probs = cells.map((c) => c.bust_probability);
  return {
    status: "OFFLINE_SYNTHETIC",
    model_version: "offline-fallback",
    issuing_agency: "NCMRWF / Ministry of Earth Sciences (MoES)",
    generated_utc: new Date().toISOString(),
    lead_day: leadDay,
    lead_hour: leadDay * 24,
    bust_definition: { variable: "24h accumulated precipitation", error_threshold_mm: 25 },
    domain: { lat_bounds: [8, 37], lon_bounds: [68, 97], total_stations: cells.length },
    domain_telemetry: {
      mean_bust_risk: Number(
        (probs.reduce((a, b) => a + b, 0) / probs.length).toFixed(4)
      ),
      mean_confidence_pct: Number(
        (
          cells.reduce((a, c) => a + c.confidence_percentage, 0) / cells.length
        ).toFixed(1)
      ),
      high_risk_cells: cells.filter((c) => c.risk_level === "HIGH").length,
      moderate_risk_cells: cells.filter((c) => c.risk_level === "MODERATE").length,
      low_risk_cells: cells.filter((c) => c.risk_level === "LOW").length,
      error_prone_cells: cells.filter((c) => c.risk_level !== "LOW").length,
      max_bust_probability: Math.max(...probs),
      min_bust_probability: Math.min(...probs),
      active_lead_day: leadDay,
    },
    error_prone_areas: cells
      .filter((c) => c.risk_level !== "LOW")
      .map((c) => ({
        grid_id: c.grid_id,
        name: c.name,
        subdivision: c.subdivision,
        lat: c.lat,
        lon: c.lon,
        bust_probability: c.bust_probability,
        confidence_percentage: c.confidence_percentage,
        risk_level: c.risk_level,
        risk_color: c.risk_color,
        reliability_flag: c.reliability_flag,
        event_type: c.event_type,
        hist_bust_freq_pct: c.historical_error_context.hist_bust_frequency_pct,
        current_vs_historical_ratio:
          c.historical_error_context.current_vs_historical_ratio,
        historical_comparison_signal:
          c.historical_error_context.historical_comparison_signal,
        expected_precip_error_mm: c.expected_model_deviation.precipitation_mm,
        primary_driver: c.top_atmospheric_drivers[0]?.feature_key ?? null,
      }))
      .sort((a, b) => b.bust_probability - a.bust_probability),
    grid_cells: cells,
  };
}

function buildOfflineProfile(): LeadTimeProfileResponse {
  const domain_profile = Array.from({ length: 10 }, (_, i) => {
    const day = i + 1;
    const grid = buildOfflineGrid(day);
    const probs = grid.grid_cells.map((c) => c.bust_probability);
    return {
      lead_day: day,
      lead_hour: day * 24,
      mean_bust_probability: grid.domain_telemetry.mean_bust_risk,
      mean_confidence_pct: grid.domain_telemetry.mean_confidence_pct,
      max_bust_probability: Math.max(...probs),
      high_risk_cells: grid.domain_telemetry.high_risk_cells,
      error_prone_cells: grid.domain_telemetry.error_prone_cells,
      mean_expected_precip_error_mm: Number(
        (
          grid.grid_cells.reduce(
            (a, c) => a + c.expected_model_deviation.precipitation_mm,
            0
          ) / grid.grid_cells.length
        ).toFixed(1)
      ),
    };
  });

  const regions = OFFLINE_REGIONS.map((r, index) => {
    const series = domain_profile.map((d) => {
      const cell = buildOfflineGrid(d.lead_day).grid_cells[index];
      return {
        lead_day: d.lead_day,
        lead_hour: d.lead_hour,
        bust_probability: cell.bust_probability,
        confidence_percentage: cell.confidence_percentage,
        risk_level: cell.risk_level,
        expected_precip_error_mm: cell.expected_model_deviation.precipitation_mm,
      };
    });
    const peak = series.reduce((a, b) =>
      b.bust_probability > a.bust_probability ? b : a
    );
    return {
      grid_id: r[0],
      name: r[1],
      subdivision: r[2],
      lat: r[3],
      lon: r[4],
      mean_bust_probability: Number(
        (series.reduce((a, p) => a + p.bust_probability, 0) / series.length).toFixed(4)
      ),
      peak_bust_probability: peak.bust_probability,
      peak_lead_day: peak.lead_day,
      first_high_risk_lead_day: series.find((s) => s.risk_level === "HIGH")
        ?.lead_day ?? null,
      series,
    };
  }).sort((a, b) => b.mean_bust_probability - a.mean_bust_probability);

  return {
    status: "OFFLINE_SYNTHETIC",
    model_version: "offline-fallback",
    generated_utc: new Date().toISOString(),
    lead_day_range: [1, 10],
    domain_profile,
    highest_risk_lead_day: domain_profile.reduce((a, b) =>
      b.mean_bust_probability > a.mean_bust_probability ? b : a
    ).lead_day,
    lowest_risk_lead_day: domain_profile.reduce((a, b) =>
      b.mean_bust_probability < a.mean_bust_probability ? b : a
    ).lead_day,
    regions,
  };
}

function buildOfflineExplain(
  gridId: string,
  leadDay: number
): ExplainBustResponse {
  const index = Math.max(
    0,
    OFFLINE_REGIONS.findIndex((r) => r[0] === gridId)
  );
  const region = OFFLINE_REGIONS[index] ?? OFFLINE_REGIONS[0];
  const cell = buildOfflineGrid(leadDay).grid_cells[index];
  const shapNames = [
    ["lead_day", "Forecast lead time", "d"],
    ["hist_bust_freq_pct", "Regional historical bust frequency", "%"],
    ["precipitable_water_mm", "Column precipitable water (PWAT)", "mm"],
    ["cape_j_kg", "Convective available potential energy", "J kg-1"],
    ["ensemble_spread_std", "Ensemble spread of 24h accumulated precipitation", "mm"],
    ["slp_hpa", "Mean sea-level pressure", "hPa"],
  ] as const;

  const total = 0.19 + 0.14 + 0.09 + 0.07 + 0.05 + 0.03;
  return {
    ...cell,
    grid_id: region[0],
    name: region[1],
    subdivision: region[2],
    lat: region[3],
    lon: region[4],
    climate_type: region[5],
    shap_base_value: Number(
      (cell.bust_probability - total).toFixed(4)
    ),
    weather_event_classification: {
      event_type: cell.event_type,
      classification_confidence: "LOW",
      regime_scores: {},
    },
    shap_attributions: shapNames.map(([key, name, unit], i) => {
      const shap = [0.19, 0.14, 0.09, 0.07, 0.05, 0.03][i];
      const value =
        key === "lead_day"
          ? leadDay
          : key === "hist_bust_freq_pct"
          ? cell.historical_error_context.hist_bust_frequency_pct
          : key === "cape_j_kg"
          ? cell.cape_j_kg
          : (cell as unknown as Record<string, number>)[key] ?? 0;
      return {
        feature: key,
        name,
        unit,
        value,
        display_value: `${value} ${unit}`,
        shap_value: shap,
        relative_impact_pct: Number(((shap / total) * 100).toFixed(1)),
        direction: "INCREASES_RISK" as const,
        explanation: OFFLINE_NOTICE,
      };
    }),
    operational_advisory: `OFFLINE SYNTHETIC ADVISORY [Day ${leadDay}]: ${OFFLINE_NOTICE} No model output is available; do not use these values for operational decisions.`,
    ai_synoptic_briefing: null,
    observed_features: {
      slp_hpa: cell.slp_hpa,
      precipitable_water_mm: cell.precipitable_water_mm,
      wind_shear_divergence: cell.wind_shear_divergence,
      temp_gradient_k: cell.temp_gradient_k,
      cape_j_kg: cell.cape_j_kg,
      ensemble_spread_std: cell.ensemble_spread_std,
      lead_day: leadDay,
    },
    ignored_custom_features: [],
    model_metadata: {
      ready: false,
      model_version: null,
      algorithm: null,
      error_model_algorithm: null,
      attribution_method: null,
      trained_utc: null,
      feature_names: null,
      feature_schema: null,
      bust_definition: null,
      archive: null,
      held_out_skill: null,
      reliability: null,
      skill_by_lead_day: null,
      environment: null,
      error: OFFLINE_NOTICE,
    },
  };
}
