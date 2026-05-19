// Shared helpers for talking to the NeuroPit gateway from the dashboard.
// Every fetch sends the bearer token from local storage when present.
//
// `ensureDashboardToken` mints a race_strategist token automatically on first
// load so the dashboard can call protected endpoints without a manual login
// step. A real deployment swaps this for the team's identity provider.

const API_BASE = process.env.NEXT_PUBLIC_NEUROPIT_API_URL ?? "http://localhost:8000";
const DASHBOARD_ROLE = "race_strategist";

function authHeaders(): Record<string, string> {
  if (typeof window === "undefined") return {};
  const token = window.localStorage.getItem("neuropit_token");
  return token ? { Authorization: `Bearer ${token}` } : {};
}

export async function ensureDashboardToken(role: string = DASHBOARD_ROLE): Promise<string | null> {
  if (typeof window === "undefined") return null;
  const existing = window.localStorage.getItem("neuropit_token");
  if (existing) return existing;
  try {
    const response = await fetch(`${API_BASE}/auth/token`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ subject: "mission-control", role }),
    });
    if (!response.ok) return null;
    const body = (await response.json()) as { access_token?: string };
    if (!body.access_token) return null;
    window.localStorage.setItem("neuropit_token", body.access_token);
    return body.access_token;
  } catch {
    return null;
  }
}

export async function postJSON<TBody, TResponse>(path: string, body: TBody): Promise<TResponse> {
  const response = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...authHeaders() },
    body: JSON.stringify(body),
  });
  if (!response.ok) {
    const detail = await response.text();
    throw new Error(`POST ${path} failed: ${response.status} ${detail}`);
  }
  return (await response.json()) as TResponse;
}

export async function getJSON<TResponse>(path: string): Promise<TResponse> {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: authHeaders(),
  });
  if (!response.ok) {
    const detail = await response.text();
    throw new Error(`GET ${path} failed: ${response.status} ${detail}`);
  }
  return (await response.json()) as TResponse;
}

export type LapSummary = {
  driver_id: string;
  lap_number: number;
  actual_lap_time_s: number;
  average_stress: number;
  average_fatigue: number;
  panic_events: number;
};

export type GhostLapResult = {
  driver_id: string;
  lap_number: number;
  actual_lap_time_s: number;
  ghost_lap_time_s: number;
  lost_time_s: number;
  contributions: Record<string, number>;
};

export type CounterfactualResult = {
  scenario: string;
  baseline_lap_time_s: number;
  counterfactual_lap_time_s: number;
  lap_delta_s: number;
  rationale: string;
  adjustments: Record<string, number>;
};

export type PostRaceReport = {
  session_id: string | null;
  generated_on: string;
  driver_count: number;
  total_evaluations: number;
  drivers: Record<string, {
    summary: Record<string, number>;
    timeline: Array<{ timestamp: string; stress_score: number; confidence_score: number; fatigue_score: number; emotional_drift_score: number }>;
    ghost_lap: GhostLapResult | null;
    counterfactuals: CounterfactualResult[];
    explanations: Array<{ timestamp: string; text: string; source: string }>;
    evaluation_count: number;
  }>;
};
