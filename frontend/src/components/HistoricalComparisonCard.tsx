"use client";

import React from "react";
import { Database, GitCompare, TriangleAlert } from "lucide-react";
import { HistoricalErrorContext } from "@/types";

interface HistoricalComparisonCardProps {
  context: HistoricalErrorContext;
  currentProbability: number;
  leadDay: number;
}

function signalStyle(signal: string): {
  tone: string;
  border: string;
  title: string;
  body: string;
} {
  if (signal === "ANOMALOUSLY_ELEVATED") {
    return {
      tone: "text-rose-300",
      border: "border-rose-500/50 bg-rose-950/20",
      title: "ANOMALOUSLY ELEVATED vs ARCHIVE",
      body: "This forecast is materially less trustworthy than this region's own verification record — treat the guidance with extra caution.",
    };
  }
  if (signal === "BELOW_ARCHIVE_AVERAGE") {
    return {
      tone: "text-emerald-300",
      border: "border-emerald-500/40 bg-emerald-950/20",
      title: "BELOW ARCHIVE AVERAGE",
      body: "Current bust risk is lower than the region's historical rate, i.e. within a comparatively favourable regime.",
    };
  }
  return {
    tone: "text-amber-300",
    border: "border-amber-500/40 bg-amber-950/20",
    title: "CONSISTENT WITH ARCHIVE",
    body: "Current bust risk is typical of this region's historical error characteristics at this lead time.",
  };
}

export default function HistoricalComparisonCard({
  context,
  currentProbability,
  leadDay,
}: HistoricalComparisonCardProps) {
  const style = signalStyle(context.historical_comparison_signal);
  const currentPct = currentProbability * 100;
  const histPct = context.hist_bust_frequency_at_lead_pct;
  const scaleMax = Math.max(currentPct, histPct, 1) * 1.15;

  return (
    <div className="rounded-lg border border-slate-800 bg-[#0c1220] font-mono text-xs text-slate-300 p-4 space-y-3">
      <div className="flex items-center gap-2">
        <GitCompare className="w-3.5 h-3.5 text-sky-400" />
        <span className="text-[11px] font-bold text-slate-200 tracking-wide">
          COMPARISON WITH HISTORICAL ERRORS
        </span>
      </div>

      <div className={`p-2.5 rounded border ${style.border}`}>
        <div className={`text-[10px] font-bold ${style.tone} flex items-center gap-1`}>
          {context.historical_comparison_signal === "ANOMALOUSLY_ELEVATED" ? (
            <TriangleAlert className="w-3 h-3" />
          ) : null}
          {style.title}
        </div>
        <p className="text-[10px] text-slate-400 mt-1 leading-relaxed">{style.body}</p>
      </div>

      {/* Current vs archive bust frequency */}
      <div className="space-y-1.5">
        <div className="flex items-center justify-between text-[10px] text-slate-400">
          <span>Current forecast (Day {leadDay})</span>
          <span className="text-slate-200 font-bold">{currentPct.toFixed(1)}%</span>
        </div>
        <div className="w-full h-2 bg-slate-900 rounded-full overflow-hidden">
          <div
            className="h-full rounded-full bg-sky-500"
            style={{ width: `${(currentPct / scaleMax) * 100}%` }}
          />
        </div>

        <div className="flex items-center justify-between text-[10px] text-slate-400">
          <span>Archive bust rate at this lead</span>
          <span className="text-slate-200 font-bold">{histPct.toFixed(1)}%</span>
        </div>
        <div className="w-full h-2 bg-slate-900 rounded-full overflow-hidden">
          <div
            className="h-full rounded-full bg-slate-500"
            style={{ width: `${(histPct / scaleMax) * 100}%` }}
          />
        </div>
      </div>

      <div className="grid grid-cols-2 gap-2">
        <div className="p-2 rounded bg-[#070b14] border border-slate-800/80">
          <span className="text-[9px] text-slate-500 block">
            ARCHIVE BUST RATE (ALL LEADS)
          </span>
          <span className="text-sm font-bold text-slate-100">
            {context.hist_bust_frequency_pct.toFixed(1)}%
          </span>
        </div>
        <div className="p-2 rounded bg-[#070b14] border border-slate-800/80">
          <span className="text-[9px] text-slate-500 block">
            RATIO TO ARCHIVE
          </span>
          <span
            className={`text-sm font-bold ${
              context.current_vs_historical_ratio >= 1.5
                ? "text-rose-400"
                : context.current_vs_historical_ratio >= 0.8
                ? "text-amber-400"
                : "text-emerald-400"
            }`}
          >
            {context.current_vs_historical_ratio.toFixed(2)}x
          </span>
        </div>
        <div className="p-2 rounded bg-[#070b14] border border-slate-800/80">
          <span className="text-[9px] text-slate-500 block">
            ARCHIVE MEAN ABS ERROR
          </span>
          <span className="text-sm font-bold text-slate-100">
            {context.hist_mean_absolute_error_mm.toFixed(1)} mm
          </span>
        </div>
        <div className="p-2 rounded bg-[#070b14] border border-slate-800/80">
          <span className="text-[9px] text-slate-500 block">ARCHIVE P90 ERROR</span>
          <span className="text-sm font-bold text-amber-300">
            {context.hist_p90_absolute_error_mm.toFixed(1)} mm
          </span>
        </div>
      </div>

      <div className="text-[10px] text-slate-500 flex flex-wrap items-center gap-x-3 gap-y-1 pt-1 border-t border-slate-800">
        <span className="flex items-center gap-1">
          <Database className="w-3 h-3" />
          {context.archive_samples.toLocaleString()} archive samples
        </span>
        <span>worst lead: Day {context.historically_worst_lead_day}</span>
        <span>peak regime: {context.historical_peak_event_type}</span>
      </div>
      <div className="text-[9px] text-slate-600 leading-relaxed">
        {context.archive_provenance}
      </div>
    </div>
  );
}
