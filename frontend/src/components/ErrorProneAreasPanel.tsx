"use client";

import React from "react";
import {
  AlertTriangle,
  ArrowUpRight,
  History,
  MapPin,
} from "lucide-react";
import { ErrorProneArea } from "@/types";

interface ErrorProneAreasPanelProps {
  areas: ErrorProneArea[];
  leadDay: number;
  selectedGridId: string | null;
  totalCells: number;
  onSelect: (gridId: string) => void;
}

const SIGNAL_COPY: Record<
  string,
  { label: string; tone: string; description: string }
> = {
  ANOMALOUSLY_ELEVATED: {
    label: "ANOMALOUSLY ELEVATED",
    tone: "text-rose-300",
    description: "Bust risk is well above this region's own historical frequency",
  },
  CONSISTENT_WITH_ARCHIVE: {
    label: "CONSISTENT WITH ARCHIVE",
    tone: "text-amber-300",
    description: "Bust risk is typical of the region's verification record",
  },
  BELOW_ARCHIVE_AVERAGE: {
    label: "BELOW ARCHIVE AVERAGE",
    tone: "text-emerald-300",
    description: "Bust risk is lower than the region's historical frequency",
  },
};

export default function ErrorProneAreasPanel({
  areas,
  leadDay,
  selectedGridId,
  totalCells,
  onSelect,
}: ErrorProneAreasPanelProps) {
  const highCount = areas.filter((a) => a.risk_level === "HIGH").length;
  const moderateCount = areas.filter((a) => a.risk_level === "MODERATE").length;
  // The flag uses a fixed 0.35 probability threshold, but the base rate itself
  // climbs with lead time, so at long horizons most of the domain trips it.
  // Saying so prevents a saturated count from reading as a broken detector.
  const saturated = totalCells > 0 && areas.length / totalCells > 0.5;

  return (
    <div className="rounded-lg border border-slate-800 bg-[#0c1220] font-mono text-xs">
      <div className="flex flex-wrap items-center justify-between gap-2 px-4 py-2.5 border-b border-slate-800">
        <div className="flex items-center gap-2">
          <AlertTriangle className="w-3.5 h-3.5 text-rose-400" />
          <span className="text-[11px] font-bold text-slate-200 tracking-wide">
            ERROR-PRONE AREAS
          </span>
          <span className="text-[10px] text-slate-500">
            regions where the forecast is least trustworthy at Day {leadDay}
          </span>
        </div>
        <div className="flex items-center gap-2 text-[10px]">
          <span className="px-1.5 py-0.5 rounded border border-rose-500/40 bg-rose-950/30 text-rose-300">
            {highCount} HIGH
          </span>
          <span className="px-1.5 py-0.5 rounded border border-amber-500/40 bg-amber-950/30 text-amber-300">
            {moderateCount} ELEVATED
          </span>
        </div>
      </div>

      {saturated && areas.length > 0 && (
        <div className="px-4 py-2 text-[10px] text-amber-300/90 border-b border-slate-800 bg-amber-950/10">
          At Day {leadDay} the domain-wide bust base rate is itself elevated, so
          most regions cross the 0.35 threshold. The ordering below is the
          useful signal, not the count.
        </div>
      )}

      {areas.length === 0 ? (
        <div className="px-4 py-6 text-center text-[11px] text-emerald-300">
          No region exceeds the moderate-bust threshold at Day {leadDay}.
        </div>
      ) : (
        <div className="max-h-[320px] overflow-y-auto divide-y divide-slate-800/70">
          {areas.map((area) => {
            const signal = SIGNAL_COPY[area.historical_comparison_signal];
            const isSelected = area.grid_id === selectedGridId;
            return (
              <button
                key={area.grid_id}
                type="button"
                onClick={() => onSelect(area.grid_id)}
                className={`w-full text-left px-4 py-2.5 hover:bg-slate-900/60 transition-colors ${
                  isSelected ? "bg-sky-500/10" : ""
                }`}
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <div className="flex items-center gap-1.5">
                      <MapPin
                        className="w-3 h-3 shrink-0"
                        style={{ color: area.risk_color }}
                      />
                      <span className="font-bold text-slate-100 truncate">
                        {area.name}
                      </span>
                      <span className="text-[10px] text-slate-500 shrink-0">
                        {area.grid_id}
                      </span>
                    </div>
                    <div className="text-[10px] text-slate-500 mt-0.5 truncate">
                      {area.subdivision} · {area.event_type}
                    </div>
                  </div>

                  <div className="text-right shrink-0">
                    <div
                      className="text-base font-bold leading-none"
                      style={{ color: area.risk_color }}
                    >
                      {(area.confidence_percentage).toFixed(0)}%
                      <span className="text-[9px] text-slate-500 ml-0.5">
                        CONF
                      </span>
                    </div>
                    <div className="text-[10px] text-slate-400 mt-0.5">
                      ±{area.expected_precip_error_mm} mm
                    </div>
                  </div>
                </div>

                <div className="flex flex-wrap items-center gap-x-3 gap-y-1 mt-1.5 text-[10px]">
                  <span
                    className="px-1.5 py-0.5 rounded border"
                    style={{
                      color: area.risk_color,
                      borderColor: `${area.risk_color}66`,
                      background: `${area.risk_color}1a`,
                    }}
                  >
                    {area.reliability_flag.replace(/_/g, " ")}
                  </span>
                  <span className="flex items-center gap-1 text-slate-400">
                    <History className="w-3 h-3" />
                    archive bust rate {area.hist_bust_freq_pct.toFixed(1)}%
                  </span>
                  <span className="flex items-center gap-1 text-slate-400">
                    <ArrowUpRight className="w-3 h-3" />
                    {area.current_vs_historical_ratio.toFixed(2)}x archive
                  </span>
                  {signal && (
                    <span className={signal.tone} title={signal.description}>
                      {signal.label}
                    </span>
                  )}
                </div>

                {area.primary_driver && (
                  <div className="text-[10px] text-slate-500 mt-1">
                    Primary driver: {area.primary_driver.replace(/_/g, " ")}
                  </div>
                )}
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}
