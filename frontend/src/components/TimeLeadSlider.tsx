"use client";

import React from "react";
import { Calendar, ChevronLeft, ChevronRight, Clock } from "lucide-react";

interface TimeLeadSliderProps {
  currentLead: number;
  onChange: (lead: number) => void;
  isLoading?: boolean;
}

export default function TimeLeadSlider({
  currentLead,
  onChange,
  isLoading = false,
}: TimeLeadSliderProps) {
  const leadHours = currentLead * 24;

  const handleStep = (step: number) => {
    const nextVal = Math.max(1, Math.min(10, currentLead + step));
    onChange(nextVal);
  };

  return (
    <div className="rounded-lg border border-slate-800 bg-[#0c1220] p-4 text-xs font-mono text-slate-300 shadow-md">
      <div className="flex flex-wrap items-center justify-between gap-3 mb-3">
        <div className="flex items-center gap-2">
          <Calendar className="w-4 h-4 text-sky-400" />
          <span className="font-semibold text-slate-100 text-sm tracking-wide">
            FORECAST LEAD HORIZON
          </span>
          <span className="px-2 py-0.5 rounded text-[11px] bg-slate-800 border border-slate-700 text-sky-300">
            DAY {currentLead} / T+{leadHours}h OUTLOOK
          </span>
        </div>

        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => handleStep(-1)}
            disabled={currentLead <= 1 || isLoading}
            className="p-1.5 rounded border border-slate-700 bg-slate-800 hover:bg-slate-700 disabled:opacity-30 disabled:cursor-not-allowed text-slate-200 transition-colors"
            title="Step back 24 hours"
          >
            <ChevronLeft className="w-3.5 h-3.5" />
          </button>

          <span className="text-slate-400 font-medium px-1">
            {leadHours} Hours
          </span>

          <button
            type="button"
            onClick={() => handleStep(1)}
            disabled={currentLead >= 10 || isLoading}
            className="p-1.5 rounded border border-slate-700 bg-slate-800 hover:bg-slate-700 disabled:opacity-30 disabled:cursor-not-allowed text-slate-200 transition-colors"
            title="Advance 24 hours"
          >
            <ChevronRight className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>

      {/* Slider Control */}
      <div className="relative py-2">
        <input
          type="range"
          min="1"
          max="10"
          step="1"
          value={currentLead}
          onChange={(e) => onChange(parseInt(e.target.value, 10))}
          disabled={isLoading}
          aria-label="Forecast Lead Day"
          className="w-full h-2 bg-slate-800 rounded-lg appearance-none cursor-pointer accent-sky-500 focus:outline-none disabled:opacity-50"
        />

        {/* 10-Day Step Indicators */}
        <div className="flex justify-between items-center text-[10px] text-slate-500 mt-2 px-1">
          {Array.from({ length: 10 }, (_, i) => i + 1).map((day) => {
            const isSelected = day === currentLead;
            return (
              <button
                key={day}
                type="button"
                onClick={() => onChange(day)}
                className={`flex flex-col items-center gap-0.5 transition-colors ${
                  isSelected
                    ? "text-sky-400 font-bold"
                    : "text-slate-500 hover:text-slate-300"
                }`}
              >
                <span>D{day}</span>
                <span className="text-[9px] text-slate-600">+{day * 24}h</span>
              </button>
            );
          })}
        </div>
      </div>

      {/* Lead horizon uncertainty disclaimer */}
      <div className="mt-2 pt-2 border-t border-slate-800/80 flex items-center justify-between text-[11px] text-slate-400">
        <div className="flex items-center gap-1.5">
          <Clock className="w-3 h-3 text-slate-500" />
          <span>Nonlinear dynamical chaos error bounds grow by ~14% per 24h lead.</span>
        </div>
        {isLoading && (
          <span className="text-sky-400 animate-pulse">Computing diagnostic tensors...</span>
        )}
      </div>
    </div>
  );
}
