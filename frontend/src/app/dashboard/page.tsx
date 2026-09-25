"use client";

import React, { useEffect, useState, useCallback } from "react";
import Link from "next/link";
import dynamic from "next/dynamic";
import {
  Activity,
  ArrowLeft,
  Compass,
  RefreshCw,
} from "lucide-react";

import TimeLeadSlider from "@/components/TimeLeadSlider";
import MetricsPanel from "@/components/MetricsPanel";
import XAIExplanationCard from "@/components/XAIExplanationCard";
import ErrorProneAreasPanel from "@/components/ErrorProneAreasPanel";
import LeadTimeProfilePanel from "@/components/LeadTimeProfilePanel";
import ModelProvenanceBadge from "@/components/ModelProvenanceBadge";
import {
  fetchForecastGrid,
  explainBust,
  fetchHealth,
  fetchLeadTimeProfile,
  fetchModelInfo,
} from "@/lib/api";
import {
  ApiResult,
  ForecastGridResponse,
  ExplainBustResponse,
  HealthTelemetry,
  LeadTimeProfileResponse,
  ModelMetadata,
} from "@/types";

// Dynamically import MapContainer with SSR disabled to prevent Leaflet hydration conflicts
const MapContainer = dynamic(() => import("@/components/MapContainer"), {
  ssr: false,
  loading: () => (
    <div className="w-full h-[520px] lg:h-[620px] rounded-lg border border-slate-800 bg-[#070b14] flex flex-col items-center justify-center font-mono text-xs text-slate-500 gap-3">
      <Compass className="w-8 h-8 text-sky-400 animate-spin" />
      <span>INITIALIZING GEOSPATIAL RADAR DOMAIN...</span>
    </div>
  ),
});

