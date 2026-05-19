"use client";

import React, { useEffect, useMemo, useRef, useState } from "react";
import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { Activity, AlertTriangle, Brain, ShieldCheck, Sparkles } from "lucide-react";

type CognitiveSnapshot = {
  driver_id: string;
  timestamp: string;
  stress_score: number;
  confidence_score: number;
  fatigue_score: number;
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

type ChartPoint = {
  time: string;
  stress: number;
  confidence: number;
  fatigue: number;
};

type IncomingEnvelope =
  | { channel: "cognitive-state-inference"; payload: CognitiveSnapshot }
  | { channel: "explanation-events"; payload: ExplanationEvent }
  | { channel: "heartbeat"; payload: { timestamp: string } };

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
  const [linkUp, setLinkUp] = useState<boolean>(false);
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
      socket.onerror = () => {
        setLinkUp(false);
      };
      socket.onmessage = (event) => {
        let envelope: IncomingEnvelope;
        try {
          envelope = JSON.parse(event.data) as IncomingEnvelope;
        } catch {
          return;
        }
        if (envelope.channel === "cognitive-state-inference") {
          const snap = envelope.payload;
          setLatest(snap);
          setHistory((prev) =>
            [
              ...prev,
              {
                time: formatTime(snap.timestamp),
                stress: snap.stress_score,
                confidence: snap.confidence_score,
                fatigue: snap.fatigue_score,
              },
            ].slice(-60)
          );
        } else if (envelope.channel === "explanation-events") {
          setExplanations((prev) => [envelope.payload, ...prev].slice(0, 6));
        } else if (envelope.channel === "heartbeat") {
          setLastHeartbeat(envelope.payload.timestamp);
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
      if (reconnectTimer.current) {
        clearTimeout(reconnectTimer.current);
      }
      socket?.close();
    };
  }, []);

  const stress = latest?.stress_score ?? 0;
  const confidence = latest?.confidence_score ?? 0;
  const fatigue = latest?.fatigue_score ?? 0;
  const persona = latest?.persona_state ?? "Awaiting telemetry";
  const band = latest?.confidence_band ?? "unstable";

  const bandStyle = useMemo(() => bandColor(band), [band]);

  return (
    <main className="min-h-screen p-8">
      <div className="flex justify-between items-center mb-8 border-b border-gray-800 pb-4">
        <div>
          <h1 className="text-3xl font-bold tracking-widest uppercase">NeuroPit</h1>
          <p className="text-gray-400 text-sm tracking-widest">Cognitive State Mission Control</p>
        </div>
        <div className="flex gap-4">
          <div
            className={`flex items-center gap-2 px-4 py-2 rounded border ${
              linkUp
                ? "bg-red-900/20 border-red-900/50 text-red-400"
                : "bg-gray-900/40 border-gray-700 text-gray-400"
            }`}
          >
            <div
              className={`w-2 h-2 rounded-full ${linkUp ? "bg-red-500 animate-pulse" : "bg-gray-500"}`}
            />
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

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
        <div className="bg-neuropit-dark p-6 border border-gray-800 rounded">
          <div className="flex justify-between items-center mb-4">
            <h2 className="text-gray-400 tracking-wider">STRESS INDEX</h2>
            <AlertTriangle className="text-red-500" />
          </div>
          <div className="text-5xl font-bold text-red-500">
            {stress.toFixed(1)}
            <span className="text-sm text-gray-500 ml-2">/ 100</span>
          </div>
          <p className="text-xs text-gray-500 mt-2 uppercase tracking-wider">Persona: {persona}</p>
        </div>

        <div className="bg-neuropit-dark p-6 border border-gray-800 rounded">
          <div className="flex justify-between items-center mb-4">
            <h2 className="text-gray-400 tracking-wider">CONFIDENCE</h2>
            <Brain className="text-blue-500" />
          </div>
          <div className="text-5xl font-bold text-blue-500">
            {confidence.toFixed(1)}
            <span className="text-sm text-gray-500 ml-2">/ 100</span>
          </div>
          <p className="text-xs text-gray-500 mt-2 uppercase tracking-wider">
            Driver: {latest?.driver_id ?? "n/a"}
          </p>
        </div>

        <div className="bg-neuropit-dark p-6 border border-gray-800 rounded">
          <div className="flex justify-between items-center mb-4">
            <h2 className="text-gray-400 tracking-wider">FATIGUE ACCUMULATION</h2>
            <Activity className="text-yellow-500" />
          </div>
          <div className="text-5xl font-bold text-yellow-500">
            {fatigue.toFixed(1)}
            <span className="text-sm text-gray-500 ml-2">/ 100</span>
          </div>
          <p className="text-xs text-gray-500 mt-2 uppercase tracking-wider">
            Last heartbeat: {lastHeartbeat ? formatTime(lastHeartbeat) : "n/a"}
          </p>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
        <div className="lg:col-span-3 bg-neuropit-dark p-6 border border-gray-800 rounded">
          <h2 className="text-gray-400 tracking-wider mb-6">REAL TIME COGNITIVE TRAJECTORY</h2>
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
                    <span className="text-gray-500 ml-2 uppercase">
                      via {ev.explanation.source}
                    </span>
                  </span>
                  <p className="text-sm text-gray-300">{ev.explanation.text}</p>
                </div>
              ))
            )}
          </div>
        </div>
      </div>
    </main>
  );
}
