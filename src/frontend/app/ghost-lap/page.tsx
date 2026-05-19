"use client";

import React, { useState } from "react";
import { BarChart3, Gauge, Sparkles } from "lucide-react";

import { Nav } from "../../components/Nav";
import { GhostLapResult, LapSummary, postJSON } from "../../lib/api";

const DEFAULT_INPUTS: LapSummary = {
  driver_id: "VER",
  lap_number: 14,
  actual_lap_time_s: 92.4,
  average_stress: 60,
  average_fatigue: 35,
  panic_events: 1,
};

export default function GhostLapPage() {
  const [inputs, setInputs] = useState<LapSummary>(DEFAULT_INPUTS);
  const [result, setResult] = useState<GhostLapResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function runGhostLap() {
    setBusy(true);
    setError(null);
    try {
      const data = await postJSON<LapSummary, GhostLapResult>("/ghost-lap", inputs);
      setResult(data);
    } catch (exc) {
      setError(String(exc));
    } finally {
      setBusy(false);
    }
  }

  function bind<K extends keyof LapSummary>(key: K, numeric: boolean) {
    return (event: React.ChangeEvent<HTMLInputElement>) => {
      const raw = event.target.value;
      setInputs((prev) => ({ ...prev, [key]: numeric ? Number(raw) : raw } as LapSummary));
    };
  }

  return (
    <main className="min-h-screen p-8">
      <Nav />

      <header className="mb-6">
        <h1 className="text-3xl font-bold tracking-widest uppercase">Ghost Lap</h1>
        <p className="text-gray-400 text-sm tracking-widest mt-1">
          Cognitive normalised lap reconstruction. Attribute lost time to the driver cognitive state, not the car.
        </p>
      </header>

      <section className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="bg-neuropit-dark p-6 border border-gray-800 rounded">
          <h2 className="text-gray-400 tracking-wider mb-4 flex items-center gap-2">
            <Gauge size={16} className="text-yellow-400" />
            Lap inputs
          </h2>
          <div className="grid grid-cols-2 gap-4">
            <label className="text-xs tracking-widest text-gray-400 uppercase flex flex-col gap-1">
              Driver
              <input
                value={inputs.driver_id}
                onChange={bind("driver_id", false)}
                className="bg-black/40 border border-gray-800 rounded px-3 py-2 text-sm text-gray-100"
              />
            </label>
            <label className="text-xs tracking-widest text-gray-400 uppercase flex flex-col gap-1">
              Lap number
              <input
                type="number"
                value={inputs.lap_number}
                onChange={bind("lap_number", true)}
                className="bg-black/40 border border-gray-800 rounded px-3 py-2 text-sm text-gray-100"
              />
            </label>
            <label className="text-xs tracking-widest text-gray-400 uppercase flex flex-col gap-1">
              Actual lap time (s)
              <input
                type="number"
                step="0.01"
                value={inputs.actual_lap_time_s}
                onChange={bind("actual_lap_time_s", true)}
                className="bg-black/40 border border-gray-800 rounded px-3 py-2 text-sm text-gray-100"
              />
            </label>
            <label className="text-xs tracking-widest text-gray-400 uppercase flex flex-col gap-1">
              Avg stress
              <input
                type="number"
                value={inputs.average_stress}
                onChange={bind("average_stress", true)}
                className="bg-black/40 border border-gray-800 rounded px-3 py-2 text-sm text-gray-100"
              />
            </label>
            <label className="text-xs tracking-widest text-gray-400 uppercase flex flex-col gap-1">
              Avg fatigue
              <input
                type="number"
                value={inputs.average_fatigue}
                onChange={bind("average_fatigue", true)}
                className="bg-black/40 border border-gray-800 rounded px-3 py-2 text-sm text-gray-100"
              />
            </label>
            <label className="text-xs tracking-widest text-gray-400 uppercase flex flex-col gap-1">
              Panic events
              <input
                type="number"
                value={inputs.panic_events}
                onChange={bind("panic_events", true)}
                className="bg-black/40 border border-gray-800 rounded px-3 py-2 text-sm text-gray-100"
              />
            </label>
          </div>
          <button
            onClick={runGhostLap}
            disabled={busy}
            className="mt-6 px-4 py-2 rounded border border-red-700/60 bg-red-900/20 text-red-300 text-sm tracking-widest uppercase hover:bg-red-900/40 disabled:opacity-50"
          >
            {busy ? "Reconstructing" : "Reconstruct ghost lap"}
          </button>
        </div>

        <div className="bg-neuropit-dark p-6 border border-gray-800 rounded">
          <h2 className="text-gray-400 tracking-wider mb-4 flex items-center gap-2">
            <BarChart3 size={16} className="text-purple-400" />
            Result
          </h2>
          {error && <div className="text-sm text-red-400 mb-4">{error}</div>}
          {!result && !error && (
            <p className="text-sm text-gray-500">
              Run the reconstruction to see the lost time breakdown.
            </p>
          )}
          {result && (
            <div className="space-y-4">
              <div className="text-3xl font-bold text-purple-300">
                {result.ghost_lap_time_s.toFixed(2)}s
                <span className="text-xs text-gray-500 ml-2 tracking-widest uppercase">
                  ghost lap
                </span>
              </div>
              <div className="text-sm text-gray-400">
                Actual lap: {result.actual_lap_time_s.toFixed(2)}s. Lost cognitive time:{" "}
                <span className="text-yellow-300 font-semibold">{result.lost_time_s.toFixed(2)}s</span>.
              </div>
              <div className="grid grid-cols-1 gap-2 text-sm">
                {Object.entries(result.contributions).map(([name, value]) => (
                  <div
                    key={name}
                    className="flex justify-between border-b border-gray-800 pb-1 text-gray-300"
                  >
                    <span className="text-xs tracking-widest uppercase text-gray-500 flex items-center gap-2">
                      <Sparkles size={12} className="text-purple-400" />
                      {name.replace(/_/g, " ")}
                    </span>
                    <span className="font-semibold text-purple-200">{value.toFixed(2)}s</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </section>
    </main>
  );
}
