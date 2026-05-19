"use client";

import React, { useEffect, useRef, useState } from "react";
import { ScrollText, Sparkles } from "lucide-react";

import { Nav } from "../../components/Nav";

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
    tokens: number | null;
    grounding?: Array<{ document_title: string; snippet: string; score: number }>;
  };
};

type IncomingEnvelope =
  | { channel: "explanation-events"; payload: ExplanationEvent }
  | { channel: "cognitive-state-inference"; payload: CognitiveSnapshot }
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

export default function ExplainabilityPage() {
  const [events, setEvents] = useState<ExplanationEvent[]>([]);
  const [linkUp, setLinkUp] = useState(false);
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
        if (envelope.channel === "explanation-events") {
          setEvents((prev) => [envelope.payload as ExplanationEvent, ...prev].slice(0, 30));
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

  return (
    <main className="min-h-screen p-8">
      <Nav />

      <header className="mb-6 flex justify-between items-center">
        <div>
          <h1 className="text-3xl font-bold tracking-widest uppercase">Explainability</h1>
          <p className="text-gray-400 text-sm tracking-widest mt-1">
            Live IBM Granite reasoning timeline, grounded in the motorsport ontology when available.
          </p>
        </div>
        <div
          className={`flex items-center gap-2 px-4 py-2 rounded border text-xs tracking-widest uppercase ${
            linkUp
              ? "border-green-700/60 bg-green-900/20 text-green-300"
              : "border-gray-700 bg-gray-900/40 text-gray-400"
          }`}
        >
          <span className={`w-2 h-2 rounded-full ${linkUp ? "bg-green-400 animate-pulse" : "bg-gray-500"}`} />
          {linkUp ? "Reasoning live" : "Awaiting link"}
        </div>
      </header>

      <section className="space-y-4">
        {events.length === 0 && (
          <div className="border border-dashed border-gray-800 rounded p-6 text-sm text-gray-500">
            Waiting for the first explanation event. Start the backend, the gateway, and the streamer to populate this page.
          </div>
        )}
        {events.map((event, idx) => (
          <article
            key={`${event.timestamp}-${idx}`}
            className="bg-neuropit-dark border border-gray-800 rounded p-5"
          >
            <header className="flex justify-between items-center mb-3 text-xs tracking-widest uppercase text-gray-500">
              <div className="flex items-center gap-3">
                <Sparkles size={14} className="text-purple-400" />
                <span>{event.driver_id}</span>
                <span>{formatTime(event.timestamp)}</span>
                <span className="text-gray-600">via {event.explanation.source}</span>
              </div>
              <span>{event.state.persona_state} / {event.state.confidence_band}</span>
            </header>
            <p className="text-sm text-gray-200 leading-relaxed">{event.explanation.text}</p>

            <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mt-4 text-xs">
              {[
                { label: "Stress", value: event.state.stress_score },
                { label: "Confidence", value: event.state.confidence_score },
                { label: "Fatigue", value: event.state.fatigue_score },
                { label: "Panic prob", value: event.state.panic_probability },
                { label: "Cog load", value: event.state.cognitive_load_score },
                { label: "Attention", value: event.state.attention_stability },
                { label: "Strategic", value: event.state.strategic_reliability },
                { label: "Drift", value: event.state.emotional_drift_score },
              ].map((metric) => (
                <div key={metric.label} className="border border-gray-800 rounded px-2 py-1">
                  <div className="text-gray-500 tracking-widest uppercase">{metric.label}</div>
                  <div className="text-gray-100 font-semibold text-sm">{Number(metric.value ?? 0).toFixed(1)}</div>
                </div>
              ))}
            </div>

            {event.explanation.grounding && event.explanation.grounding.length > 0 && (
              <div className="mt-4 border-t border-gray-800 pt-3">
                <div className="text-xs tracking-widest uppercase text-gray-500 flex items-center gap-2 mb-2">
                  <ScrollText size={12} />
                  Grounding passages
                </div>
                <ul className="space-y-1 text-xs text-gray-400">
                  {event.explanation.grounding.map((passage, idx2) => (
                    <li key={idx2}>
                      <span className="text-gray-200 font-semibold">{passage.document_title}</span>: {passage.snippet}
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </article>
        ))}
      </section>
    </main>
  );
}
