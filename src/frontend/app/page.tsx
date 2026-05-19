"use client";

import React, { useEffect, useMemo, useRef, useState } from "react";
import Image from "next/image";
import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { Activity, AlertTriangle, Brain, Eye, Gauge, ShieldCheck, Sparkles, Target } from "lucide-react";

import { Nav } from "../components/Nav";

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

function bandColor(band: string): string {
  switch (band) {
    case "high":
      return "text-green-400 border-green-700/50 bg-green-900/20";
    case "moderate":
      return "text-yellow-400 border-yellow-700/50 bg-yellow-900/20";
    default:
      return "text-red-400 border-red-700/50 bg-red-900/20";
  }
}

export default function MissionControl() {
  const [history, setHistory] = useState<ChartPoint[]>([]);
  const [latest, setLatest] = useState<CognitiveSnapshot | null>(null);
  const [explanations, setExplanations] = useState<ExplanationEvent[]>([]);
  const [emotional, setEmotional] = useState<EmotionalEvent | null>(null);
  const [linkUp, setLinkUp] = useState(false);
  const [lastHeartbeat, setLastHeartbeat] = useState<string | null>(null);

  const reconnectTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

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
        if (envelope.channel === "cognitive-state-inference") {
          const snap = envelope.payload as CognitiveSnapshot;
          setLatest(snap);
          setHistory((prev) =>
            [
              ...prev,
              {
                time: formatTime(snap.timestamp),
                stress: snap.stress_score,
                confidence: snap.confidence_score,
                fatigue: snap.fatigue_score,
                panic: snap.panic_probability ?? 0,
              },
            ].slice(-60)
          );
        } else if (envelope.channel === "explanation-events") {
          setExplanations((prev) => [envelope.payload as ExplanationEvent, ...prev].slice(0, 6));
        } else if (envelope.channel === "emotional-events") {
          setEmotional(envelope.payload as EmotionalEvent);
        } else if (envelope.channel === "heartbeat") {
          setLastHeartbeat((envelope.payload as { timestamp: string }).timestamp);
        }
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
      socket?.close();
    };
  }, []);

  const stress = latest?.stress_score ?? 0;
  const confidence = latest?.confidence_score ?? 0;
  const fatigue = latest?.fatigue_score ?? 0;
  const cognitiveLoad = latest?.cognitive_load_score ?? 0;
  const attention = latest?.attention_stability ?? 0;
  const strategic = latest?.strategic_reliability ?? 0;
  const panicProb = latest?.panic_probability ?? 0;
  const drift = latest?.emotional_drift_score ?? 0;
  const persona = latest?.persona_state ?? "Awaiting telemetry";
  const band = latest?.confidence_band ?? "unstable";
  const bandStyle = useMemo(() => bandColor(band), [band]);

  return (
    <main className="min-h-screen p-8">
      <Nav />

      <div className="flex justify-between items-center mb-8 border-b border-gray-800 pb-4">
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
            <h1 className="text-3xl font-bold tracking-widest uppercase">NeuroPit</h1>
            <p className="text-gray-400 text-sm tracking-widest">
              Cognitive Twin Operating System / Telemetry is infrastructure. Cognition is the product.
            </p>
          </div>
        </div>
        <div className="flex gap-4">
          <div
            className={`flex items-center gap-2 px-4 py-2 rounded border ${
              linkUp
                ? "bg-red-900/20 border-red-900/50 text-red-400"
                : "bg-gray-900/40 border-gray-700 text-gray-400"
            }`}
          >
            <div className={`w-2 h-2 rounded-full ${linkUp ? "bg-red-500 animate-pulse" : "bg-gray-500"}`} />
            <span className="text-sm font-semibold tracking-wider">
              {linkUp ? "LIVE TELEMETRY" : "AWAITING LINK"}
            </span>
          </div>
          <div className={`flex items-center gap-2 px-4 py-2 rounded border ${bandStyle}`}>
            <ShieldCheck size={16} />
            <span className="text-sm tracking-wider uppercase">{band} confidence</span>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
        <CognitiveTile label="Stress" value={stress} icon={<AlertTriangle className="text-red-500" />} accent="text-red-400" />
        <CognitiveTile label="Confidence" value={confidence} icon={<Brain className="text-blue-500" />} accent="text-blue-400" />
        <CognitiveTile label="Fatigue" value={fatigue} icon={<Activity className="text-yellow-500" />} accent="text-yellow-400" />
        <CognitiveTile label="Cognitive load" value={cognitiveLoad} icon={<Gauge className="text-purple-500" />} accent="text-purple-300" />
        <CognitiveTile label="Attention" value={attention} icon={<Eye className="text-cyan-400" />} accent="text-cyan-300" />
        <CognitiveTile label="Strategic" value={strategic} icon={<Target className="text-emerald-400" />} accent="text-emerald-300" />
        <CognitiveTile label="Panic prob" value={panicProb} icon={<AlertTriangle className="text-orange-400" />} accent="text-orange-300" />
        <CognitiveTile label="Emotional drift" value={drift} icon={<Sparkles className="text-pink-400" />} accent="text-pink-300" />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
        <div className="lg:col-span-3 bg-neuropit-dark p-6 border border-gray-800 rounded">
          <h2 className="text-gray-400 tracking-wider mb-2 flex items-center justify-between">
            <span>REAL TIME COGNITIVE TRAJECTORY</span>
            <span className="text-xs text-gray-500 uppercase">
              Persona: {persona} / Driver: {latest?.driver_id ?? "n/a"} / Heartbeat:{" "}
              {lastHeartbeat ? formatTime(lastHeartbeat) : "n/a"}
            </span>
          </h2>
          <div className="h-96">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={history}>
                <CartesianGrid strokeDasharray="3 3" stroke="#333" />
                <XAxis dataKey="time" stroke="#666" />
                <YAxis stroke="#666" domain={[0, 100]} />
                <Tooltip contentStyle={{ backgroundColor: "#1a1a1a", border: "1px solid #333" }} />
                <Line type="monotone" dataKey="stress" stroke="#ef4444" strokeWidth={2} dot={false} />
                <Line type="monotone" dataKey="confidence" stroke="#3b82f6" strokeWidth={2} dot={false} />
                <Line type="monotone" dataKey="fatigue" stroke="#eab308" strokeWidth={2} dot={false} />
                <Line type="monotone" dataKey="panic" stroke="#f97316" strokeWidth={2} dot={false} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="bg-neuropit-dark p-6 border border-gray-800 rounded flex flex-col">
          <h2 className="text-gray-400 tracking-wider mb-4 flex items-center gap-2">
            <Sparkles size={16} className="text-purple-400" />
            IBM GRANITE EXPLAINABILITY
          </h2>
          <div className="flex-1 overflow-y-auto space-y-4 max-h-96">
            {explanations.length === 0 ? (
              <div className="border-l-2 border-gray-700 pl-4 py-2 text-gray-500 text-sm">
                Waiting for the first cognitive evaluation. The reasoning panel will populate as the pipeline starts producing events.
              </div>
            ) : (
              explanations.map((ev, idx) => (
                <div key={`${ev.timestamp}-${idx}`} className="border-l-2 border-blue-500 pl-4 py-2">
                  <span className="text-xs text-blue-400 font-bold tracking-widest block mb-1">
                    {ev.driver_id} {formatTime(ev.timestamp)}
                    <span className="text-gray-500 ml-2 uppercase">via {ev.explanation.source}</span>
                  </span>
                  <p className="text-sm text-gray-300">{ev.explanation.text}</p>
                </div>
              ))
            )}
          </div>

          {emotional && (
            <div className="mt-6 pt-4 border-t border-gray-800">
              <div className="text-xs tracking-widest uppercase text-gray-500 mb-2">Emotional distribution</div>
              <div className="text-sm text-gray-200">
                Dominant: <span className="text-purple-300 font-semibold uppercase">{emotional.dominant_emotion}</span> ({(emotional.dominant_probability * 100).toFixed(1)}%)
              </div>
              <div className="grid grid-cols-3 gap-1 mt-2 text-xs">
                {Object.entries(emotional.distribution).map(([key, value]) => (
                  <div key={key} className="border border-gray-800 rounded px-2 py-1">
                    <span className="text-gray-500 uppercase">{key}</span>
                    <span className="text-gray-100 float-right">{(value * 100).toFixed(0)}%</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </main>
  );
}

function CognitiveTile({
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
    <div className="bg-neuropit-dark p-4 border border-gray-800 rounded">
      <div className="flex justify-between items-center mb-2">
        <h2 className="text-gray-400 text-xs tracking-widest uppercase">{label}</h2>
        {icon}
      </div>
      <div className={`text-3xl font-bold ${accent}`}>
        {value.toFixed(1)}
        <span className="text-xs text-gray-500 ml-1">/ 100</span>
      </div>
    </div>
  );
}
