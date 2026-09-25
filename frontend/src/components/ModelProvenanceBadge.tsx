"use client";

import React, { useState } from "react";
import {
  BadgeCheck,
  ChevronDown,
  ChevronUp,
  Cpu,
  Radio,
  WifiOff,
} from "lucide-react";
import { ModelMetadata } from "@/types";

interface ModelProvenanceBadgeProps {
  modelInfo: ModelMetadata | null;
  dataSource: "live" | "offline-fallback";
  error: string | null;
}

export default function ModelProvenanceBadge({
  modelInfo,
  dataSource,
  error,
}: ModelProvenanceBadgeProps) {
  const [open, setOpen] = useState(false);
  const skill = modelInfo?.held_out_skill;
  const isLive = dataSource === "live";

  return (
    <div className="rounded-lg border border-slate-800 bg-[#0c1220] font-mono text-xs">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="w-full flex flex-wrap items-center justify-between gap-2 px-4 py-2.5 text-left hover:bg-slate-900/40 transition-colors"
      >
        <div className="flex items-center gap-2 flex-wrap">
          {isLive ? (
            <Radio className="w-3.5 h-3.5 text-emerald-400" />
          ) : (
            <WifiOff className="w-3.5 h-3.5 text-amber-400" />
          )}
          <span
            className={`px-1.5 py-0.5 rounded border text-[10px] font-bold ${
              isLive
                ? "border-emerald-500/40 bg-emerald-950/30 text-emerald-300"
                : "border-amber-500/50 bg-amber-950/30 text-amber-300"
            }`}
          >
            {isLive ? "LIVE MODEL OUTPUT" : "OFFLINE SYNTHETIC BASELINE"}
          </span>
          <span className="text-[11px] text-slate-200 flex items-center gap-1">
            <Cpu className="w-3 h-3 text-sky-400" />
            {modelInfo?.algorithm || "model metadata unavailable"}
          </span>
          {skill?.roc_auc != null && (
            <span className="text-[10px] text-slate-500">
              held-out AUC {skill.roc_auc.toFixed(3)}
            </span>
          )}
        </div>
        {open ? (
          <ChevronUp className="w-3.5 h-3.5 text-slate-500" />
        ) : (
          <ChevronDown className="w-3.5 h-3.5 text-slate-500" />
        )}
      </button>

      {isLive && error === null && skill?.roc_auc != null && (
        <div className="px-4 pb-2.5">
          <div className="text-[10px] text-slate-500 flex items-center gap-1">
            <BadgeCheck className="w-3 h-3 text-emerald-400" />
            probabilities are calibrated on a held-out split (ECE{" "}
            {skill.expected_calibration_error?.toFixed(4)})
          </div>
        </div>
      )}

      {open && (
        <div className="px-4 pb-4 space-y-2 border-t border-slate-800 pt-3">
          {!isLive && (
            <div className="p-2.5 rounded border border-amber-500/40 bg-amber-950/20 text-[10px] text-amber-200 leading-relaxed">
              The backend API could not be reached{error ? `: ${error}` : ""}. The
              dashboard is rendering a deterministic synthetic baseline, NOT model
              predictions. Do not use these values for operational decisions.
            </div>
          )}

          {modelInfo?.bust_definition && (
            <div className="text-[10px] text-slate-400">
              <span className="text-slate-500">Bust definition: </span>
              {String(
                (modelInfo.bust_definition as Record<string, unknown>)
                  .variable ?? "24h accumulated precipitation"
              )}{" "}
              error &gt;{" "}
              {String(
                (modelInfo.bust_definition as Record<string, unknown>)
                  .error_threshold_mm ?? 25
              )}{" "}
              mm
            </div>
          )}

          {skill && (
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
              <div className="p-2 rounded bg-[#070b14] border border-slate-800/80">
                <span className="text-[9px] text-slate-500 block">ROC-AUC</span>
                <span className="text-sm font-bold text-slate-100">
                  {skill.roc_auc?.toFixed(3) ?? "n/a"}
                </span>
                {skill.roc_auc_cluster_ci90 && (
                  <span className="text-[9px] text-slate-500">
                    CI [{skill.roc_auc_cluster_ci90[0].toFixed(3)},{" "}
                    {skill.roc_auc_cluster_ci90[1].toFixed(3)}]
                  </span>
                )}
              </div>
              <div className="p-2 rounded bg-[#070b14] border border-slate-800/80">
                <span className="text-[9px] text-slate-500 block">BRIER SKILL</span>
                <span
                  className={`text-sm font-bold ${
                    (skill.brier_skill_score ?? 0) > 0
                      ? "text-emerald-400"
                      : "text-rose-400"
                  }`}
                >
                  {skill.brier_skill_score != null
                    ? `${skill.brier_skill_score > 0 ? "+" : ""}${skill.brier_skill_score.toFixed(3)}`
                    : "n/a"}
                </span>
              </div>
              <div className="p-2 rounded bg-[#070b14] border border-slate-800/80">
                <span className="text-[9px] text-slate-500 block">ERROR MAE</span>
                <span className="text-sm font-bold text-slate-100">
                  {skill.error_model_mae_mm?.toFixed(1) ?? "n/a"} mm
                </span>
                <span className="text-[9px] text-slate-500">
                  clim {skill.error_model_mae_climatology_mm?.toFixed(1) ?? "n/a"}
                </span>
              </div>
              <div className="p-2 rounded bg-[#070b14] border border-slate-800/80">
                <span className="text-[9px] text-slate-500 block">
                  SKILL VS CLIMATOLOGY
                </span>
                <span className="text-sm font-bold text-sky-300">
                  {skill.error_model_skill_vs_climatology_pct?.toFixed(1) ?? "n/a"}%
                </span>
              </div>
            </div>
          )}

          {modelInfo?.error_model_algorithm && (
            <div className="text-[10px] text-slate-500">
              <span className="text-slate-600">Error magnitude model: </span>
              {modelInfo.error_model_algorithm}
            </div>
          )}
          {modelInfo?.attribution_method && (
            <div className="text-[10px] text-slate-500">
              <span className="text-slate-600">Attribution: </span>
              {modelInfo.attribution_method}
            </div>
          )}
          {modelInfo?.trained_utc && (
            <div className="text-[10px] text-slate-500">
              <span className="text-slate-600">Trained: </span>
              {modelInfo.trained_utc}
            </div>
          )}
          {modelInfo?.archive && (
            <div className="text-[10px] text-slate-500 leading-relaxed">
              <span className="text-slate-600">Archive: </span>
              {String(
                (modelInfo.archive as Record<string, unknown>).provenance ??
                  "synthetic verification archive"
              )}
            </div>
          )}
          {modelInfo?.reliability && modelInfo.reliability.length > 0 && (
            <div className="space-y-1">
              <span className="text-[10px] text-slate-400 font-semibold">
                RELIABILITY (held-out)
              </span>
              <div className="grid grid-cols-6 gap-1">
                {modelInfo.reliability.map((bin) => (
                  <div
                    key={String(bin.bin ?? bin.lower)}
                    className="p-1 rounded bg-[#070b14] border border-slate-800/80 text-center"
                  >
                    <span className="text-[9px] text-slate-500 block">
                      {String(bin.lower ?? "—")}
                    </span>
                    <span className="text-[10px] text-slate-200 font-bold">
                      {bin.mean_predicted != null
                        ? Number(bin.mean_predicted).toFixed(2)
                        : "—"}
                    </span>
                    <span className="text-[9px] text-emerald-400">
                      {bin.observed_frequency != null
                        ? Number(bin.observed_frequency).toFixed(2)
                        : "—"}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
