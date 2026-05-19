"use client";

import React, { useMemo } from "react";
import { ArrowRight, Gauge, Radio, ShieldOff, Target } from "lucide-react";

export type PrescriptionPayload = {
  driver_id: string;
  timestamp: string;
  optimality: {
    cognitive_efficiency: number;
    performance_lost_s: number;
    weighted_distance: number;
    centroid: Record<string, number>;
    deltas: Record<string, number>;
    contributions: Record<string, number>;
    sample_count: number;
    persona_seed: string;
  };
  primary: {
    code: string;
    label: string;
    surface: string;
    summary: string;
    score: number;
    triggers: string[];
    blocked_by: string[];
    projected_twin: Record<string, number>;
    projected_efficiency: number;
  };
  alternatives: Array<{
    code: string;
    label: string;
    surface: string;
    summary: string;
    score: number;
    triggers: string[];
    blocked_by: string[];
    projected_twin: Record<string, number>;
    projected_efficiency: number;
  }>;
  rationale: string;
  forecast_used: boolean;
  granite?: {
    text: string;
    source: string;
    model: string;
  };
};

type Props = {
  prescription: PrescriptionPayload | null;
  driverId: string | null;
};

const SURFACE_ICONS: Record<string, React.ReactNode> = {
  radio: <Radio size={12} className="text-cyan-300" />,
  strategy: <Target size={12} className="text-emerald-300" />,
  none: <Gauge size={12} className="text-gray-400" />,
};

function efficiencyTone(value: number): string {
  if (value >= 75) return "text-emerald-300";
  if (value >= 50) return "text-amber-300";
  return "text-red-300";
}

function efficiencyBar(value: number): string {
  if (value >= 75) return "bg-emerald-500";
  if (value >= 50) return "bg-amber-400";
  return "bg-red-500";
}

