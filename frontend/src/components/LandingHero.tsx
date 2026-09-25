"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import {
  Activity,
  ArrowRight,
  Compass,
  Cpu,
  Layers,
  ShieldCheck,
  TrendingDown,
  Wind,
} from "lucide-react";
import { fetchHealth } from "@/lib/api";
import { HealthTelemetry } from "@/types";

export default function LandingHero() {
  const [telemetry, setTelemetry] = useState<HealthTelemetry | null>(null);
  const [isBackendLive, setIsBackendLive] = useState<boolean | null>(null);
  const [currentTime, setCurrentTime] = useState<string>("");

  useEffect(() => {
    fetchHealth().then((res) => {
      setTelemetry(res.data);
      setIsBackendLive(res.source === "live" && res.data.model_ready);
    });
    const updateUtc = () => {
      const now = new Date();
      setCurrentTime(now.toISOString().replace("T", " ").substring(0, 19) + " UTC");
    };
    updateUtc();
    const interval = setInterval(updateUtc, 1000);
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="relative min-h-screen flex flex-col justify-between overflow-hidden bg-[#090d16] text-slate-100">
      {/* Background data grid styling */}
      <div className="absolute inset-0 bg-grid-pattern opacity-60 pointer-events-none" />
      <div className="absolute top-0 right-1/4 w-[600px] h-[600px] bg-sky-500/5 blur-[140px] pointer-events-none rounded-full" />
      <div className="absolute bottom-10 left-10 w-[500px] h-[500px] bg-emerald-500/5 blur-[120px] pointer-events-none rounded-full" />

      {/* Top Telemetry Header */}
      <header className="relative z-10 border-b border-slate-800/80 bg-[#0b101d]/90 backdrop-blur-md px-6 py-3.5">
        <div className="max-w-7xl mx-auto flex flex-wrap items-center justify-between gap-4 text-xs font-mono">
          <div className="flex items-center gap-3">
            <div className="flex items-center gap-2 font-semibold tracking-wider text-slate-100 text-sm">
              <span className="inline-block w-2.5 h-2.5 rounded-sm bg-sky-500 shadow-[0_0_8px_rgba(56,189,248,0.8)]" />
              <span>VayuDRISHTI</span>
              <span className="text-[10px] text-slate-400 font-normal uppercase px-1.5 py-0.5 rounded border border-slate-700 bg-slate-800/60">
                Core v3.0
              </span>
            </div>
            <span className="text-slate-600 hidden sm:inline">|</span>
            <div className="hidden sm:flex items-center gap-2 text-slate-400">
              <Compass className="w-3.5 h-3.5 text-sky-400" />
              <span>NWP DIAGNOSTIC SUITE</span>
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-5 text-slate-300">
            <div className="flex items-center gap-2">
              <span className="text-slate-500">SYSTEM:</span>
              <span
                className={`flex items-center gap-1.5 font-medium ${
                  isBackendLive === false ? "text-amber-400" : "text-emerald-400"
                }`}
              >
                <span
                  className={`w-2 h-2 rounded-full animate-pulse ${
                    isBackendLive === false ? "bg-amber-400" : "bg-emerald-400"
                  }`}
                />
                {isBackendLive === false
                  ? "MODEL ARTIFACTS UNAVAILABLE"
                  : telemetry?.status || "OPERATIONAL"}
              </span>
            </div>

            <div className="hidden md:flex items-center gap-2">
              <span className="text-slate-500">BASE MODEL:</span>
              <span className="text-sky-300 font-medium">
                {telemetry?.nwp_model_base || "NCMRWF-Irrespective Diagnostic v3.0"}
              </span>
            </div>

            <div className="hidden lg:flex items-center gap-2">
              <span className="text-slate-500">GRID DOMAIN:</span>
              <span className="text-slate-300">8.0°N–37.0°N / 68.0°E–97.0°E</span>
            </div>

            <div className="flex items-center gap-2 pl-2 border-l border-slate-800 text-slate-400">
              <Activity className="w-3.5 h-3.5 text-slate-400" />
              <span>{currentTime || "SYNCING CLOCK..."}</span>
            </div>
          </div>
        </div>
      </header>

      {/* Main Scientific Hero Content */}
      <main className="relative z-10 max-w-7xl mx-auto px-6 py-12 lg:py-20 flex-1 flex flex-col justify-center">
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-12 items-center">
          {/* Left Column: Mission & Scientific Rationale */}
          <div className="lg:col-span-7 space-y-6">
            <div className="inline-flex items-center gap-2 px-3 py-1 rounded border border-sky-500/30 bg-sky-950/20 text-sky-300 font-mono text-xs">
              <Layers className="w-3.5 h-3.5 text-sky-400" />
              <span>ATMOSPHERIC TENSOR UNCERTAINTY QUANTIFICATION</span>
            </div>

            <h1 className="text-3xl sm:text-4xl lg:text-5xl font-bold tracking-tight text-slate-50 leading-[1.15]">
              Diagnostic Intelligence for High-Consequence NWP Forecast Busts
            </h1>

            <p className="text-base sm:text-lg text-slate-300 leading-relaxed font-light">
              Numerical Weather Prediction (NWP) models suffer catastrophic failure modes during complex convective and baroclinic transitions over the Indian subcontinent.
              <strong className="text-slate-100 font-medium"> VayuDRISHTI</strong> monitors 850–200 hPa shear divergence, moisture flux discrepancies, and vertical lapse rates to detect forecast bust risks before operational dissemination.
            </p>

            <div className="pt-2 flex flex-wrap items-center gap-4">
              <Link
                href="/dashboard"
                id="launch-workspace-btn"
                className="inline-flex items-center gap-2.5 px-6 py-3.5 rounded bg-sky-500 hover:bg-sky-400 text-slate-950 font-semibold text-sm tracking-wide transition-all shadow-[0_0_20px_rgba(56,189,248,0.35)] hover:shadow-[0_0_25px_rgba(56,189,248,0.55)] active:scale-[0.99]"
              >
                <span>Launch Diagnostic Workspace</span>
                <ArrowRight className="w-4 h-4" />
              </Link>

              <div className="flex items-center gap-2 text-xs font-mono text-slate-400 px-3 py-2 rounded border border-slate-800 bg-[#0f172a]/60">
                <span className="w-1.5 h-1.5 rounded-full bg-sky-400" />
                <span>LEAD HORIZON: DAY 1 TO DAY 10</span>
              </div>
            </div>

            {/* Scientific Impact Breakdown */}
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 pt-6 border-t border-slate-800/80">
              <div className="p-3.5 rounded border border-slate-800/80 bg-[#0d1322]/80">
                <div className="flex items-center gap-2 text-sky-400 mb-1 font-mono text-xs">
                  <Wind className="w-4 h-4" />
                  <span>SHEAR DIVERGENCE</span>
                </div>
                <div className="text-xl font-bold font-mono text-slate-100">850–200 hPa</div>
                <div className="text-xs text-slate-400 mt-1">
                  Detects convective parameterization breakdown along monsoon troughs.
                </div>
              </div>

              <div className="p-3.5 rounded border border-slate-800/80 bg-[#0d1322]/80">
                <div className="flex items-center gap-2 text-amber-400 mb-1 font-mono text-xs">
                  <TrendingDown className="w-4 h-4" />
                  <span>BUST PROBABILITY</span>
                </div>
                <div className="text-xl font-bold font-mono text-slate-100">0.00 – 1.00</div>
                <div className="text-xs text-slate-400 mt-1">
                  Calibrated risk index against 30-member GFS/GEFS ensemble dispersion.
                </div>
              </div>

              <div className="p-3.5 rounded border border-slate-800/80 bg-[#0d1322]/80">
                <div className="flex items-center gap-2 text-emerald-400 mb-1 font-mono text-xs">
                  <Cpu className="w-4 h-4" />
                  <span>XAI ATTRIBUTION</span>
                </div>
                <div className="text-xl font-bold font-mono text-slate-100">SHAP Tensor</div>
                <div className="text-xs text-slate-400 mt-1">
                  Translates high-dimensional variance into operational physical drivers.
                </div>
              </div>
            </div>
          </div>

          {/* Right Column: Live Telemetry Terminal Card */}
          <div className="lg:col-span-5">
            <div className="rounded-lg border border-slate-800 bg-[#0b101e] shadow-2xl p-5 relative font-mono text-xs">
              <div className="flex items-center justify-between pb-3 border-b border-slate-800 mb-4">
                <div className="flex items-center gap-2">
                  <span className="w-2.5 h-2.5 rounded-full bg-rose-500/80" />
                  <span className="w-2.5 h-2.5 rounded-full bg-amber-500/80" />
                  <span className="w-2.5 h-2.5 rounded-full bg-emerald-500/80" />
                  <span className="ml-2 text-slate-400 text-[11px] font-semibold tracking-wider">
                    OPERATIONAL_INSPECTION_BUFFER
                  </span>
                </div>
                <span className="text-[10px] text-slate-500">CH-04 / LAT: 20.31°N</span>
              </div>

              <div className="space-y-3">
                <div className="p-3 rounded bg-[#070b14] border border-slate-800/80">
                  <div className="flex justify-between items-center text-slate-400 mb-1">
                    <span>TARGET STATION</span>
                    <span className="text-sky-400 font-semibold">IND-E-16 (Odisha Corridor)</span>
                  </div>
                  <div className="flex justify-between items-center text-slate-400 mb-1">
                    <span>EVALUATION LEAD TIME</span>
                    <span className="text-slate-200">DAY 3 (72-HOUR OUTLOOK)</span>
                  </div>
                  <div className="flex justify-between items-center text-slate-400">
                    <span>CONFIDENCE METRIC</span>
                    <span className="text-amber-400 font-semibold">54.2% [MODERATE]</span>
                  </div>
                </div>

                <div className="space-y-2">
                  <div className="text-[11px] text-slate-400 font-medium">PRIMARY ATTRIBUTION WEIGHTS (SHAP):</div>
                  <div className="space-y-1.5">
                    <div>
                      <div className="flex justify-between text-[11px] mb-0.5">
                        <span className="text-slate-300">850-200 hPa Shear Divergence</span>
                        <span className="text-rose-400">+34.2%</span>
                      </div>
                      <div className="w-full bg-slate-800 h-1.5 rounded-full overflow-hidden">
                        <div className="bg-rose-500 h-1.5 rounded-full" style={{ width: "78%" }} />
                      </div>
                    </div>

                    <div>
                      <div className="flex justify-between text-[11px] mb-0.5">
                        <span className="text-slate-300">850-500 hPa Vertical Lapse Rate</span>
                        <span className="text-amber-400">+26.8%</span>
                      </div>
                      <div className="w-full bg-slate-800 h-1.5 rounded-full overflow-hidden">
                        <div className="bg-amber-400 h-1.5 rounded-full" style={{ width: "62%" }} />
                      </div>
                    </div>

                    <div>
                      <div className="flex justify-between text-[11px] mb-0.5">
                        <span className="text-slate-300">Historical Error Variance (σ)</span>
                        <span className="text-sky-400">+22.1%</span>
                      </div>
                      <div className="w-full bg-slate-800 h-1.5 rounded-full overflow-hidden">
                        <div className="bg-sky-400 h-1.5 rounded-full" style={{ width: "51%" }} />
                      </div>
                    </div>
                  </div>
                </div>

                <div className="p-3 rounded bg-slate-900/90 border-l-2 border-amber-400 text-slate-300 text-[11px] leading-relaxed">
                  <strong className="text-amber-300 block mb-0.5">SYNTACTIC ADVISORY:</strong>
                  Baroclinic moisture flux decoupling detected. High likelihood of precipitation displacement (±28.4 mm). Recommend shifting operational ensemble weight to high-resolution WRF/Doppler nowcasting.
                </div>
              </div>

              <div className="mt-4 pt-3 border-t border-slate-800/80 flex items-center justify-between text-[11px] text-slate-500">
                <span className="flex items-center gap-1.5">
                  <ShieldCheck className="w-3.5 h-3.5 text-emerald-400" />
                  WMO / IMD Validation Schema
                </span>
                <span>STATUS: ACTIVE_FEED</span>
              </div>
            </div>
          </div>
        </div>
      </main>

      {/* Scientific Telemetry Footer */}
      <footer className="relative z-10 border-t border-slate-800/80 bg-[#070b14] px-6 py-4">
        <div className="max-w-7xl mx-auto flex flex-wrap items-center justify-between gap-4 text-xs font-mono text-slate-500">
          <div className="flex items-center gap-4">
            <span>VayuDRISHTI ATMOSPHERIC PLATFORM</span>
            <span>•</span>
            <span>NOAA/NCEP GFS DATA PIPELINE</span>
            <span>•</span>
            <span>OPERATIONAL METEOROLOGY DIAGNOSTICS</span>
          </div>
          <div className="flex items-center gap-3 text-slate-400">
            <span className="inline-block w-2 h-2 rounded-full bg-emerald-500" />
            <span>ALL SENSORS SYNCED [20 REGIONAL STATIONS]</span>
          </div>
        </div>
      </footer>
    </div>
  );
}
