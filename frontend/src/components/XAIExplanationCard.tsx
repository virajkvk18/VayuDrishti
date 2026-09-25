"use client";

import React, { useState } from "react";
import {
  AlertOctagon,
  ArrowDownRight,
  ArrowUpRight,
  BrainCircuit,
  Compass,
  Info,
  Sliders,
  Sparkles,
} from "lucide-react";
import { ExplainBustResponse } from "@/types";
import HistoricalComparisonCard from "@/components/HistoricalComparisonCard";

interface XAIExplanationCardProps {
  data: ExplainBustResponse | null;
  isLoading?: boolean;
  dataSource?: "live" | "offline-fallback";
  onRunCustomAnalysis?: (features: Record<string, number>) => void;
}

export default function XAIExplanationCard({
  data,
  isLoading = false,
  dataSource = "live",
  onRunCustomAnalysis,
}: XAIExplanationCardProps) {
  const [showSensitivityModal, setShowSensitivityModal] = useState(false);
  // Ranges mirror the archive's physical limits accepted by the API, so the
  // what-if controls cannot request a value the backend would reject.
  const [shearVal, setShearVal] = useState<number>(8.0);
  const [pwatVal, setPwatVal] = useState<number>(55.0);
  const [capeVal, setCapeVal] = useState<number>(2400);

  if (isLoading) {
    return (
      <div className="rounded-lg border border-slate-800 bg-[#0c1220] p-6 font-mono text-xs text-slate-400 flex flex-col items-center justify-center min-h-[420px] gap-3">
        <BrainCircuit className="w-8 h-8 text-sky-400 animate-spin" />
        <span className="text-slate-300">Processing Atmospheric SHAP Attributions...</span>
        <span className="text-[10px] text-slate-500">Deconstructing 850–200 hPa tensor divergence matrix</span>
      </div>
    );
  }

  if (!data) {
    return (
      <div className="rounded-lg border border-slate-800 bg-[#0c1220] p-8 font-mono text-xs text-slate-500 flex flex-col items-center justify-center min-h-[420px] text-center gap-2">
        <Compass className="w-8 h-8 text-slate-600 mb-1" />
        <span className="text-slate-300 font-semibold">NO STATION SELECTED</span>
        <p className="max-w-xs text-slate-500">
          Click any meteorological grid station on the India telemetry map to inspect its forecast bust probability and XAI drivers.
        </p>
      </div>
    );
  }

  const handleApplySensitivity = () => {
    if (onRunCustomAnalysis) {
      onRunCustomAnalysis({
        wind_shear_divergence: shearVal,
        precipitable_water_mm: pwatVal,
        cape_j_kg: capeVal,
      });
      setShowSensitivityModal(false);
    }
  };

  const riskBadgeBg =
    data.risk_level === "HIGH"
      ? "bg-rose-500/20 text-rose-300 border-rose-500/40"
      : data.risk_level === "MODERATE"
      ? "bg-amber-500/20 text-amber-300 border-amber-500/40"
      : "bg-emerald-500/20 text-emerald-300 border-emerald-500/40";

  return (
    <div className="rounded-lg border border-slate-800 bg-[#0c1220] p-5 font-mono text-xs text-slate-300 shadow-xl space-y-4">
      {/* Header: Station & Geographic Telemetry */}
      <div className="flex flex-wrap items-start justify-between gap-3 pb-3 border-b border-slate-800">
        <div>
          <div className="flex items-center gap-2">
            <span className="px-1.5 py-0.5 rounded bg-sky-950 border border-sky-800 text-sky-400 font-bold text-[11px]">
              {data.grid_id}
            </span>
            <h2 className="text-sm font-bold text-slate-100">{data.name}</h2>
          </div>
          <div className="text-[11px] text-slate-400 mt-1 flex items-center gap-2">
            <span>{data.subdivision}</span>
            <span>•</span>
            <span>{data.lat.toFixed(2)}°N, {data.lon.toFixed(2)}°E</span>
            <span>•</span>
            <span className="text-slate-500">{data.climate_type}</span>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <span className={`px-2.5 py-1 rounded border text-[11px] font-bold ${riskBadgeBg}`}>
            {data.risk_level} BUST RISK
          </span>
          <button
            type="button"
            onClick={() => setShowSensitivityModal(!showSensitivityModal)}
            className="p-1.5 rounded border border-slate-700 bg-slate-800 hover:bg-slate-700 text-sky-400 transition-colors"
            title="Perform Sensitivity Perturbation Test"
          >
            <Sliders className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>

      {/* Primary Quantitative Scores */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-2.5">
        <div className="p-2.5 rounded bg-[#070b14] border border-slate-800/80">
          <span className="text-[10px] text-slate-500 block">BUST PROBABILITY</span>
          <span
            className={`text-xl font-bold ${
              data.bust_risk_score >= 0.65
                ? "text-rose-400"
                : data.bust_risk_score >= 0.35
                ? "text-amber-400"
                : "text-emerald-400"
            }`}
          >
            {data.bust_risk_score.toFixed(3)}
          </span>
        </div>

        <div className="p-2.5 rounded bg-[#070b14] border border-slate-800/80">
          <span className="text-[10px] text-slate-500 block">CONFIDENCE METRIC</span>
          <span className="text-xl font-bold text-slate-100">
            {data.confidence_percentage.toFixed(1)}%
          </span>
        </div>

        <div className="p-2.5 rounded bg-[#070b14] border border-slate-800/80">
          <span className="text-[10px] text-slate-500 block">PRECIP DEVIATION</span>
          <span className="text-xl font-bold text-amber-300">
            ±{data.expected_model_deviation.precipitation_mm} mm
          </span>
        </div>

        <div className="p-2.5 rounded bg-[#070b14] border border-slate-800/80">
          <span className="text-[10px] text-slate-500 block">PRESSURE DEVIATION</span>
          <span className="text-xl font-bold text-sky-300">
            ±{data.expected_model_deviation.slp_hpa} hPa
          </span>
        </div>
      </div>

      {/* Reliability flag + weather event classification */}
      <div className="flex flex-wrap items-center gap-2">
        <span
          className={`px-2 py-0.5 rounded border text-[10px] font-bold ${
            data.reliability_flag === "ERROR_PRONE"
              ? "border-rose-500/50 bg-rose-950/30 text-rose-300"
              : data.reliability_flag === "ELEVATED_UNCERTAINTY"
              ? "border-amber-500/50 bg-amber-950/30 text-amber-300"
              : "border-emerald-500/40 bg-emerald-950/30 text-emerald-300"
          }`}
        >
          {data.reliability_flag.replace(/_/g, " ")}
        </span>
        <span className="px-2 py-0.5 rounded border border-slate-700 bg-slate-900 text-slate-300 text-[10px]">
          REGIME: {data.weather_event_classification.event_type}
        </span>
        <span className="text-[10px] text-slate-500">
          classification confidence {data.weather_event_classification.classification_confidence}
        </span>
        {dataSource === "offline-fallback" && (
          <span className="px-2 py-0.5 rounded border border-amber-500/50 bg-amber-950/30 text-amber-300 text-[10px] font-bold">
            OFFLINE SYNTHETIC
          </span>
        )}
      </div>

      {/* Historical error comparison */}
      <HistoricalComparisonCard
        context={data.historical_error_context}
        currentProbability={data.bust_probability}
        leadDay={data.lead_day}
      />

      {/* Top 3 Atmospheric Drivers (XAI) */}
      <div className="space-y-2">
        <div className="flex items-center gap-1.5 text-slate-400 font-semibold text-[11px]">
          <BrainCircuit className="w-3.5 h-3.5 text-sky-400" />
          <span>TOP ATMOSPHERIC DRIVERS (SHAP DECOMPOSITION)</span>
        </div>

        <div className="space-y-2">
          {data.top_atmospheric_drivers.map((driver, idx) => (
            <div
              key={idx}
              className="p-3 rounded bg-[#080d19] border border-slate-800 hover:border-slate-700 transition-colors"
            >
              <div className="flex items-center justify-between text-xs mb-1">
                <span className="font-semibold text-slate-200">
                  {idx + 1}. {driver.feature}
                </span>
                <span
                  className={`font-bold flex items-center gap-0.5 ${
                    driver.shap_value >= 0 ? "text-rose-400" : "text-emerald-400"
                  }`}
                >
                  {driver.shap_value >= 0 ? (
                    <ArrowUpRight className="w-3.5 h-3.5" />
                  ) : (
                    <ArrowDownRight className="w-3.5 h-3.5" />
                  )}
                  {driver.impact_pct.toFixed(1)}% Impact
                </span>
              </div>
              <p className="text-[11px] text-slate-400 leading-relaxed">
                {driver.scientific_explanation}
              </p>
            </div>
          ))}
        </div>
      </div>

      {/* SHAP Attribution Relative Bar Chart */}
      {data.shap_attributions && data.shap_attributions.length > 0 && (
        <div className="space-y-2 pt-1">
          <div className="flex items-center justify-between text-[11px] text-slate-400 font-semibold">
            <span>FEATURE CONTRIBUTION RELATIVE WEIGHTS</span>
            <span className="text-slate-500 font-normal normal-case">
              baseline {data.shap_base_value.toFixed(3)} + drivers{" "}
              {(data.bust_probability - data.shap_base_value >= 0 ? "+" : "")}
              {(data.bust_probability - data.shap_base_value).toFixed(3)} ={" "}
              {data.bust_probability.toFixed(3)}
            </span>
          </div>
          <div className="space-y-1.5">
            {data.shap_attributions.slice(0, 5).map((attr) => (
              <div key={attr.feature} className="space-y-0.5">
                <div className="flex justify-between items-center text-[10px] text-slate-400">
                  <span className="truncate max-w-[220px] text-slate-300">
                    {attr.name}
                  </span>
                  <span
                    className={
                      attr.direction === "INCREASES_RISK"
                        ? "text-rose-400"
                        : "text-emerald-400"
                    }
                  >
                    {attr.shap_value >= 0 ? "+" : ""}
                    {attr.shap_value.toFixed(3)} ({attr.relative_impact_pct}%)
                  </span>
                </div>
                <div className="w-full bg-slate-900 h-1.5 rounded-full overflow-hidden flex">
                  <div
                    className={`h-full rounded-full ${
                      attr.direction === "INCREASES_RISK"
                        ? "bg-rose-500"
                        : "bg-emerald-500"
                    }`}
                    style={{ width: `${Math.min(100, attr.relative_impact_pct * 2.2)}%` }}
                  />
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Operational Advisory Alert Box */}
      <div
        className={`p-3.5 rounded border-l-4 ${
          data.risk_level === "HIGH"
            ? "bg-rose-950/20 border-rose-500 text-rose-200"
            : data.risk_level === "MODERATE"
            ? "bg-amber-950/20 border-amber-500 text-amber-200"
            : "bg-emerald-950/20 border-emerald-500 text-emerald-200"
        }`}
      >
        <div className="flex items-center gap-2 font-bold text-[11px] mb-1">
          <AlertOctagon className="w-3.5 h-3.5" />
          <span>OPERATIONAL ADVISORY (WMO/IMD METEOROLOGICAL DIRECTIVE)</span>
        </div>
        <p className="text-[11px] leading-relaxed text-slate-300">
          {data.operational_advisory}
        </p>
      </div>

      {/* AI synoptic briefing (optional, opt-in server side) */}
      {data.ai_synoptic_briefing && (
        <div className="p-3.5 rounded border-l-4 border-violet-500 bg-violet-950/20">
          <div className="flex items-center gap-2 font-bold text-[11px] mb-1 text-violet-200">
            <Sparkles className="w-3.5 h-3.5" />
            <span>AI SYNOPTIC BRIEFING (GENERATIVE, NON-AUTHORITATIVE)</span>
          </div>
          <p className="text-[11px] leading-relaxed text-slate-300 whitespace-pre-wrap">
            {data.ai_synoptic_briefing}
          </p>
        </div>
      )}

      {/* Ignored custom features warning */}
      {data.ignored_custom_features.length > 0 && (
        <div className="p-2.5 rounded border border-amber-500/40 bg-amber-950/20 text-[10px] text-amber-200 flex items-start gap-1.5">
          <Info className="w-3 h-3 mt-0.5 shrink-0" />
          <span>
            Ignored out-of-range / non-editable inputs:{" "}
            {data.ignored_custom_features.join(", ")}
          </span>
        </div>
      )}

      {/* Sensitivity Perturbation Simulator Drawer */}
      {showSensitivityModal && (
        <div className="p-3.5 rounded bg-[#070b14] border border-sky-800/60 space-y-3 pt-3">
          <div className="flex items-center justify-between text-xs">
            <span className="font-semibold text-sky-400">
              SYNTHETIC SOUNDING PERTURBATION TEST
            </span>
            <span className="text-[10px] text-slate-500">What-If Analysis</span>
          </div>

          <div className="space-y-2 text-[11px]">
            <div>
              <div className="flex justify-between mb-1">
                <span>Shear Divergence: {shearVal.toFixed(1)} × 10⁻⁵ s⁻¹</span>
              </div>
              <input
                type="range"
                min="0.0"
                max="30.0"
                step="0.5"
                value={shearVal}
                onChange={(e) => setShearVal(parseFloat(e.target.value))}
                className="w-full h-1.5 bg-slate-800 rounded accent-sky-500"
              />
            </div>

            <div>
              <div className="flex justify-between mb-1">
                <span>Precipitable Water: {pwatVal.toFixed(1)} mm</span>
              </div>
              <input
                type="range"
                min="5.0"
                max="90.0"
                step="1.0"
                value={pwatVal}
                onChange={(e) => setPwatVal(parseFloat(e.target.value))}
                className="w-full h-1.5 bg-slate-800 rounded accent-sky-500"
              />
            </div>

            <div>
              <div className="flex justify-between mb-1">
                <span>CAPE Energy: {capeVal} J/kg</span>
              </div>
              <input
                type="range"
                min="0"
                max="6000"
                step="100"
                value={capeVal}
                onChange={(e) => setCapeVal(parseInt(e.target.value, 10))}
                className="w-full h-1.5 bg-slate-800 rounded accent-sky-500"
              />
            </div>

            <p className="text-[10px] text-slate-500 leading-relaxed">
              Single-feature steps can move the probability little: the model is
              a gradient-boosted tree ensemble, so its response is piecewise
              constant. Several parameters must shift together to produce a
              visible change.
            </p>
          </div>

          <div className="flex justify-end gap-2 pt-1">
            <button
              type="button"
              onClick={() => setShowSensitivityModal(false)}
              className="px-2.5 py-1 rounded bg-slate-800 text-slate-400 hover:text-slate-200"
            >
              Cancel
            </button>
            <button
              type="button"
              onClick={handleApplySensitivity}
              className="px-3 py-1 rounded bg-sky-500 text-slate-950 font-semibold hover:bg-sky-400"
            >
              Run Custom Sounding
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
