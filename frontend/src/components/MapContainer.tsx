"use client";

import React, { useEffect, useRef, useState } from "react";
import type { Map as LeafletMap, LayerGroup } from "leaflet";
import { GridCellSummary } from "@/types";

type MapLayer = "BUST_RISK" | "CONFIDENCE" | "EXPECTED_ERROR";

interface MapContainerProps {
  cells: GridCellSummary[];
  selectedGridId: string | null;
  onSelectStation: (gridId: string) => void;
  leadDay: number;
  dataSource?: "live" | "offline-fallback";
}

const LAYER_COPY: Record<MapLayer, { label: string; legend: string }> = {
  BUST_RISK: {
    label: "BUST RISK",
    legend: "P(error > 25 mm) — red = likely bust",
  },
  CONFIDENCE: {
    label: "CONFIDENCE",
    legend: "1 − P(bust) — green = trustworthy",
  },
  EXPECTED_ERROR: {
    label: "EXPECTED ERROR",
    legend: "expected |error| in mm",
  },
};

/** Maps a 0..1 value to a red → amber → green ramp. */
function ramp(t: number): string {
  const clamped = Math.max(0, Math.min(1, t));
  if (clamped < 0.5) {
    const k = clamped / 0.5;
    return `rgb(${Math.round(239 - 44 * k)}, ${Math.round(68 + 107 * k)}, ${Math.round(68 - 28 * k)})`;
  }
  const k = (clamped - 0.5) / 0.5;
  return `rgb(${Math.round(195 - 179 * k)}, ${Math.round(175 - 143 * k)}, ${Math.round(40 + 137 * k)})`;
}

function layerValue(cell: GridCellSummary, layer: MapLayer): number {
  if (layer === "CONFIDENCE") return cell.confidence_percentage / 100;
  if (layer === "EXPECTED_ERROR")
    return Math.min(
      1,
      cell.expected_model_deviation.precipitation_mm / 60
    );
  return cell.bust_probability;
}

function layerColor(cell: GridCellSummary, layer: MapLayer): string {
  if (layer === "CONFIDENCE") {
    // Inverted: high confidence should read as green.
    return ramp(1 - cell.confidence_percentage / 100);
  }
  return ramp(layerValue(cell, layer));
}

function rampGradient(): string {
  const stops = Array.from({ length: 11 }, (_, i) => `${ramp(i / 10)} ${i * 10}%`);
  return `linear-gradient(90deg, ${stops.join(", ")})`;
}

