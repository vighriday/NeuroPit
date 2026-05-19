"use client";

import React from "react";

const PERSONA_COLORS: Record<string, string> = {
  Panic: "bg-red-600",
  Aggressive: "bg-orange-500",
  Fatigue: "bg-purple-500",
  Defensive: "bg-amber-400",
  "Flow State": "bg-emerald-400",
  Recovery: "bg-blue-500",
};

export type PersonaTick = {
  timestamp: string;
  persona: string;
};

type Props = {
  ticks: PersonaTick[];
};

export function PersonaTimeline({ ticks }: Props) {
  if (ticks.length === 0) {
    return (
      <div className="text-xs text-gray-600 tracking-[0.25em] uppercase">
        Awaiting persona stream
      </div>
    );
  }

  return (
    <div>
      <div className="flex h-3 rounded-sm overflow-hidden border border-gray-800">
        {ticks.map((tick, idx) => (
          <div
            key={`${tick.timestamp}-${idx}`}
            className={`flex-1 ${PERSONA_COLORS[tick.persona] ?? "bg-gray-700"}`}
            title={`${tick.persona} @ ${tick.timestamp.slice(11, 19)}`}
          />
        ))}
      </div>
      <div className="mt-2 flex justify-between text-[10px] tracking-[0.25em] uppercase text-gray-600">
        {Object.keys(PERSONA_COLORS).map((label) => (
          <span key={label} className="flex items-center gap-1">
            <span className={`w-2 h-2 rounded-sm ${PERSONA_COLORS[label]}`} /> {label}
          </span>
        ))}
      </div>
    </div>
  );
}
