"use client";

import React from "react";
import { motion } from "framer-motion";

type MetricRingProps = {
  label: string;
  value: number;
  max?: number;
  size?: number;
  stroke?: number;
  inverted?: boolean;
  /**
   * Optional static text colour. When omitted (the recommended path)
   * the number colour follows the same traffic light bucket as the
   * ring stroke, so a healthy reading is never painted in danger red.
   */
  accent?: string;
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

  // Traffic light buckets. For inverted metrics (e.g. confidence, where
  // higher is better) we flip the thresholds. Border cases use <= so
  // a confidence reading sitting exactly on 40 trips the danger bucket
  // instead of falling into the moderate one.
  const dangerous = inverted ? clamped <= 40 : clamped >= 70;
  const cautious = inverted ? clamped <= 60 : clamped >= 50;

  const ringColor = dangerous
    ? "stroke-apex-red"
    : cautious
    ? "stroke-apex-amber"
    : "stroke-apex-cyan";

  const numberColor =
    accent ??
    (dangerous
      ? "text-apex-red"
      : cautious
      ? "text-apex-amber"
      : "text-apex-cyan");

  return (
    <div className="flex flex-col items-center justify-center relative">
      <svg width={size} height={size} className="-rotate-90">
        <circle
          cx={center}
          cy={center}
          r={radius}
          fill="none"
          strokeWidth={stroke}
          className="stroke-white/10"
        />
        <motion.circle
          cx={center}
          cy={center}
          r={radius}
          fill="none"
          strokeWidth={stroke}
          strokeLinecap="round"
          strokeDasharray={circumference}
          animate={{ strokeDashoffset: dashOffset }}
          transition={{ duration: 0.8, type: "spring", bounce: 0.2 }}
          className={`${ringColor}`}
          style={{ filter: "drop-shadow(0 0 6px currentColor)" }}
        />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center pointer-events-none pb-4">
        <motion.div
          key={clamped}
          initial={{ scale: 0.9, opacity: 0 }}
          animate={{ scale: 1, opacity: 1 }}
          className={`text-4xl font-mono font-bold tracking-tighter ${numberColor} drop-shadow-lg`}
        >
          {clamped.toFixed(1)}
        </motion.div>
        <div className="text-[10px] tracking-[0.25em] uppercase text-gray-400 mt-1">{label}</div>
      </div>
      <div className="absolute bottom-0 text-[10px] tracking-[0.25em] uppercase text-gray-600 mb-2">/ {max}</div>
    </div>
  );
}
