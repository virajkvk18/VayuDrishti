"use client";

import React from "react";
import {
  AlertTriangle,
  CheckCircle2,
  Gauge,
  TrendingUp,
} from "lucide-react";
import { DomainTelemetry } from "@/types";

interface MetricsPanelProps {
  telemetry?: DomainTelemetry;
  totalStations: number;
}

export default function MetricsPanel({
  telemetry,
  totalStations,
}: MetricsPanelProps) {
  const meanRisk = telemetry?.mean_bust_risk ?? 0.0;
  const highRisk = telemetry?.high_risk_cells ?? 0;
  const modRisk = telemetry?.moderate_risk_cells ?? 0;
  const lowRisk = telemetry?.low_risk_cells ?? 0;

  return (
    <div className="grid grid-cols-2 md:grid-cols-4 gap-3 font-mono text-xs">
      {/* Mean Bust Probability */}
      <div className="rounded-lg border border-slate-800 bg-[#0c1220] p-3.5 flex flex-col justify-between">
        <div className="flex items-center justify-between text-slate-400 mb-1">
          <span className="text-[11px] font-semibold text-slate-300">MEAN BUST RISK</span>
          <Gauge className="w-3.5 h-3.5 text-sky-400" />
        </div>
        <div className="flex items-baseline gap-2">
          <span
            className={`text-2xl font-bold ${
              meanRisk >= 0.65
                ? "text-rose-400"
                : meanRisk >= 0.35
                ? "text-amber-400"
                : "text-emerald-400"
            }`}
          >
            {meanRisk.toFixed(3)}
          </span>
          <span className="text-[10px] text-slate-500">INDEX (0–1)</span>
        </div>
        <div className="text-[10px] text-slate-500 mt-1 flex items-center gap-1">
          <TrendingUp className="w-3 h-3 text-slate-400" />
          <span>Domain aggregate</span>
        </div>
      </div>

      {/* High Bust Warning Stations */}
      <div className="rounded-lg border border-rose-900/40 bg-rose-950/10 p-3.5 flex flex-col justify-between">
        <div className="flex items-center justify-between text-rose-300 mb-1">
          <span className="text-[11px] font-semibold text-rose-200">HIGH BUST RISK</span>
          <AlertTriangle className="w-3.5 h-3.5 text-rose-400" />
        </div>
        <div className="flex items-baseline gap-2">
          <span className="text-2xl font-bold text-rose-400">{highRisk}</span>
          <span className="text-[10px] text-slate-400">/ {totalStations} STATIONS</span>
        </div>
        <div className="text-[10px] text-rose-400/80 mt-1">
          Critical parameterization breakdown
        </div>
      </div>

      {/* Moderate Variance Stations */}
      <div className="rounded-lg border border-amber-900/40 bg-amber-950/10 p-3.5 flex flex-col justify-between">
        <div className="flex items-center justify-between text-amber-300 mb-1">
          <span className="text-[11px] font-semibold text-amber-200">MODERATE VARIANCE</span>
          <AlertTriangle className="w-3.5 h-3.5 text-amber-400" />
        </div>
        <div className="flex items-baseline gap-2">
          <span className="text-2xl font-bold text-amber-400">{modRisk}</span>
          <span className="text-[10px] text-slate-400">/ {totalStations} STATIONS</span>
        </div>
        <div className="text-[10px] text-amber-400/80 mt-1">
          Elevated ensemble dispersion
        </div>
      </div>

      {/* Nominal Stability Stations */}
      <div className="rounded-lg border border-emerald-900/40 bg-emerald-950/10 p-3.5 flex flex-col justify-between">
        <div className="flex items-center justify-between text-emerald-300 mb-1">
          <span className="text-[11px] font-semibold text-emerald-200">NOMINAL RELIABILITY</span>
          <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
        </div>
        <div className="flex items-baseline gap-2">
          <span className="text-2xl font-bold text-emerald-400">{lowRisk}</span>
          <span className="text-[10px] text-slate-400">/ {totalStations} STATIONS</span>
        </div>
        <div className="text-[10px] text-emerald-400/80 mt-1">
          Physics within empirical envelope
        </div>
      </div>
    </div>
  );
}
