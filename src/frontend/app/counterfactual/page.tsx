"use client";

import React, { useState } from "react";
import { Shuffle, TrendingDown } from "lucide-react";

import { Nav } from "../../components/Nav";
import { CounterfactualResult, LapSummary, postJSON } from "../../lib/api";

const SCENARIOS = [
  "earlier_pit_stop",
  "lower_fatigue",
  "stable_emotional_state",
  "delayed_rain_onset",
  "reduced_pressure_environment",
];

const DEFAULT_INPUTS: LapSummary = {
  driver_id: "HAM",
  lap_number: 28,
  actual_lap_time_s: 92.9,
  average_stress: 70,
  average_fatigue: 55,
  panic_events: 1,
};

export default function CounterfactualPage() {
  const [inputs, setInputs] = useState<LapSummary>(DEFAULT_INPUTS);
  const [results, setResults] = useState<CounterfactualResult[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function runAll() {
    setBusy(true);
    setError(null);
    setResults([]);
    try {
      const collected: CounterfactualResult[] = [];
      for (const scenario of SCENARIOS) {
        const data = await postJSON<LapSummary, CounterfactualResult>(`/counterfactual/${scenario}`, inputs);
        collected.push(data);
      }
      setResults(collected);
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
        <h1 className="text-3xl font-bold tracking-widest uppercase">Counterfactual</h1>
        <p className="text-gray-400 text-sm tracking-widest mt-1">
          Explore the five canonical what if scenarios from the PRD against a baseline lap.
        </p>
      </header>

      <section className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="bg-neuropit-dark p-6 border border-gray-800 rounded">
          <h2 className="text-gray-400 tracking-wider mb-4 flex items-center gap-2">
            <Shuffle size={16} className="text-blue-400" />
            Baseline lap
          </h2>
          <div className="grid grid-cols-2 gap-4">
            {[
              { key: "driver_id", label: "Driver", numeric: false },
              { key: "lap_number", label: "Lap number", numeric: true },
              { key: "actual_lap_time_s", label: "Actual lap time (s)", numeric: true },
              { key: "average_stress", label: "Avg stress", numeric: true },
              { key: "average_fatigue", label: "Avg fatigue", numeric: true },
              { key: "panic_events", label: "Panic events", numeric: true },
            ].map((field) => (
              <label
                key={field.key}
                className="text-xs tracking-widest text-gray-400 uppercase flex flex-col gap-1"
              >
                {field.label}
                <input
                  type={field.numeric ? "number" : "text"}
                  value={(inputs as Record<string, string | number>)[field.key]}
                  onChange={bind(field.key as keyof LapSummary, field.numeric)}
                  className="bg-black/40 border border-gray-800 rounded px-3 py-2 text-sm text-gray-100"
                />
              </label>
            ))}
          </div>
          <button
            onClick={runAll}
            disabled={busy}
            className="mt-6 px-4 py-2 rounded border border-blue-700/60 bg-blue-900/20 text-blue-300 text-sm tracking-widest uppercase hover:bg-blue-900/40 disabled:opacity-50"
          >
            {busy ? "Running scenarios" : "Run all scenarios"}
          </button>
        </div>

        <div className="bg-neuropit-dark p-6 border border-gray-800 rounded">
          <h2 className="text-gray-400 tracking-wider mb-4 flex items-center gap-2">
            <TrendingDown size={16} className="text-green-400" />
            Scenario results
          </h2>
          {error && <div className="text-sm text-red-400 mb-4">{error}</div>}
          {results.length === 0 && !error && (
            <p className="text-sm text-gray-500">Submit a baseline lap to populate scenarios.</p>
          )}
          <div className="space-y-3">
            {results.map((result) => (
              <div key={result.scenario} className="border border-gray-800 rounded p-3">
                <div className="flex justify-between text-xs tracking-widest uppercase text-gray-500">
                  <span>{result.scenario.replace(/_/g, " ")}</span>
                  <span className={result.lap_delta_s <= 0 ? "text-green-400" : "text-red-400"}>
                    {result.lap_delta_s > 0 ? "+" : ""}
                    {result.lap_delta_s.toFixed(2)}s
                  </span>
                </div>
                <div className="text-sm text-gray-300 mt-1">{result.rationale}</div>
                <div className="text-xs text-gray-500 mt-2">
                  Counterfactual lap: {result.counterfactual_lap_time_s.toFixed(2)}s
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>
    </main>
  );
}
