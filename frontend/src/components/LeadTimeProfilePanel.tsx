"use client";

import React, { useState } from "react";
import { Activity, Clock, TrendingUp } from "lucide-react";
import { LeadTimeProfileResponse } from "@/types";

interface LeadTimeProfilePanelProps {
  profile: LeadTimeProfileResponse | null;
  isLoading: boolean;
  activeLeadDay: number;
  onSelectLeadDay: (leadDay: number) => void;
}

export default function LeadTimeProfilePanel({
  profile,
  isLoading,
  activeLeadDay,
  onSelectLeadDay,
}: LeadTimeProfilePanelProps) {
  const [showAllRegions, setShowAllRegions] = useState(false);

  if (isLoading) {
    return (
      <div className="rounded-lg border border-slate-800 bg-[#0c1220] p-5 font-mono text-xs text-slate-400 flex items-center gap-2">
        <Activity className="w-4 h-4 animate-spin text-sky-400" />
        Loading Day 1 to Day 10 skill profile...
      </div>
    );
  }

  if (!profile) {
    return (
      <div className="rounded-lg border border-slate-800 bg-[#0c1220] p-5 font-mono text-xs text-slate-500">
        Lead-time profile unavailable.
      </div>
    );
  }

  const entries = profile.domain_profile;
  const maxProb = Math.max(...entries.map((e) => e.mean_bust_probability), 0.01);
  const visibleRegions = showAllRegions ? profile.regions : profile.regions.slice(0, 8);

  return (
    <div className="rounded-lg border border-slate-800 bg-[#0c1220] font-mono text-xs">
      <div className="flex flex-wrap items-center justify-between gap-2 px-4 py-2.5 border-b border-slate-800">
        <div className="flex items-center gap-2">
          <TrendingUp className="w-3.5 h-3.5 text-sky-400" />
          <span className="text-[11px] font-bold text-slate-200 tracking-wide">
            LEAD-TIME CONFIDENCE PROFILE (DAY 1-10)
          </span>
        </div>
        <div className="text-[10px] text-slate-500">
          lowest risk Day {profile.lowest_risk_lead_day} · highest risk Day{" "}
          {profile.highest_risk_lead_day}
        </div>
      </div>

      {/* Domain confidence decay curve */}
      <div className="px-4 pt-3 pb-2">
        <div className="flex items-end gap-1 h-[92px]">
          {entries.map((entry) => {
            const height = (entry.mean_bust_probability / maxProb) * 100;
            const isActive = entry.lead_day === activeLeadDay;
            const tone =
              entry.mean_bust_probability >= 0.65
                ? "#ef4444"
                : entry.mean_bust_probability >= 0.35
                ? "#eab308"
                : "#10b981";
            return (
              <button
                key={entry.lead_day}
                type="button"
                onClick={() => onSelectLeadDay(entry.lead_day)}
                className="flex-1 flex flex-col items-center justify-end gap-1 group h-full"
                title={`Day ${entry.lead_day}: ${(
                  entry.mean_bust_probability * 100
                ).toFixed(1)}% bust probability, ${(
                  entry.error_prone_cells
                )} error-prone cells, expected error ${entry.mean_expected_precip_error_mm} mm`}
              >
                <span
                  className={`text-[9px] ${isActive ? "text-slate-100" : "text-slate-500"}`}
                >
                  {(entry.mean_bust_probability * 100).toFixed(0)}
                </span>
                <span
                  className="w-full rounded-t transition-all"
                  style={{
                    height: `${Math.max(4, height)}%`,
                    background: tone,
                    opacity: isActive ? 1 : 0.65,
                    outline: isActive ? `1px solid ${tone}` : "none",
                  }}
                />
                <span
                  className={`text-[9px] ${isActive ? "text-slate-100 font-bold" : "text-slate-500"}`}
                >
                  D{entry.lead_day}
                </span>
              </button>
            );
          })}
        </div>
        <div className="flex items-center justify-between text-[10px] text-slate-500 mt-2 pt-2 border-t border-slate-800">
          <span>Bar height = mean bust probability across all regions</span>
          <span>
            Day {activeLeadDay} mean expected error:{" "}
            <span className="text-amber-300">
              ±
              {entries.find((e) => e.lead_day === activeLeadDay)
                ?.mean_expected_precip_error_mm ?? 0}{" "}
              mm
            </span>
          </span>
        </div>
      </div>

      {/* Per-region decay matrix */}
      <div className="px-4 pb-3">
        <div className="flex items-center justify-between mb-1.5">
          <span className="text-[10px] text-slate-400 font-semibold flex items-center gap-1">
            <Clock className="w-3 h-3" />
            PER-REGION DECAY MATRIX
          </span>
          <button
            type="button"
            onClick={() => setShowAllRegions((v) => !v)}
            className="text-[10px] px-1.5 py-0.5 rounded border border-slate-700 bg-slate-800 text-slate-300 hover:bg-slate-700"
          >
            {showAllRegions
              ? "Top 8 only"
              : `All ${profile.regions.length} regions`}
          </button>
        </div>

        <div className="space-y-1">
          {visibleRegions.map((region) => {
            const activeCell = region.series.find(
              (p) => p.lead_day === activeLeadDay
            );
            return (
              <div key={region.grid_id} className="flex items-center gap-2">
                <span className="text-[10px] text-slate-400 w-[132px] shrink-0 truncate">
                  {region.name.split(/[,(]/)[0].trim()}
                </span>
                <div className="flex-1 flex gap-0.5">
                  {region.series.map((point) => {
                    const intensity = Math.max(0.12, point.bust_probability);
                    const tone =
                      point.risk_level === "HIGH"
                        ? "#ef4444"
                        : point.risk_level === "MODERATE"
                        ? "#eab308"
                        : "#10b981";
                    return (
                      <button
                        key={point.lead_day}
                        type="button"
                        onClick={() => onSelectLeadDay(point.lead_day)}
                        className="flex-1 h-3.5 rounded-sm transition-all hover:scale-y-150"
                        style={{
                          background: tone,
                          opacity: point.lead_day === activeLeadDay ? 1 : 0.25 + intensity * 0.6,
                        }}
                        title={`${region.name} · Day ${point.lead_day}: ${(
                          point.bust_probability * 100
                        ).toFixed(1)}% bust · ${point.confidence_percentage.toFixed(
                          1
                        )}% confidence`}
                      />
                    );
                  })}
                </div>
                <span className="text-[10px] text-slate-500 w-[86px] text-right shrink-0">
                  peak D{region.peak_lead_day} ·{" "}
                  {region.first_high_risk_lead_day
                    ? `high D${region.first_high_risk_lead_day}`
                    : "no high"}
                </span>
                {activeCell && (
                  <span className="text-[10px] text-sky-300 w-[46px] text-right shrink-0">
                    {activeCell.confidence_percentage.toFixed(0)}%
                  </span>
                )}
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
