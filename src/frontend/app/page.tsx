"use client";

import React, { useEffect, useMemo, useRef, useState } from "react";
import Image from "next/image";
import {
  Area,
  AreaChart,
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import {
  Activity,
  AlertTriangle,
  Brain,
  Eye,
  Gauge,
  ShieldCheck,
  Sparkles,
  Target,
  Wifi,
} from "lucide-react";

import { Footer } from "../components/Footer";
import { MetricRing } from "../components/MetricRing";
import { Nav } from "../components/Nav";
import { PersonaTick, PersonaTimeline } from "../components/PersonaTimeline";
import { PrescriptionPanel, type PrescriptionPayload } from "../components/PrescriptionPanel";
import { WhatIfDrawer } from "../components/WhatIfDrawer";
import { ensureDashboardToken } from "../lib/api";

type CognitiveSnapshot = {
  driver_id: string;
  timestamp: string;
  stress_score: number;
  confidence_score: number;
  fatigue_score: number;
  cognitive_load_score: number;
  attention_stability: number;
  strategic_reliability: number;
  panic_probability: number;
  emotional_drift_score: number;
  tunnel_vision_prob: number;
  persona_state: string;
  confidence_band: string;
};

type ExplanationEvent = {
  driver_id: string;
  timestamp: string;
  state: CognitiveSnapshot;
  explanation: {
    text: string;
    source: string;
    model: string;
    tokens?: number | null;
  };
};

type EmotionalEvent = {
  driver_id: string;
  timestamp: string;
  distribution: Record<string, number>;
  dominant_emotion: string;
  dominant_probability: number;
};

type AnomalyEvent = {
  driver_id: string;
  timestamp: string;
  source_persona: string;
  source_confidence_band: string;
  horizons: Record<string, Record<string, number>>;
};

type PrescriptionEnvelopePayload = {
  driver_id: string;
  timestamp: string;
  prescription: PrescriptionPayload;
};

type ChartPoint = {
  time: string;
  stress: number;
  confidence: number;
  fatigue: number;
  panic: number;
};

type IncomingEnvelope =
  | { channel: "cognitive-state-inference"; payload: CognitiveSnapshot }
  | { channel: "explanation-events"; payload: ExplanationEvent }
  | { channel: "emotional-events"; payload: EmotionalEvent }
  | { channel: "anomaly-events"; payload: AnomalyEvent }
  | { channel: "cognitive-prescriptions"; payload: PrescriptionEnvelopePayload }
  | { channel: "heartbeat"; payload: { timestamp: string } }
  | { channel: string; payload: unknown };

const DEFAULT_WS_URL =
  process.env.NEXT_PUBLIC_NEUROPIT_WS_URL ?? "ws://localhost:8000/ws/cognitive";

function formatTime(iso: string): string {
  try {
    return new Date(iso).toLocaleTimeString().split(" ")[0];
  } catch {
    return iso.slice(11, 19);
  }
}

function bandStyle(band: string | null): { label: string; tone: string } {
  switch (band) {
    case "high":
      return {
        label: "STABLE LINK",
        tone: "text-emerald-400 border-emerald-700/50 bg-emerald-900/20",
      };
    case "moderate":
      return {
        label: "MODERATE BAND",
        tone: "text-amber-300 border-amber-700/50 bg-amber-900/20",
      };
    case "unstable":
      return {
        label: "UNSTABLE BAND",
        tone: "text-red-400 border-red-700/50 bg-red-900/20",
      };
    default:
      return {
        label: "AWAITING TWIN",
        tone: "text-gray-400 border-gray-700/50 bg-gray-900/30",
      };
  }
}

type DriverState = {
  history: ChartPoint[];
  persona: PersonaTick[];
  latest: CognitiveSnapshot | null;
  emotional: EmotionalEvent | null;
  forecast: AnomalyEvent | null;
  prescription: PrescriptionPayload | null;
};

const emptyDriverState = (): DriverState => ({
  history: [],
  persona: [],
  latest: null,
  emotional: null,
  forecast: null,
  prescription: null,
});

export default function MissionControl() {
  const [byDriver, setByDriver] = useState<Record<string, DriverState>>({});
  const [explanations, setExplanations] = useState<ExplanationEvent[]>([]);
  const [selectedDriver, setSelectedDriver] = useState<string | null>(null);
  const [linkUp, setLinkUp] = useState(false);
  const [lastHeartbeat, setLastHeartbeat] = useState<string | null>(null);

  const reconnectTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const flushTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const incomingBuffer = useRef<IncomingEnvelope[]>([]);

  useEffect(() => {
    void ensureDashboardToken();
  }, []);

  // The cognitive engine emits roughly ten frames per second per
  // driver, plus emotional, anomaly, prescription, and explanation
  // events. Setting React state synchronously on every frame triggers
  // a full pit wall re-render at the same cadence and the UI feels
  // sluggish. We buffer incoming envelopes and flush them in batches
  // four times a second so the dashboard stays smooth even under
  // multi-driver load.
  const applyBatch = (events: IncomingEnvelope[]): void => {
    if (events.length === 0) return;

    const driverDeltas: Record<string, Partial<DriverState>> = {};
    const driverHistoryAdds: Record<string, ChartPoint[]> = {};
    const driverPersonaAdds: Record<string, PersonaTick[]> = {};
    const newExplanations: ExplanationEvent[] = [];
    let newHeartbeat: string | null = null;
    let nextSelectedFallback: string | null = null;

    for (const envelope of events) {
      if (envelope.channel === "cognitive-state-inference") {
        const snap = envelope.payload as CognitiveSnapshot;
        const driverId = snap.driver_id;
        driverDeltas[driverId] = { ...(driverDeltas[driverId] ?? {}), latest: snap };
        const point: ChartPoint = {
          time: formatTime(snap.timestamp),
          stress: snap.stress_score,
          confidence: snap.confidence_score,
          fatigue: snap.fatigue_score,
          panic: snap.panic_probability ?? 0,
        };
        (driverHistoryAdds[driverId] ??= []).push(point);
        (driverPersonaAdds[driverId] ??= []).push({
          timestamp: snap.timestamp,
          persona: snap.persona_state,
        });
        nextSelectedFallback ??= driverId;
      } else if (envelope.channel === "explanation-events") {
        newExplanations.push(envelope.payload as ExplanationEvent);
      } else if (envelope.channel === "emotional-events") {
        const evt = envelope.payload as EmotionalEvent;
        driverDeltas[evt.driver_id] = { ...(driverDeltas[evt.driver_id] ?? {}), emotional: evt };
      } else if (envelope.channel === "anomaly-events") {
        const evt = envelope.payload as AnomalyEvent;
        driverDeltas[evt.driver_id] = { ...(driverDeltas[evt.driver_id] ?? {}), forecast: evt };
      } else if (envelope.channel === "cognitive-prescriptions") {
        const evt = envelope.payload as PrescriptionEnvelopePayload;
        if (evt.driver_id && evt.prescription) {
          driverDeltas[evt.driver_id] = {
            ...(driverDeltas[evt.driver_id] ?? {}),
            prescription: evt.prescription,
          };
        }
      } else if (envelope.channel === "heartbeat") {
        newHeartbeat = (envelope.payload as { timestamp: string }).timestamp;
      }
    }

    setByDriver((prev) => {
      const next: Record<string, DriverState> = { ...prev };
      const touched = new Set([
        ...Object.keys(driverDeltas),
        ...Object.keys(driverHistoryAdds),
        ...Object.keys(driverPersonaAdds),
      ]);
      for (const driverId of touched) {
        const base = next[driverId] ?? emptyDriverState();
        const merged: DriverState = {
          ...base,
          ...(driverDeltas[driverId] ?? {}),
        };
        const historyAdds = driverHistoryAdds[driverId];
        if (historyAdds && historyAdds.length > 0) {
          merged.history = [...base.history, ...historyAdds].slice(-120);
        }
        const personaAdds = driverPersonaAdds[driverId];
        if (personaAdds && personaAdds.length > 0) {
          merged.persona = [...base.persona, ...personaAdds].slice(-80);
        }
        next[driverId] = merged;
      }
      return next;
    });

    if (newExplanations.length > 0) {
      setExplanations((prev) => [...newExplanations.reverse(), ...prev].slice(0, 8));
    }
    if (newHeartbeat) {
      setLastHeartbeat(newHeartbeat);
    }
    if (nextSelectedFallback) {
      setSelectedDriver((current) => current ?? nextSelectedFallback);
    }
  };

  const scheduleFlush = (): void => {
    if (flushTimer.current) return;
    flushTimer.current = setTimeout(() => {
      flushTimer.current = null;
      const batch = incomingBuffer.current;
      incomingBuffer.current = [];
      applyBatch(batch);
    }, 250);
  };

  useEffect(() => {
    let socket: WebSocket | null = null;
    let cancelled = false;

    const connect = () => {
      if (cancelled) return;
      try {
        socket = new WebSocket(DEFAULT_WS_URL);
      } catch {
        scheduleReconnect();
        return;
      }
      socket.onopen = () => setLinkUp(true);
      socket.onclose = () => {
        setLinkUp(false);
        scheduleReconnect();
      };
      socket.onerror = () => setLinkUp(false);
      socket.onmessage = (event) => {
        let envelope: IncomingEnvelope;
        try {
          envelope = JSON.parse(event.data) as IncomingEnvelope;
        } catch {
          return;
        }
        incomingBuffer.current.push(envelope);
        scheduleFlush();
      };
    };

    const scheduleReconnect = () => {
      if (reconnectTimer.current) return;
      reconnectTimer.current = setTimeout(() => {
        reconnectTimer.current = null;
        connect();
      }, 2500);
    };

    connect();

    return () => {
      cancelled = true;
      if (reconnectTimer.current) clearTimeout(reconnectTimer.current);
      if (flushTimer.current) clearTimeout(flushTimer.current);
      socket?.close();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const drivers = useMemo(() => Object.keys(byDriver).sort(), [byDriver]);
  const active = selectedDriver ? byDriver[selectedDriver] : null;
  const latest = active?.latest ?? null;

  const stress = latest?.stress_score ?? 0;
  const confidence = latest?.confidence_score ?? 0;
  const fatigue = latest?.fatigue_score ?? 0;
  const cognitiveLoad = latest?.cognitive_load_score ?? 0;
  const attention = latest?.attention_stability ?? 0;
  const strategic = latest?.strategic_reliability ?? 0;
  const panicProb = latest?.panic_probability ?? 0;
  const drift = latest?.emotional_drift_score ?? 0;
  const persona = latest?.persona_state ?? "Awaiting telemetry";
  const band = latest?.confidence_band ?? null;
  const bandView = useMemo(() => bandStyle(band), [band]);
  const hasLatest = latest !== null;
  const driverScopedExplanations = useMemo(
    () => (selectedDriver ? explanations.filter((e) => e.driver_id === selectedDriver) : explanations),
    [explanations, selectedDriver]
  );

  return (
    <main className="min-h-screen p-6 md:p-8">
      <Nav />

      <div className="flex flex-col gap-3 md:flex-row md:justify-between md:items-center mb-6 border-b border-gray-800 pb-5">
        <div className="flex items-center gap-4">
          <Image
            src="/neuropit-logo.png"
            alt="NeuroPit logo"
            width={64}
            height={64}
            priority
            className="rounded"
          />
          <div>
            <h1 className="text-3xl md:text-4xl font-black tracking-[0.25em] uppercase">
              Mission Control
            </h1>
            <p className="text-gray-400 text-[11px] tracking-[0.3em] uppercase mt-1">
              Cognitive Twin Operating System / Telemetry is infrastructure. Cognition is the product.
            </p>
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-3">
          <div
            className={`flex items-center gap-2 px-3 py-2 rounded border ${
              linkUp
                ? "bg-red-900/20 border-red-900/50 text-red-300"
                : "bg-gray-900/40 border-gray-700 text-gray-400"
            }`}
          >
            <Wifi size={14} />
            <span className="text-[11px] font-semibold tracking-[0.3em]">
              {linkUp ? "LIVE TELEMETRY" : "AWAITING LINK"}
            </span>
            <span
              className={`w-2 h-2 rounded-full ${
                linkUp ? "bg-red-500 animate-pulse" : "bg-gray-500"
              }`}
            />
          </div>
          <div className={`flex items-center gap-2 px-3 py-2 rounded border ${bandView.tone}`}>
            <ShieldCheck size={14} />
            <span className="text-[11px] tracking-[0.3em] uppercase">{bandView.label}</span>
          </div>
          <div className="flex items-center gap-2 px-3 py-2 rounded border border-gray-800 bg-gray-900/40 text-gray-400 text-[11px] tracking-[0.3em] uppercase">
            HEARTBEAT {lastHeartbeat ? formatTime(lastHeartbeat) : "...."}
          </div>
          <WhatIfDrawer driverId={selectedDriver} />
        </div>
      </div>

      <div className="flex flex-wrap gap-2 mb-6">
        <span className="text-[10px] tracking-[0.3em] uppercase text-gray-500 self-center mr-2">
          Driver
        </span>
        {drivers.length === 0 && (
          <span className="text-xs text-gray-600">Awaiting first cognitive event</span>
        )}
        {drivers.map((driverId) => {
          const ds = byDriver[driverId];
          const dPersona = ds.latest?.persona_state ?? "Recovery";
          const dBand = ds.latest?.confidence_band ?? "unstable";
          const isActive = driverId === selectedDriver;
          return (
            <button
              key={driverId}
              onClick={() => setSelectedDriver(driverId)}
              className={`px-3 py-2 rounded border transition-colors text-left ${
                isActive
                  ? "border-red-700/70 bg-red-900/30 text-red-200"
                  : "border-gray-800 bg-gray-900/40 text-gray-400 hover:text-gray-200 hover:border-gray-600"
              }`}
            >
              <div className="text-sm font-bold tracking-[0.25em] uppercase">{driverId}</div>
              <div className="text-[10px] tracking-[0.25em] uppercase text-gray-500">
                {dPersona} · {dBand}
              </div>
            </button>
          );
        })}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-4 gap-4 mb-6">
        <div className="bg-neuropit-dark border border-gray-800 rounded p-5 flex flex-col items-center">
          <MetricRing label="Stress" value={stress} accent="text-red-300" />
        </div>
        <div className="bg-neuropit-dark border border-gray-800 rounded p-5 flex flex-col items-center">
          <MetricRing label="Confidence" value={confidence} accent="text-blue-300" inverted />
        </div>
        <div className="bg-neuropit-dark border border-gray-800 rounded p-5 flex flex-col items-center">
          <MetricRing label="Fatigue" value={fatigue} accent="text-amber-300" />
        </div>
        <div className="bg-neuropit-dark border border-gray-800 rounded p-5 flex flex-col items-center">
          <MetricRing label="Panic Prob" value={panicProb} accent="text-orange-300" />
        </div>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-6">
        <SecondaryTile label="Cognitive load" value={cognitiveLoad} icon={<Gauge size={14} className="text-purple-300" />} accent="text-purple-200" />
        <SecondaryTile label="Attention" value={attention} icon={<Eye size={14} className="text-cyan-300" />} accent="text-cyan-200" />
        <SecondaryTile label="Strategic" value={strategic} icon={<Target size={14} className="text-emerald-300" />} accent="text-emerald-200" />
        <SecondaryTile label="Emotional drift" value={drift} icon={<Sparkles size={14} className="text-pink-300" />} accent="text-pink-200" />
      </div>

      <div className="mb-6">
        <PrescriptionPanel prescription={active?.prescription ?? null} driverId={selectedDriver} />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-4 gap-4">
        <div className="lg:col-span-3 bg-neuropit-dark border border-gray-800 rounded p-5">
          <div className="flex justify-between items-center mb-4">
            <h2 className="text-[11px] tracking-[0.3em] uppercase text-gray-400">
              Real time cognitive trajectory
            </h2>
            <span className="text-[10px] tracking-[0.3em] uppercase text-gray-500">
              {selectedDriver ?? "—"} · {persona}
            </span>
          </div>
          <div className="h-80">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={active?.history ?? []}>
                <defs>
                  <linearGradient id="stressGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="#ef4444" stopOpacity={0.4} />
                    <stop offset="100%" stopColor="#ef4444" stopOpacity={0} />
                  </linearGradient>
                  <linearGradient id="confidenceGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="#3b82f6" stopOpacity={0.3} />
                    <stop offset="100%" stopColor="#3b82f6" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" />
                <XAxis dataKey="time" stroke="#4b5563" tick={{ fontSize: 10 }} />
                <YAxis stroke="#4b5563" domain={[0, 100]} tick={{ fontSize: 10 }} />
                <Tooltip
                  contentStyle={{
                    backgroundColor: "#0a0a0a",
                    border: "1px solid #374151",
                    fontSize: 11,
                  }}
                />
                <Area type="monotone" dataKey="stress" stroke="#ef4444" strokeWidth={2} fill="url(#stressGrad)" />
                <Area type="monotone" dataKey="confidence" stroke="#3b82f6" strokeWidth={2} fill="url(#confidenceGrad)" />
                <Line type="monotone" dataKey="fatigue" stroke="#eab308" strokeWidth={1.5} dot={false} />
                <Line type="monotone" dataKey="panic" stroke="#f97316" strokeWidth={1.5} dot={false} />
              </AreaChart>
            </ResponsiveContainer>
          </div>
          <div className="mt-4">
            <h3 className="text-[10px] tracking-[0.3em] uppercase text-gray-500 mb-2">Persona drift</h3>
            <PersonaTimeline ticks={active?.persona ?? []} />
          </div>
        </div>

        <div className="bg-neuropit-dark border border-gray-800 rounded p-5 flex flex-col">
          <h2 className="text-[11px] tracking-[0.3em] uppercase text-gray-400 mb-3 flex items-center gap-2">
            <Sparkles size={14} className="text-purple-300" />
            IBM Granite explainability
          </h2>
          <div className="flex-1 overflow-y-auto space-y-3 max-h-80 pr-1">
            {driverScopedExplanations.length === 0 ? (
              <div className="border-l-2 border-gray-700 pl-3 py-2 text-gray-500 text-xs">
                Awaiting first reasoning event.
              </div>
            ) : (
              driverScopedExplanations.map((ev, idx) => (
                <div key={`${ev.timestamp}-${idx}`} className="border-l-2 border-blue-500 pl-3 py-1.5">
                  <div className="text-[9px] tracking-[0.3em] uppercase text-blue-400 mb-1 flex justify-between">
                    <span>
                      {ev.driver_id} {formatTime(ev.timestamp)}
                    </span>
                    <span className="text-gray-500">via {ev.explanation.source}</span>
                  </div>
                  <p className="text-xs text-gray-200 leading-relaxed">{ev.explanation.text}</p>
                </div>
              ))
            )}
          </div>

          {active?.emotional && (
            <div className="mt-4 pt-3 border-t border-gray-800">
              <div className="text-[10px] tracking-[0.3em] uppercase text-gray-500 mb-2">
                Emotional distribution
              </div>
              <div className="text-xs text-gray-200 mb-2">
                Dominant:{" "}
                <span className="text-purple-300 font-bold uppercase">
                  {active.emotional.dominant_emotion}
                </span>{" "}
                ({(active.emotional.dominant_probability * 100).toFixed(1)}%)
              </div>
              <div className="grid grid-cols-3 gap-1 text-[10px]">
                {Object.entries(active.emotional.distribution).map(([key, value]) => (
                  <div key={key} className="border border-gray-800 rounded px-1.5 py-1">
                    <span className="text-gray-500 uppercase block leading-tight">{key}</span>
                    <span className="text-gray-100">{(value * 100).toFixed(0)}%</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {active?.forecast && (
            <div className="mt-4 pt-3 border-t border-gray-800">
              <div className="text-[10px] tracking-[0.3em] uppercase text-gray-500 mb-2 flex items-center gap-1">
                <AlertTriangle size={11} className="text-orange-400" />
                5s failure forecast
              </div>
              <div className="grid grid-cols-2 gap-1 text-[10px]">
                {Object.entries(active.forecast.horizons["5s"] ?? {}).map(([key, value]) => (
                  <div key={key} className="border border-gray-800 rounded px-1.5 py-1">
                    <span className="text-gray-500 uppercase block leading-tight">
                      {key.replace(/_/g, " ")}
                    </span>
                    <span className="text-orange-200">{(value * 100).toFixed(0)}%</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>

      <Footer />
    </main>
  );
}

function SecondaryTile({
  label,
  value,
  icon,
  accent,
}: {
  label: string;
  value: number;
  icon: React.ReactNode;
  accent: string;
}) {
  return (
    <div className="bg-neuropit-dark border border-gray-800 rounded px-4 py-3">
      <div className="flex justify-between items-center mb-1">
        <span className="text-[10px] tracking-[0.3em] uppercase text-gray-500">{label}</span>
        {icon}
      </div>
      <div className={`text-2xl font-black tracking-tight ${accent}`}>
        {value.toFixed(1)}
        <span className="text-[10px] text-gray-600 ml-1">/ 100</span>
      </div>
    </div>
  );
}
