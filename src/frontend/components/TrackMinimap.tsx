"use client";

import React, { useMemo } from "react";

export type TrackPoint = {
  x: number;
  y: number;
  stress: number;
};

type Props = {
  points: TrackPoint[];
  size?: number;
};

export function TrackMinimap({ points, size = 220 }: Props) {
  const projected = useMemo(() => {
    if (points.length < 2) return [];
    const xs = points.map((p) => p.x);
    const ys = points.map((p) => p.y);
    const minX = Math.min(...xs);
    const maxX = Math.max(...xs);
    const minY = Math.min(...ys);
    const maxY = Math.max(...ys);
    const rangeX = maxX - minX || 1;
    const rangeY = maxY - minY || 1;
    const padding = 14;
    const usable = size - padding * 2;
    return points.map((p) => ({
      x: padding + ((p.x - minX) / rangeX) * usable,
      y: padding + ((p.y - minY) / rangeY) * usable,
      stress: p.stress,
    }));
  }, [points, size]);

  if (projected.length < 2) {
    return (
      <div
        className="flex items-center justify-center border border-gray-800 rounded text-xs text-gray-600 tracking-[0.25em] uppercase"
        style={{ width: size, height: size }}
      >
        Awaiting positional stream
      </div>
    );
  }

  return (
    <svg width={size} height={size} className="border border-gray-800 rounded bg-black/40">
      <polyline
        points={projected.map((p) => `${p.x},${p.y}`).join(" ")}
        fill="none"
        stroke="#1f2937"
        strokeWidth={2}
      />
      {projected.map((p, idx) => {
        const intensity = Math.min(1, p.stress / 100);
        const fill =
          p.stress > 75
            ? `rgba(239, 68, 68, ${0.45 + intensity * 0.4})`
            : p.stress > 50
            ? `rgba(245, 158, 11, ${0.4 + intensity * 0.4})`
            : `rgba(16, 185, 129, ${0.35 + intensity * 0.4})`;
        return <circle key={idx} cx={p.x} cy={p.y} r={1.6} fill={fill} />;
      })}
      <circle
        cx={projected[projected.length - 1].x}
        cy={projected[projected.length - 1].y}
        r={4.5}
        fill="#ef4444"
        className="animate-pulse"
      />
    </svg>
  );
}