export default function DashboardPage() {
  const [leadDay, setLeadDay] = useState<number>(1);
  const [selectedGridId, setSelectedGridId] = useState<string>("IND-E-16");
  const [gridData, setGridData] = useState<ForecastGridResponse | null>(null);
  const [explainData, setExplainData] = useState<ExplainBustResponse | null>(null);
  const [telemetry, setTelemetry] = useState<HealthTelemetry | null>(null);
  const [profile, setProfile] = useState<LeadTimeProfileResponse | null>(null);
  const [modelInfo, setModelInfo] = useState<ModelMetadata | null>(null);
  const [isLoadingGrid, setIsLoadingGrid] = useState<boolean>(true);
  const [isLoadingExplain, setIsLoadingExplain] = useState<boolean>(false);
  const [isLoadingProfile, setIsLoadingProfile] = useState<boolean>(true);
  const [gridSource, setGridSource] = useState<"live" | "offline-fallback">(
    "live"
  );
  const [gridError, setGridError] = useState<string | null>(null);
  const [utcTimestamp, setUtcTimestamp] = useState<string>("");

  // Refresh clock
  useEffect(() => {
    const updateTime = () => {
      const now = new Date();
      setUtcTimestamp(now.toISOString().replace("T", " ").substring(0, 19) + " UTC");
    };
    updateTime();
    const interval = setInterval(updateTime, 1000);
    return () => clearInterval(interval);
  }, []);

  // Fetch health telemetry and model provenance once
  useEffect(() => {
    fetchHealth().then((res) => setTelemetry(res.data));
    fetchModelInfo().then((res) => setModelInfo(res.data));
  }, []);

  // Load the Day 1-10 profile once; it is lead-time invariant
  useEffect(() => {
    let cancelled = false;
    setIsLoadingProfile(true);
    fetchLeadTimeProfile()
      .then((res) => {
        if (!cancelled) setProfile(res.data);
      })
      .finally(() => {
        if (!cancelled) setIsLoadingProfile(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  // Load grid for active lead day
  const loadForecastGrid = useCallback(async (day: number) => {
    setIsLoadingGrid(true);
    try {
      const res: ApiResult<ForecastGridResponse> = await fetchForecastGrid(day);
      setGridData(res.data);
      setGridSource(res.source);
      setGridError(res.error);
    } finally {
      setIsLoadingGrid(false);
    }
  }, []);

  // Load XAI breakdown for selected station and lead day
  const loadExplanation = useCallback(
    async (gridId: string, day: number, customFeatures?: Record<string, number>) => {
      setIsLoadingExplain(true);
      try {
        const res = await explainBust(gridId, day, customFeatures);
        setExplainData(res.data);
      } finally {
        setIsLoadingExplain(false);
      }
    },
    []
  );

  // Trigger grid fetch on lead day change
  useEffect(() => {
    loadForecastGrid(leadDay);
  }, [leadDay, loadForecastGrid]);

  // Trigger explanation update on station or lead day change
  useEffect(() => {
    if (selectedGridId) {
      loadExplanation(selectedGridId, leadDay);
    }
  }, [selectedGridId, leadDay, loadExplanation]);

  const handleStationSelect = (gridId: string) => {
    setSelectedGridId(gridId);
  };

  const handleLeadChange = (newLead: number) => {
    setLeadDay(newLead);
  };

  const handleRefresh = () => {
    loadForecastGrid(leadDay);
    fetchModelInfo().then((res) => setModelInfo(res.data));
    fetchHealth().then((res) => setTelemetry(res.data));
    fetchLeadTimeProfile().then((res) => setProfile(res.data));
    if (selectedGridId) {
      loadExplanation(selectedGridId, leadDay);
    }
  };

  const handleCustomAnalysis = (customFeatures: Record<string, number>) => {
    if (selectedGridId) {
      loadExplanation(selectedGridId, leadDay, customFeatures);
    }
  };

  return (
    <div className="min-h-screen bg-[#090d16] text-slate-100 flex flex-col font-mono text-xs">
      {/* Top Telemetry Header */}
      <header className="border-b border-slate-800 bg-[#0b101e]/90 backdrop-blur-md px-5 py-3 sticky top-0 z-30">
        <div className="max-w-[1700px] mx-auto flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-4">
            <Link
              href="/"
              className="flex items-center gap-1.5 text-slate-400 hover:text-slate-100 transition-colors p-1 rounded hover:bg-slate-800"
              title="Return to System Overview"
            >
              <ArrowLeft className="w-4 h-4" />
              <span className="hidden sm:inline">Overview</span>
            </Link>

            <div className="flex items-center gap-2 font-bold tracking-wider text-slate-100 text-sm">
              <span className="w-2.5 h-2.5 rounded-sm bg-sky-500 shadow-[0_0_8px_rgba(56,189,248,0.8)]" />
              <span>VayuDRISHTI</span>
              <span className="text-[10px] text-sky-400 font-normal px-2 py-0.5 rounded border border-sky-800 bg-sky-950/40">
                OPERATIONAL DIAGNOSTIC SUITE
              </span>
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-4 text-slate-300">
            <div className="flex items-center gap-2">
              <span className="text-slate-500">TELEMETRY:</span>
              <span
                className={`flex items-center gap-1 ${
                  gridSource === "live" ? "text-emerald-400" : "text-amber-400"
                }`}
              >
                <span
                  className={`w-2 h-2 rounded-full animate-pulse ${
                    gridSource === "live" ? "bg-emerald-400" : "bg-amber-400"
                  }`}
                />
                {telemetry?.status || "OPERATIONAL"}
              </span>
            </div>

            <div className="hidden md:flex items-center gap-2">
              <span className="text-slate-500">NWP CORE:</span>
              <span className="text-slate-200">
                {gridData?.model_version || "NCMRWF-Irrespective Diagnostic v3.0"}
              </span>
            </div>

            <div className="hidden lg:flex items-center gap-2 text-slate-400">
              <Activity className="w-3.5 h-3.5" />
              <span>{utcTimestamp}</span>
            </div>

            <button
              type="button"
              onClick={handleRefresh}
              className="p-1.5 rounded border border-slate-700 bg-slate-800 hover:bg-slate-700 text-slate-200 transition-colors flex items-center gap-1.5"
              title="Refresh Telemetry Matrix"
            >
              <RefreshCw
                className={`w-3.5 h-3.5 ${
                  isLoadingGrid || isLoadingExplain ? "animate-spin" : ""
                }`}
              />
              <span className="hidden sm:inline">Sync</span>
            </button>
          </div>
        </div>
      </header>

      {/* Main Workspace Body */}
      <main className="flex-1 max-w-[1700px] w-full mx-auto p-4 lg:p-6 space-y-4">
        {/* Offline / degraded banner */}
        {gridSource === "offline-fallback" && (
          <div className="rounded-lg border border-amber-500/50 bg-amber-950/30 px-4 py-2.5 font-mono text-[11px] text-amber-200 flex flex-wrap items-center gap-2">
            <span className="font-bold">BACKEND OFFLINE —</span>
            <span>
              showing a deterministic synthetic baseline, not live model output
              {gridError ? ` (${gridError})` : ""}. Start the API with{" "}
              <code className="text-amber-100">uvicorn app.main:app --port 8000</code>{" "}
              from the backend directory.
            </span>
          </div>
        )}

        {/* Model provenance + held-out skill */}
        <ModelProvenanceBadge
          modelInfo={modelInfo}
          dataSource={gridSource}
          error={gridError}
        />

        {/* Top Control Bar: Lead Slider & Domain Metrics */}
        <div className="grid grid-cols-1 xl:grid-cols-12 gap-4 items-stretch">
          <div className="xl:col-span-5 flex flex-col justify-center">
            <TimeLeadSlider
              currentLead={leadDay}
              onChange={handleLeadChange}
              isLoading={isLoadingGrid}
            />
          </div>
          <div className="xl:col-span-7 flex flex-col justify-center">
            <MetricsPanel
              telemetry={gridData?.domain_telemetry}
              totalStations={gridData?.grid_cells.length || 20}
            />
          </div>
        </div>

        {/* Core Interactive Layout: Geospatial Map Overlay & XAI Inspector */}
        <div className="grid grid-cols-1 xl:grid-cols-12 gap-4 items-start">
          {/* Geospatial Map Area */}
          <div className="xl:col-span-7 space-y-3">
            <MapContainer
              cells={gridData?.grid_cells || []}
              selectedGridId={selectedGridId}
              onSelectStation={handleStationSelect}
              leadDay={leadDay}
              dataSource={gridSource}
            />

            {/* Error-prone areas for the active lead day */}
            <ErrorProneAreasPanel
              areas={gridData?.error_prone_areas || []}
              leadDay={leadDay}
              selectedGridId={selectedGridId}
              totalCells={gridData?.grid_cells.length || 0}
              onSelect={handleStationSelect}
            />

            {/* Sub-map quick station selection pills */}
            <div className="p-3 rounded-lg border border-slate-800 bg-[#0c1220] flex flex-wrap items-center gap-2">
              <span className="text-[10px] text-slate-500 font-semibold mr-1">
                QUICK SECTOR JUMP:
              </span>
              {(gridData?.grid_cells || []).slice(0, 10).map((cell) => {
                const isSelected = cell.grid_id === selectedGridId;
                return (
                  <button
                    key={cell.grid_id}
                    type="button"
                    onClick={() => handleStationSelect(cell.grid_id)}
                    className={`px-2 py-1 rounded text-[10px] transition-colors border ${
                      isSelected
                        ? "bg-sky-500/20 border-sky-400 text-sky-200 font-bold"
                        : "bg-slate-900 border-slate-800 text-slate-400 hover:text-slate-200"
                    }`}
                  >
                    {cell.name.split(" ")[0]} ({cell.grid_id})
                  </button>
                );
              })}
            </div>
          </div>

          {/* XAI Explanation & Inspector Panel */}
          <div className="xl:col-span-5 space-y-3">
            <XAIExplanationCard
              data={explainData}
              isLoading={isLoadingExplain}
              dataSource={gridSource}
              onRunCustomAnalysis={handleCustomAnalysis}
            />
          </div>
        </div>

        {/* Lead-time confidence profile across the full Day 1-10 horizon */}
        <LeadTimeProfilePanel
          profile={profile}
          isLoading={isLoadingProfile}
          activeLeadDay={leadDay}
          onSelectLeadDay={handleLeadChange}
        />
      </main>

      {/* Persistent Technical Status Footer */}
      <footer className="border-t border-slate-800 bg-[#070b14] px-5 py-2.5 text-[11px] text-slate-500 flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <span
            className={`flex items-center gap-1.5 ${
              gridSource === "live" ? "text-emerald-400" : "text-amber-400"
            }`}
          >
            <span
              className={`w-1.5 h-1.5 rounded-full ${
                gridSource === "live" ? "bg-emerald-400" : "bg-amber-400"
              }`}
            />
            {gridSource === "live" ? "MODEL_ONLINE" : "MODEL_OFFLINE"}
          </span>
          <span>•</span>
          <span>LAT: 8.00°N TO 37.00°N | LON: 68.00°E TO 97.00°E</span>
        </div>
        <div className="flex items-center gap-4 text-slate-400">
          <span>ACTIVE STATION: {selectedGridId}</span>
          <span>•</span>
          <span>OUTLOOK: DAY {leadDay} (+{leadDay * 24}h)</span>
        </div>
      </footer>
    </div>
  );
}