export default function MapContainer({
  cells,
  selectedGridId,
  onSelectStation,
  leadDay,
  dataSource = "live",
}: MapContainerProps) {
  const [layer, setLayer] = useState<MapLayer>("BUST_RISK");
  const mapRef = useRef<HTMLDivElement>(null);
  const leafletMapInstance = useRef<LeafletMap | null>(null);
  const markersLayerRef = useRef<LayerGroup | null>(null);

  useEffect(() => {
    let isMounted = true;

    // Dynamically load leaflet on client-side
    import("leaflet").then((L) => {
      if (!isMounted || !mapRef.current) return;

      if (!leafletMapInstance.current) {
        // Initialize Map centered over Indian subcontinent
        const map = L.map(mapRef.current, {
          center: [22.0, 79.5],
          zoom: 5,
          minZoom: 4,
          maxZoom: 10,
          zoomControl: false,
          attributionControl: false,
        });

        // Add Dark CartoDB basemap tiles
        L.tileLayer(
          "https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png",
          {
            maxZoom: 19,
            subdomains: "abcd",
          }
        ).addTo(map);

        // Add custom zoom control
        L.control.zoom({ position: "topright" }).addTo(map);

        leafletMapInstance.current = map;
        markersLayerRef.current = L.layerGroup().addTo(map);
      }

      // Clear previous markers
      if (markersLayerRef.current) {
        markersLayerRef.current.clearLayers();
      }

      // Render station markers
      cells.forEach((cell) => {
        const isSelected = cell.grid_id === selectedGridId;
        const color = layerColor(cell, layer);

        const radius = isSelected ? 12 : 8;

        // Custom SVG circle marker
        const circle = L.circleMarker([cell.lat, cell.lon], {
          radius: radius,
          fillColor: color,
          color: isSelected ? "#38bdf8" : "#ffffff",
          weight: isSelected ? 3 : 1.5,
          opacity: 0.9,
          fillOpacity: 0.85,
        });

        // Tooltip / Popup content
        const popupContent = `
          <div style="font-family: monospace; font-size: 11px; padding: 2px;">
            <div style="font-weight: bold; color: ${color}; margin-bottom: 2px;">
              ${cell.grid_id} — ${cell.name}
            </div>
            <div style="color: #94a3b8; margin-bottom: 4px;">${cell.subdivision}</div>
            <div style="display: flex; justify-content: space-between; margin-bottom: 2px;">
              <span>Bust Risk:</span>
              <strong style="color: ${color};">${cell.bust_probability.toFixed(3)}</strong>
            </div>
            <div style="display: flex; justify-content: space-between; margin-bottom: 2px;">
              <span>Confidence:</span>
              <strong>${cell.confidence_percentage.toFixed(1)}%</strong>
            </div>
            <div style="display: flex; justify-content: space-between; margin-bottom: 2px;">
              <span>Flag:</span>
              <strong>${cell.reliability_flag}</strong>
            </div>
            <div style="display: flex; justify-content: space-between; margin-bottom: 2px;">
              <span>Archive bust rate:</span>
              <span>${cell.historical_error_context.hist_bust_frequency_pct.toFixed(1)}%</span>
            </div>
            <div style="display: flex; justify-content: space-between;">
              <span>Expected precip error:</span>
              <span>±${cell.expected_model_deviation.precipitation_mm} mm</span>
            </div>
          </div>
        `;

        circle.bindPopup(popupContent, {
          closeButton: false,
          className: "custom-telemetry-popup",
        });

        circle.on("click", () => {
          onSelectStation(cell.grid_id);
        });

        if (markersLayerRef.current) {
          circle.addTo(markersLayerRef.current);
        }
      });
    });

    return () => {
      isMounted = false;
    };
  }, [cells, selectedGridId, onSelectStation, layer]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (leafletMapInstance.current) {
        leafletMapInstance.current.remove();
        leafletMapInstance.current = null;
      }
    };
  }, []);

  return (
    <div className="relative w-full h-[520px] lg:h-[620px] rounded-lg border border-slate-800 overflow-hidden bg-[#070b14] shadow-xl">
      {/* Map Container Element */}
      <div ref={mapRef} className="w-full h-full z-0" />

      {/* Top Map HUD Overlay */}
      <div className="absolute top-3 left-3 z-10 font-mono text-[11px] bg-[#0c1220]/90 backdrop-blur-md border border-slate-800 p-2.5 rounded shadow-lg space-y-1">
        <div className="flex items-center gap-2 text-slate-300 font-semibold">
          <span className="w-2 h-2 rounded-full bg-sky-400 animate-pulse" />
          <span>INDIAN CONTINENTAL RADAR TELEMETRY</span>
        </div>
        <div className="text-[10px] text-slate-400">
          SPATIAL DOMAIN: 8.0°N–37.0°N | 68.0°E–97.0°E
        </div>
        <div className="text-[10px] text-sky-400">
          LEAD EVALUATION: DAY {leadDay} (+{leadDay * 24}h FORECAST HORIZON)
        </div>
        {dataSource === "offline-fallback" && (
          <div className="text-[10px] text-amber-400 font-bold">
            OFFLINE SYNTHETIC BASELINE — NOT MODEL OUTPUT
          </div>
        )}
      </div>

      {/* Map layer switch */}
      <div className="absolute top-3 right-12 z-10 font-mono text-[10px] bg-[#0c1220]/95 backdrop-blur-md border border-slate-800 p-1.5 rounded shadow-lg">
        <div className="text-[9px] text-slate-500 px-1 pb-1">MAP LAYER</div>
        <div className="flex flex-col gap-1">
          {(Object.keys(LAYER_COPY) as MapLayer[]).map((key) => (
            <button
              key={key}
              type="button"
              onClick={() => setLayer(key)}
              className={`px-2 py-0.5 rounded text-left transition-colors ${
                layer === key
                  ? "bg-sky-500/25 border border-sky-500/50 text-sky-200 font-bold"
                  : "border border-transparent text-slate-400 hover:text-slate-200"
              }`}
            >
              {LAYER_COPY[key].label}
            </button>
          ))}
        </div>
      </div>

      {/* Bottom Map Legend */}
      <div className="absolute bottom-3 left-3 z-10 font-mono text-[10px] bg-[#0c1220]/95 backdrop-blur-md border border-slate-800 p-2.5 rounded shadow-lg space-y-1.5">
        <div className="text-slate-400 font-semibold">
          {LAYER_COPY[layer].legend}
        </div>
        <div className="h-2 w-48 rounded-full" style={{ background: rampGradient() }} />
        <div className="flex justify-between w-48 text-[9px] text-slate-500">
          <span>low</span>
          <span>mid</span>
          <span>high</span>
        </div>
        <div className="flex flex-wrap items-center gap-3 pt-1 border-t border-slate-800">
          <div className="flex items-center gap-1.5">
            <span className="w-2.5 h-2.5 rounded-full bg-rose-500" />
            <span className="text-slate-300">High Bust (&ge;0.65)</span>
          </div>
          <div className="flex items-center gap-1.5">
            <span className="w-2.5 h-2.5 rounded-full bg-amber-500" />
            <span className="text-slate-300">Elevated (0.35–0.65)</span>
          </div>
          <div className="flex items-center gap-1.5">
            <span className="w-2.5 h-2.5 rounded-full bg-emerald-500" />
            <span className="text-slate-300">Nominal (&lt;0.35)</span>
          </div>
        </div>
      </div>

      {/* Selection indicator pill */}
      {selectedGridId && (
        <div className="absolute top-3 right-12 z-10 font-mono text-[11px] bg-sky-950/80 border border-sky-600/50 text-sky-300 px-3 py-1.5 rounded shadow-lg">
          ACTIVE CELL: {selectedGridId}
        </div>
      )}
    </div>
  );
}
