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
  size = 144,
  stroke = 6,
  inverted = false,
}: MetricRingProps) {
  const clamped = Math.max(0, Math.min(max, value));
  const ratio = clamped / max;

  // Pad the viewBox so the round-cap stroke never clips at the edges
  // when the ring is full. Without this the top of a 100% reading
  // looks flat and the panel reads as a square.
  const pad = stroke;
  const radius = (size - stroke) / 2;
  const circumference = 2 * Math.PI * radius;
  const dashOffset = circumference * (1 - ratio);
  const center = size / 2;
  const viewBox = `${-pad} ${-pad} ${size + pad * 2} ${size + pad * 2}`;

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
    <div
      className="relative flex flex-col items-center justify-center"
      style={{ width: size + pad * 2, height: size + pad * 2 }}
    >
      <svg
        width={size + pad * 2}
        height={size + pad * 2}
        viewBox={viewBox}
        className="-rotate-90 overflow-visible"
      >
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
          transition={{ duration: 0.8, type: "spring", bounce: 0.15 }}
          className={ringColor}
        />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center pointer-events-none">
        <motion.div
          key={clamped}
          initial={{ opacity: 0.6 }}
          animate={{ opacity: 1 }}
          className={`text-3xl font-mono font-semibold tabular-nums tracking-tight ${numberColor}`}
        >
          {clamped.toFixed(1)}
        </motion.div>
        <div className="text-[10px] tracking-[0.25em] uppercase text-gray-400 mt-1">
          {label}
        </div>
        <div className="text-[9px] tracking-[0.25em] uppercase text-gray-600 mt-0.5">
          / {max}
        </div>
      </div>
    </div>
  );
}