export function PrescriptionPanel({ prescription, driverId }: Props) {
  const biggestDeltaField = useMemo(() => {
    if (!prescription) return null;
    const entries = Object.entries(prescription.optimality.contributions ?? {});
    if (entries.length === 0) return null;
    return entries.sort((a, b) => b[1] - a[1])[0];
  }, [prescription]);

  if (!prescription || !driverId) {
    return (
      <div className="bg-neuropit-dark border border-gray-800 rounded p-5">
        <h2 className="text-[11px] tracking-[0.3em] uppercase text-gray-400 mb-3 flex items-center gap-2">
          <Target size={14} className="text-emerald-300" />
          Prescriptive engine
        </h2>
        <div className="text-xs text-gray-600 border-l-2 border-gray-700 pl-3 py-2">
          Awaiting first prescription event for the selected driver.
        </div>
      </div>
    );
  }

  const eff = prescription.optimality.cognitive_efficiency;
  const lost = prescription.optimality.performance_lost_s;

  return (
    <div className="bg-neuropit-dark border border-gray-800 rounded p-5">
      <div className="flex justify-between items-start mb-3">
        <h2 className="text-[11px] tracking-[0.3em] uppercase text-gray-400 flex items-center gap-2">
          <Target size={14} className="text-emerald-300" />
          Prescriptive engine
        </h2>
        <span className="text-[9px] tracking-[0.3em] uppercase text-gray-500">
          {prescription.forecast_used ? "forecast aware" : "no forecast"}
        </span>
      </div>

      <div className="grid grid-cols-2 gap-3 mb-4">
        <div className="border border-gray-800 rounded px-3 py-2">
          <div className="text-[9px] tracking-[0.3em] uppercase text-gray-500 mb-1">
            Cognitive efficiency
          </div>
          <div className={`text-2xl font-black tracking-tight ${efficiencyTone(eff)}`}>
            {eff.toFixed(0)}
            <span className="text-[10px] text-gray-600 ml-1">/ 100</span>
          </div>
          <div className="mt-2 h-1.5 bg-gray-800 rounded overflow-hidden">
            <div
              className={`h-full ${efficiencyBar(eff)}`}
              style={{ width: `${Math.min(100, Math.max(0, eff))}%` }}
            />
          </div>
        </div>
        <div className="border border-gray-800 rounded px-3 py-2">
          <div className="text-[9px] tracking-[0.3em] uppercase text-gray-500 mb-1">
            On the table this lap
          </div>
          <div className="text-2xl font-black tracking-tight text-orange-300">
            {lost >= 0.005 ? `+${lost.toFixed(2)}s` : "0.00s"}
          </div>
          <div className="text-[10px] text-gray-600 mt-2">
            envelope samples seen: {prescription.optimality.sample_count}
          </div>
        </div>
      </div>

      <div className="border border-emerald-700/40 bg-emerald-900/10 rounded px-3 py-3 mb-3">
        <div className="flex justify-between items-center">
          <div className="text-[9px] tracking-[0.3em] uppercase text-emerald-300">
            Prescribed action
          </div>
          <div className="flex items-center gap-1 text-[10px] text-gray-400">
            {SURFACE_ICONS[prescription.primary.surface] ?? null}
            <span className="uppercase tracking-[0.3em]">
              {prescription.primary.surface}
            </span>
          </div>
        </div>
        <div className="text-lg font-bold text-emerald-200 mt-1">
          {prescription.primary.label}
        </div>
        <div className="text-xs text-gray-300 mt-1 leading-relaxed">
          {prescription.primary.summary}
        </div>
        {prescription.primary.triggers.length > 0 && (
          <div className="flex flex-wrap gap-1 mt-2">
            {prescription.primary.triggers.map((t) => (
              <span
                key={t}
                className="text-[9px] tracking-[0.2em] uppercase border border-emerald-700/40 bg-emerald-900/20 text-emerald-200 px-1.5 py-0.5 rounded"
              >
                {t.replace(/_/g, " ")}
              </span>
            ))}
          </div>
        )}
        <div className="flex items-center gap-2 mt-3 text-[10px] text-gray-400">
          <span className="tracking-[0.2em] uppercase text-gray-500">
            projected efficiency if executed
          </span>
          <ArrowRight size={11} />
          <span className={`font-bold ${efficiencyTone(prescription.primary.projected_efficiency)}`}>
            {prescription.primary.projected_efficiency.toFixed(0)}/100
          </span>
        </div>
      </div>

      <div className="mb-3">
        <div className="text-[9px] tracking-[0.3em] uppercase text-gray-500 mb-1">
          Rationale
        </div>
        <p className="text-xs text-gray-200 leading-relaxed border-l-2 border-emerald-700/40 pl-3 py-1">
          {prescription.rationale}
        </p>
        {prescription.granite?.text && (
          <p className="text-[11px] text-gray-300 leading-relaxed border-l-2 border-blue-500 pl-3 py-1 mt-2">
            <span className="text-[9px] uppercase tracking-[0.3em] text-blue-400 mr-1">
              via {prescription.granite.source}
            </span>
            {prescription.granite.text}
          </p>
        )}
      </div>

      {biggestDeltaField && (
        <div className="mb-3">
          <div className="text-[9px] tracking-[0.3em] uppercase text-gray-500 mb-1">
            Biggest envelope drift
          </div>
          <div className="text-xs text-gray-200">
            <span className="text-gray-500 uppercase tracking-[0.2em] mr-2">
              {biggestDeltaField[0].replace(/_score$/, "").replace(/_/g, " ")}
            </span>
            <span className="text-amber-200 font-bold">
              {(biggestDeltaField[1] * 100).toFixed(0)}% of total
            </span>
          </div>
        </div>
      )}

      {prescription.alternatives.length > 0 && (
        <div>
          <div className="text-[9px] tracking-[0.3em] uppercase text-gray-500 mb-2">
            Ranked alternatives
          </div>
          <div className="space-y-1">
            {prescription.alternatives.map((alt) => (
              <div
                key={alt.code}
                className={`flex justify-between items-center text-[11px] border rounded px-2 py-1 ${
                  alt.blocked_by.length > 0
                    ? "border-red-700/40 bg-red-900/10 text-gray-500"
                    : "border-gray-800 text-gray-300"
                }`}
              >
                <span className="flex items-center gap-2">
                  {SURFACE_ICONS[alt.surface] ?? null}
                  {alt.label}
                  {alt.blocked_by.length > 0 && (
                    <ShieldOff size={11} className="text-red-400" />
                  )}
                </span>
                <span className="text-gray-500 text-[10px]">
                  score {alt.score.toFixed(1)} · eff {alt.projected_efficiency.toFixed(0)}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
