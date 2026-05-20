// Shared helpers for talking to the NeuroPit gateway from the dashboard.
// Every fetch sends the bearer token from local storage when present.
//
// The token is minted on first load and proactively refreshed five
// minutes before it expires. Any request that still returns 401
// because the local token has been wiped or the server JWT secret
// rotated is retried once after re-minting. This is what fixes the
// `Signature has expired` errors a long-lived Mission Control tab
// used to surface.

const API_BASE = process.env.NEXT_PUBLIC_NEUROPIT_API_URL ?? "http://localhost:8000";
const DASHBOARD_ROLE = "race_strategist";
const TOKEN_KEY = "neuropit_token";
const TOKEN_EXPIRY_KEY = "neuropit_token_expires_at";
const REFRESH_LEAD_MS = 5 * 60 * 1000; // refresh five minutes before expiry

type TokenResponse = {
  access_token: string;
  expires_in?: number;
  expires_at?: string;
};

function persistToken(token: string, expiresAt: number): void {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(TOKEN_KEY, token);
  window.localStorage.setItem(TOKEN_EXPIRY_KEY, String(expiresAt));
}

function readStoredToken(): { token: string; expiresAt: number } | null {
  if (typeof window === "undefined") return null;
  const token = window.localStorage.getItem(TOKEN_KEY);
  if (!token) return null;
  const expiresAtRaw = window.localStorage.getItem(TOKEN_EXPIRY_KEY);
  const expiresAt = expiresAtRaw ? Number(expiresAtRaw) : 0;
  return { token, expiresAt };
}

function clearStoredToken(): void {
  if (typeof window === "undefined") return;
  window.localStorage.removeItem(TOKEN_KEY);
  window.localStorage.removeItem(TOKEN_EXPIRY_KEY);
}

let inFlightMint: Promise<string | null> | null = null;

async function mintToken(role: string): Promise<string | null> {
  if (inFlightMint) return inFlightMint;
  inFlightMint = (async () => {
    try {
      const response = await fetch(`${API_BASE}/auth/token`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ subject: "mission-control", role }),
      });
      if (!response.ok) return null;
      const body = (await response.json()) as TokenResponse;
      if (!body.access_token) return null;
      const expiresAt = body.expires_at
        ? Date.parse(body.expires_at)
        : Date.now() + (body.expires_in ?? 7200) * 1000;
      persistToken(body.access_token, expiresAt);
      return body.access_token;
    } catch {
      return null;
    } finally {
      inFlightMint = null;
    }
  })();
  return inFlightMint;
}

export async function ensureDashboardToken(role: string = DASHBOARD_ROLE): Promise<string | null> {
  if (typeof window === "undefined") return null;
  const stored = readStoredToken();
  if (stored && stored.expiresAt > Date.now() + REFRESH_LEAD_MS) {
    return stored.token;
  }
  // Token missing, expired, or near-expiring: mint a fresh one.
  clearStoredToken();
  return mintToken(role);
}

function authHeaders(): Record<string, string> {
  if (typeof window === "undefined") return {};
  const token = window.localStorage.getItem(TOKEN_KEY);
  return token ? { Authorization: `Bearer ${token}` } : {};
}

async function fetchWithAuthRetry(input: RequestInfo, init: RequestInit): Promise<Response> {
  await ensureDashboardToken();
  let response = await fetch(input, {
    ...init,
    headers: { ...(init.headers ?? {}), ...authHeaders() },
  });
  if (response.status === 401) {
    clearStoredToken();
    const refreshed = await ensureDashboardToken();
    if (refreshed) {
      response = await fetch(input, {
        ...init,
        headers: { ...(init.headers ?? {}), ...authHeaders() },
      });
    }
  }
  return response;
}

export async function postJSON<TBody, TResponse>(path: string, body: TBody): Promise<TResponse> {
  const response = await fetchWithAuthRetry(`${API_BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!response.ok) {
    const detail = await response.text();
    throw new Error(`POST ${path} failed: ${response.status} ${detail}`);
  }
  return (await response.json()) as TResponse;
}

export async function getJSON<TResponse>(path: string): Promise<TResponse> {
  const response = await fetchWithAuthRetry(`${API_BASE}${path}`, {
    method: "GET",
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
