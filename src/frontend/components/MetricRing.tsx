"use client";

import React from "react";

type MetricRingProps = {
  label: string;
  value: number;
  max?: number;
  accent: string;
  size?: number;
  stroke?: number;
  inverted?: boolean;
};

export function MetricRing({
  label,
  value,
  max = 100,
  accent,
  size = 140,
  stroke = 10,
  inverted = false,
}: MetricRingProps) {
  const clamped = Math.max(0, Math.min(max, value));
  const ratio = clamped / max;
  const radius = (size - stroke) / 2;
  const circumference = 2 * Math.PI * radius;
  const dashOffset = circumference * (1 - ratio);
  const center = size / 2;

  const dangerous = inverted ? clamped < 40 : clamped > 70;
  const cautious = inverted ? clamped < 60 : clamped > 50;

  const ringColor = dangerous
    ? "stroke-red-500"
    : cautious
    ? "stroke-amber-400"
    : "stroke-emerald-400";

  return (
    <div className="flex flex-col items-center justify-center">
      <svg width={size} height={size} className="-rotate-90">
        <circle
          cx={center}
          cy={center}
          r={radius}
          fill="none"
          strokeWidth={stroke}
          className="stroke-gray-800"
        />
        <circle
          cx={center}
          cy={center}
          r={radius}
          fill="none"
          strokeWidth={stroke}
          strokeLinecap="round"
          strokeDasharray={circumference}
          strokeDashoffset={dashOffset}
          className={`${ringColor} transition-all duration-300`}
        />
      </svg>
      <div className="-mt-[88px] flex flex-col items-center pointer-events-none">
        <div className={`text-4xl font-black tracking-tighter ${accent}`}>
          {clamped.toFixed(1)}
        </div>
        <div className="text-[10px] tracking-[0.25em] uppercase text-gray-500">{label}</div>
      </div>
      <div className="mt-12 text-[10px] tracking-[0.25em] uppercase text-gray-600">/ {max}</div>
    </div>
  );
}
