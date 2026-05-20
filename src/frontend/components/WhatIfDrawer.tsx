"use client";

import React, { useState } from "react";
import { History, Loader2, Play, Plus, RefreshCw, X } from "lucide-react";
import {
  Area,
  AreaChart,
  CartesianGrid,
  Line,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { postJSON } from "../lib/api";

type Mutation = {
  target: string;
  value: string;
};

type TrajectoryPoint = {
  timestamp: string;
  baseline: Record<string, number>;
  counterfactual: Record<string, number>;
  delta: Record<string, number>;
};

type WhatIfReplayResponse = {
  driver_id: string;
  window_seconds: number;
  mutations: Array<Record<string, unknown>>;
  baseline_count: number;
  trajectory: TrajectoryPoint[];
  summary: {
    baseline_avg: Record<string, number>;
    counterfactual_avg: Record<string, number>;
    delta_avg: Record<string, number>;
    biggest_delta_field: string | null;
    biggest_delta_value: number;
  };
  rationale: string;
};

type Props = {
  driverId: string | null;
};

const MUTATION_PRESETS: Array<{ label: string; target: string; value: string }> = [
  {
    label: "Calm driver (HR 110)",
    target: "inputs.biometrics.synthetic_hr",
    value: "110",
  },
  {
    label: "Higher HRV",
    target: "inputs.biometrics.synthetic_hrv",
    value: "70",
  },
  {
    label: "Calm steering inputs",
    target: "inputs.features.steering_instability",
    value: "1.0",
  },
  {
    label: "Confident throttle",
    target: "inputs.features.throttle_commitment",
    value: "0.95",
  },
  {
    label: "Reduce panic oscillation",
    target: "inputs.features.panic_oscillation",
    value: "1.0",
  },
];

function coerceValue(raw: string): unknown {
  const trimmed = raw.trim();
  if (trimmed === "") return "";
  const asNumber = Number(trimmed);
  if (!Number.isNaN(asNumber) && Number.isFinite(asNumber)) return asNumber;
  return trimmed;
}

export function WhatIfDrawer({ driverId }: Props) {
  const [open, setOpen] = useState(false);
  const [windowSeconds, setWindowSeconds] = useState(20);
  const [mutations, setMutations] = useState<Mutation[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [response, setResponse] = useState<WhatIfReplayResponse | null>(null);

  const addPreset = (preset: Mutation) => {
    if (mutations.some((m) => m.target === preset.target)) return;
    setMutations((prev) => [...prev, preset]);
  };

  const removeMutation = (target: string) => {
    setMutations((prev) => prev.filter((m) => m.target !== target));
  };

  const runReplay = async () => {
    if (!driverId) return;
    setLoading(true);
    setError(null);
    try {
      const body = {
        driver_id: driverId,
        window_seconds: windowSeconds,
        mutations: mutations.map((m) => ({ target: m.target, value: coerceValue(m.value) })),
      };
      const result = await postJSON<typeof body, WhatIfReplayResponse>(
        "/whatif/replay",
        body,
      );
      setResponse(result);
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err);
      setError(message);
      setResponse(null);
    } finally {
      setLoading(false);
    }
  };

  const chartData = response?.trajectory.map((point, idx) => ({
    idx,
    timestamp: point.timestamp.slice(11, 19),
    baseline_stress: point.baseline.stress_score,
    counterfactual_stress: point.counterfactual.stress_score,
    baseline_confidence: point.baseline.confidence_score,
    counterfactual_confidence: point.counterfactual.confidence_score,
  })) ?? [];

  return (
    <>
      <button
        type="button"
        onClick={() => setOpen(true)}
        disabled={!driverId}
        className="flex items-center gap-2 px-3 py-2 rounded border border-blue-700/40 bg-blue-900/20 text-blue-200 text-[11px] tracking-[0.3em] uppercase hover:bg-blue-900/40 disabled:opacity-40 disabled:cursor-not-allowed"
      >
        <History size={14} />
        What-If replay
      </button>

      {open && (
        <div className="fixed inset-0 z-50 bg-black/70 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-neuropit-dark border border-gray-800 rounded-lg max-w-4xl w-full max-h-[90vh] overflow-y-auto">
            <div className="flex justify-between items-center px-5 py-4 border-b border-gray-800 sticky top-0 bg-neuropit-dark z-10">
              <div>
                <h2 className="text-sm tracking-[0.3em] uppercase text-blue-300 flex items-center gap-2">
                  <History size={14} />
                  What-If replay
                </h2>
                <p className="text-[10px] text-gray-500 mt-1">
                  Audit-log driven. Mutates real recorded inputs and re-runs the cognitive
                  engine deterministically.
                </p>
              </div>
              <button
                type="button"
                onClick={() => setOpen(false)}
                className="text-gray-400 hover:text-gray-200"
                aria-label="Close"
              >
                <X size={18} />
              </button>
            </div>

            <div className="p-5 grid grid-cols-1 md:grid-cols-2 gap-5">
              <div>
                <div className="text-[10px] tracking-[0.3em] uppercase text-gray-500 mb-2">
                  Window
                </div>
                <div className="flex items-center gap-2 mb-4">
                  <input
                    type="number"
                    min={1}
                    max={600}
                    value={windowSeconds}
                    onChange={(e) => setWindowSeconds(Number(e.target.value) || 1)}
                    className="w-24 bg-black border border-gray-700 rounded px-2 py-1 text-sm text-gray-100"
                  />
                  <span className="text-[10px] tracking-[0.3em] uppercase text-gray-500">
                    seconds back
                  </span>
                </div>

                <div className="text-[10px] tracking-[0.3em] uppercase text-gray-500 mb-2">
                  Mutation presets
                </div>
                <div className="grid grid-cols-1 gap-1 mb-4">
                  {MUTATION_PRESETS.map((preset) => {
                    const added = mutations.some((m) => m.target === preset.target);
                    return (
                      <button
                        key={preset.target}
                        type="button"
                        onClick={() => addPreset(preset)}
                        className={`text-left text-[11px] px-2 py-1.5 border rounded flex items-center justify-between gap-2 ${
                          added
                            ? "border-emerald-700/40 bg-emerald-900/10 text-emerald-200"
                            : "border-gray-800 text-gray-300 hover:border-gray-600"
                        }`}
                      >
                        <span>{preset.label}</span>
                        <Plus size={12} className={added ? "text-emerald-300" : "text-gray-500"} />
                      </button>
                    );
                  })}
                </div>

                {mutations.length > 0 && (
                  <div className="mb-4">
                    <div className="text-[10px] tracking-[0.3em] uppercase text-gray-500 mb-2">
                      Active mutations
                    </div>
                    <div className="space-y-1">
                      {mutations.map((mut) => (
                        <div
                          key={mut.target}
                          className="flex items-center gap-2 border border-gray-800 rounded px-2 py-1.5 text-[11px]"
                        >
                          <span className="text-gray-400 flex-1 font-mono">{mut.target}</span>
                          <span className="text-gray-500">=</span>
                          <input
                            type="text"
                            value={mut.value}
                            onChange={(e) => {
                              const newValue = e.target.value;
                              setMutations((prev) =>
                                prev.map((m) =>
                                  m.target === mut.target ? { ...m, value: newValue } : m,
                                ),
                              );
                            }}
                            className="w-20 bg-black border border-gray-700 rounded px-1.5 py-0.5 text-gray-100"
                          />
                          <button
                            type="button"
                            onClick={() => removeMutation(mut.target)}
                            className="text-gray-500 hover:text-red-400"
                            aria-label="Remove mutation"
                          >
                            <X size={12} />
                          </button>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                <button
                  type="button"
                  onClick={runReplay}
                  disabled={loading || !driverId}
                  className="w-full flex items-center justify-center gap-2 px-3 py-2 rounded border border-blue-700/40 bg-blue-900/30 text-blue-200 text-[11px] tracking-[0.3em] uppercase hover:bg-blue-900/50 disabled:opacity-40 disabled:cursor-not-allowed"
                >
                  {loading ? (
                    <Loader2 size={14} className="animate-spin" />
                  ) : (
                    <Play size={14} />
                  )}
                  Run replay
                </button>

                {error && (
                  <div className="mt-3 text-xs text-red-300 border border-red-800/40 bg-red-900/10 rounded px-3 py-2">
                    {error}
                  </div>
                )}
              </div>

              <div>
                {response ? (
                  <div className="space-y-4">
                    <div className="border border-gray-800 rounded px-3 py-3">
                      <div className="text-[10px] tracking-[0.3em] uppercase text-gray-500 mb-2">
                        Divergence summary
                      </div>
                      <p className="text-xs text-gray-200 leading-relaxed">{response.rationale}</p>
                      {response.summary.biggest_delta_field && (
                        <div className="mt-3 grid grid-cols-3 gap-2 text-[10px]">
                          <div className="border border-gray-800 rounded px-2 py-1.5">
                            <div className="text-gray-500 uppercase tracking-[0.2em]">field</div>
                            <div className="text-gray-100">
                              {response.summary.biggest_delta_field
                                .replace(/_score$/, "")
                                .replace(/_/g, " ")}
                            </div>
                          </div>
                          <div className="border border-gray-800 rounded px-2 py-1.5">
                            <div className="text-gray-500 uppercase tracking-[0.2em]">delta</div>
                            <div className="text-amber-200">
                              {response.summary.biggest_delta_value.toFixed(2)}
                            </div>
                          </div>
                          <div className="border border-gray-800 rounded px-2 py-1.5">
                            <div className="text-gray-500 uppercase tracking-[0.2em]">rows</div>
                            <div className="text-gray-100">{response.baseline_count}</div>
                          </div>
                        </div>
                      )}
                    </div>

                    <div className="border border-gray-800 rounded px-3 py-3">
                      <div className="text-[10px] tracking-[0.3em] uppercase text-gray-500 mb-2">
                        Trajectory (baseline vs counterfactual)
                      </div>
                      <div className="h-48">
                        <ResponsiveContainer width="100%" height="100%">
                          <AreaChart data={chartData}>
                            <defs>
                              <linearGradient id="whatIfDelta" x1="0" y1="0" x2="0" y2="1">
                                <stop offset="0%" stopColor="#3b82f6" stopOpacity={0.4} />
                                <stop offset="100%" stopColor="#3b82f6" stopOpacity={0} />
                              </linearGradient>
                            </defs>
                            <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" />
                            <XAxis dataKey="timestamp" stroke="#4b5563" tick={{ fontSize: 9 }} />
                            <YAxis stroke="#4b5563" domain={[0, 100]} tick={{ fontSize: 9 }} />
                            <Tooltip
                              contentStyle={{
                                backgroundColor: "#0a0a0a",
                                border: "1px solid #374151",
                                fontSize: 11,
                              }}
                            />
                            <Area
                              type="monotone"
                              dataKey="counterfactual_stress"
                              name="counterfactual stress"
                              stroke="#3b82f6"
                              strokeWidth={2}
                              fill="url(#whatIfDelta)"
                            />
                            <Line
                              type="monotone"
                              dataKey="baseline_stress"
                              name="baseline stress"
                              stroke="#ef4444"
                              strokeWidth={1.5}
                              dot={false}
                            />
                            <Line
                              type="monotone"
                              dataKey="counterfactual_confidence"
                              name="counterfactual confidence"
                              stroke="#10b981"
                              strokeWidth={1.5}
                              dot={false}
                              strokeDasharray="4 2"
                            />
                            <Line
                              type="monotone"
                              dataKey="baseline_confidence"
                              name="baseline confidence"
                              stroke="#0ea5e9"
                              strokeWidth={1.5}
                              dot={false}
                            />
                          </AreaChart>
                        </ResponsiveContainer>
                      </div>
                    </div>
                  </div>
                ) : (
                  <div className="text-xs text-gray-500 border-l-2 border-gray-700 pl-3 py-2 flex items-center gap-2">
                    <RefreshCw size={12} />
                    Pick mutations on the left, then run replay. The engine fetches the last
                    window from the audit log and re-runs the cognitive maths under both
                    scenarios deterministically.
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
