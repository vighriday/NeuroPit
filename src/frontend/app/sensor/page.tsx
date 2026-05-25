"use client";

/**
 * Live PPG biometric capture page.
 *
 * This page turns a phone into a low fidelity heart rate sensor by
 * sampling the red channel of the camera while the user holds their
 * fingertip over the lens. The signal is band passed and peak counted
 * on the client to extract beats per minute, then forwarded to the
 * gateway WebSocket where the backend wraps it as a biometrics event
 * and produces it onto the same Kafka topic the synthetic biometric
 * source uses.
 *
 * Cross platform behaviour
 * ------------------------
 * iOS Safari only exposes camera frames inside a user initiated event
 * handler, so the page guards every camera call behind an explicit
 * "Start" tap. Android Chrome is more permissive but the same guard
 * keeps the UX consistent. The video element uses `playsInline` and
 * `muted` to satisfy iOS autoplay rules. The torch (flashlight) is
 * requested through `track.applyConstraints({ torch: true })`. Devices
 * without torch capability just skip that step silently, which yields
 * a noisier BPM but still works in indoor lighting.
 *
 * Privacy
 * -------
 * The camera frame is processed locally and never transmitted. Only
 * the extracted BPM number plus a confidence band is sent to the
 * gateway. The video element is hidden once capture starts so the
 * raw stream is not displayed even on the local device.
 */

import { useEffect, useRef, useState } from "react";

type CaptureState =
  | "idle"
  | "requesting"
  | "running"
  | "denied"
  | "no-camera"
  | "error";

const SAMPLE_BUFFER_SIZE = 512; // ~17s at 30fps
const MIN_SAMPLES_FOR_BPM = 180; // ~6s at 30fps
const MIN_PLAUSIBLE_BPM = 40;
const MAX_PLAUSIBLE_BPM = 180; // 200 is too lenient; real adults rarely cross 180 at rest
const EMIT_INTERVAL_MS = 1000;
const BPM_SMOOTHING_WINDOW = 5; // median across last N estimates before emitting

function deriveWsUrl(apiBase: string | undefined): string {
  if (typeof window === "undefined") return "ws://localhost:8000/ws/sensor";
  const fallback = `${window.location.protocol === "https:" ? "wss" : "ws"}://${window.location.hostname}:8000/ws/sensor`;
  if (!apiBase) return fallback;
  try {
    const url = new URL(apiBase);
    const wsProto = url.protocol === "https:" ? "wss:" : "ws:";
    return `${wsProto}//${url.host}/ws/sensor`;
  } catch {
    return fallback;
  }
}

function detrend(samples: number[]): number[] {
  // Remove slow DC drift by subtracting a rolling mean over a one
  // second window. Keeps the pulse component intact while killing
  // ambient light shifts as the finger moves slightly.
  if (samples.length < 16) return samples.slice();
  const window = 30;
  const out: number[] = new Array(samples.length).fill(0);
  let sum = 0;
  for (let i = 0; i < samples.length; i += 1) {
    sum += samples[i];
    if (i >= window) sum -= samples[i - window];
    const w = Math.min(i + 1, window);
    out[i] = samples[i] - sum / w;
  }
  return out;
}

function smooth3(samples: number[]): number[] {
  if (samples.length < 3) return samples.slice();
  const out: number[] = new Array(samples.length);
  out[0] = samples[0];
  out[samples.length - 1] = samples[samples.length - 1];
  for (let i = 1; i < samples.length - 1; i += 1) {
    out[i] = (samples[i - 1] + samples[i] + samples[i + 1]) / 3;
  }
  return out;
}

function median(values: number[]): number {
  const sorted = values.slice().sort((a, b) => a - b);
  const mid = Math.floor(sorted.length / 2);
  if (sorted.length % 2 === 0) return (sorted[mid - 1] + sorted[mid]) / 2;
  return sorted[mid];
}

function estimateBpm(samples: number[], fps: number): { bpm: number; confidence: number } {
  if (samples.length < MIN_SAMPLES_FOR_BPM || fps < 8) {
    return { bpm: 0, confidence: 0 };
  }
  const filtered = smooth3(detrend(samples));
  if (filtered.length < 16) return { bpm: 0, confidence: 0 };

  const mean = filtered.reduce((acc, x) => acc + x, 0) / filtered.length;
  const std = Math.sqrt(
    filtered.reduce((acc, x) => acc + (x - mean) ** 2, 0) / filtered.length,
  );
  // Need a non flat signal. Pure DC means finger fell off the lens.
  if (std < 0.05) return { bpm: 0, confidence: 0 };

  // Mean plus half a stdev is a robust threshold for the systolic peak
  // of an inverted PPG trace.
  const threshold = mean + std * 0.5;

  // Refractory period: enforce minimum 0.33s between accepted peaks
  // (= 180 BPM ceiling) so a noisy double bounce on one beat does not
  // get counted twice. This is the single biggest source of the
  // earlier 200 BPM saturation.
  const minPeakGap = Math.round(fps * 0.33);

  const peakIndices: number[] = [];
  let lastPeak = -minPeakGap - 1;
  for (let i = 1; i < filtered.length - 1; i += 1) {
    if (
      filtered[i] > threshold &&
      filtered[i] > filtered[i - 1] &&
      filtered[i] >= filtered[i + 1] &&
      i - lastPeak >= minPeakGap
    ) {
      peakIndices.push(i);
      lastPeak = i;
    }
  }

  if (peakIndices.length < 3) return { bpm: 0, confidence: 0 };

  const deltas: number[] = [];
  for (let i = 1; i < peakIndices.length; i += 1) {
    deltas.push(peakIndices[i] - peakIndices[i - 1]);
  }
  const minDelta = fps * 0.33;
  const maxDelta = fps * 1.5;
  const usable = deltas.filter((d) => d >= minDelta && d <= maxDelta);
  if (usable.length < 2) return { bpm: 0, confidence: 0 };

  // Median delta beats the mean here because a single missed beat
  // doubles one delta and pulls the mean down by half a BPM range.
  const medianDelta = median(usable);
  const bpm = (60 * fps) / medianDelta;
  if (bpm < MIN_PLAUSIBLE_BPM || bpm > MAX_PLAUSIBLE_BPM) {
    return { bpm: 0, confidence: 0 };
  }

  // Confidence shrinks with delta variance and grows with sample
  // count. A long, regular trace earns a higher confidence than a
  // short noisy one.
  const dMean = usable.reduce((acc, x) => acc + x, 0) / usable.length;
  const dStd = Math.sqrt(
    usable.reduce((acc, x) => acc + (x - dMean) ** 2, 0) / usable.length,
  );
  const cv = dStd / dMean;
  const lengthBoost = Math.min(usable.length / 8, 1);
  const confidence = Math.max(0, Math.min(1, (1 - cv) * lengthBoost));
  return {
    bpm: Math.round(bpm * 10) / 10,
    confidence: Math.round(confidence * 100) / 100,
  };
}

export default function SensorPage() {
  const [state, setState] = useState<CaptureState>("idle");
  const [driverId, setDriverId] = useState("VER");
  const [bpm, setBpm] = useState<number | null>(null);
  const [confidence, setConfidence] = useState<number>(0);
  const [sentCount, setSentCount] = useState(0);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [fps, setFps] = useState(0);
  const [torchActive, setTorchActive] = useState(false);

  const videoRef = useRef<HTMLVideoElement | null>(null);
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const samplesRef = useRef<number[]>([]);
  const wsRef = useRef<WebSocket | null>(null);
  const rafRef = useRef<number | null>(null);
  const lastEmitRef = useRef<number>(0);
  const frameTimesRef = useRef<number[]>([]);
  const bpmHistoryRef = useRef<number[]>([]);
  const wsUrlRef = useRef<string>("");
  const wantWsRef = useRef<boolean>(false);

  // The WS URL depends on window.location and the
  // NEXT_PUBLIC_NEUROPIT_API_URL env var. Both can read differently on
  // the server vs the client, which would trigger a React hydration
  // mismatch. We compute the URL inside a client side effect after
  // hydration so the first SSR render and the first browser render
  // produce identical HTML.
  const [wsUrl, setWsUrl] = useState<string>("");
  useEffect(() => {
    setWsUrl(deriveWsUrl(process.env.NEXT_PUBLIC_NEUROPIT_API_URL));
  }, []);

  useEffect(() => {
    return () => stopCapture();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const stopCapture = () => {
    wantWsRef.current = false;
    if (rafRef.current !== null) {
      cancelAnimationFrame(rafRef.current);
      rafRef.current = null;
    }
    if (wsRef.current) {
      try {
        wsRef.current.close();
      } catch {
        // ignore
      }
      wsRef.current = null;
    }
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((t) => t.stop());
      streamRef.current = null;
    }
    samplesRef.current = [];
    frameTimesRef.current = [];
    bpmHistoryRef.current = [];
    setTorchActive(false);
    setBpm(null);
    setConfidence(0);
  };

  const openSocket = () => {
    const url = wsUrlRef.current;
    if (!url) return;
    try {
      const ws = new WebSocket(url);
      wsRef.current = ws;
      ws.onerror = () => {
        // Soft fail. The reconnect loop will retry. Surface a banner
        // only after we have been disconnected for a while.
        setErrorMessage(
          "Lost connection to NeuroPit gateway. Retrying...",
        );
      };
      ws.onclose = () => {
        wsRef.current = null;
        if (wantWsRef.current) {
          // Backoff a beat before retrying so we do not hammer a dead
          // gateway. One second is plenty given PPG emits at 1 Hz.
          setTimeout(() => {
            if (wantWsRef.current && wsRef.current === null) {
              openSocket();
            }
          }, 1000);
        }
      };
      ws.onopen = () => {
        setErrorMessage(null);
      };
    } catch (err) {
      setErrorMessage(`WebSocket failed to open: ${(err as Error)?.message ?? err}`);
    }
  };

  const startCapture = async () => {
    setErrorMessage(null);
    setState("requesting");
    if (typeof navigator === "undefined" || !navigator.mediaDevices?.getUserMedia) {
      setState("no-camera");
      setErrorMessage("Camera API not available on this browser");
      return;
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: {
          facingMode: { ideal: "environment" },
          width: { ideal: 640 },
          height: { ideal: 480 },
        },
        audio: false,
      });
      streamRef.current = stream;

      if (videoRef.current) {
        videoRef.current.srcObject = stream;
        videoRef.current.setAttribute("playsinline", "true");
        await videoRef.current.play();
      }

      // Best effort torch enable. Not supported on iOS Safari; safe to
      // ignore the rejection.
      const track = stream.getVideoTracks()[0];
      try {
        // The torch constraint is non standard but works on Chrome
        // Android. TypeScript does not know about it.
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        const advancedConstraints: any = [{ torch: true }];
        await track.applyConstraints({
          advanced: advancedConstraints,
        });
        setTorchActive(true);
      } catch {
        setTorchActive(false);
      }

      wsUrlRef.current = wsUrl;
      wantWsRef.current = true;
      openSocket();

      setState("running");
      lastEmitRef.current = performance.now();
      tick();
    } catch (err) {
      const message = (err as Error)?.message || "Unknown camera error";
      if (message.toLowerCase().includes("denied")) {
        setState("denied");
        setErrorMessage("Camera permission denied");
      } else {
        setState("error");
        setErrorMessage(message);
      }
    }
  };

  const tick = () => {
    rafRef.current = requestAnimationFrame(tick);
    const video = videoRef.current;
    const canvas = canvasRef.current;
    if (!video || !canvas || video.readyState < 2) {
      return;
    }

    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const size = 32;
    canvas.width = size;
    canvas.height = size;
    ctx.drawImage(video, 0, 0, size, size);
    let total = 0;
    try {
      const pixels = ctx.getImageData(0, 0, size, size).data;
      for (let i = 0; i < pixels.length; i += 4) {
        total += pixels[i]; // red channel only
      }
      total /= pixels.length / 4;
    } catch {
      return;
    }

    samplesRef.current.push(total);
    while (samplesRef.current.length > SAMPLE_BUFFER_SIZE) {
      samplesRef.current.shift();
    }

    const now = performance.now();
    frameTimesRef.current.push(now);
    while (frameTimesRef.current.length > 0 && now - frameTimesRef.current[0] > 1000) {
      frameTimesRef.current.shift();
    }
    setFps(frameTimesRef.current.length);

    if (now - lastEmitRef.current >= EMIT_INTERVAL_MS) {
      lastEmitRef.current = now;
      const estimated = estimateBpm(samplesRef.current, frameTimesRef.current.length);
      if (estimated.bpm > 0) {
        // Median across the last few estimates damps single bad
        // windows. The first emit only fires after we have at least
        // two estimates so the displayed number is never a one shot.
        bpmHistoryRef.current.push(estimated.bpm);
        while (bpmHistoryRef.current.length > BPM_SMOOTHING_WINDOW) {
          bpmHistoryRef.current.shift();
        }
        if (bpmHistoryRef.current.length >= 2) {
          const smoothed = Math.round(median(bpmHistoryRef.current) * 10) / 10;
          setBpm(smoothed);
          setConfidence(estimated.confidence);
          const ws = wsRef.current;
          if (ws && ws.readyState === WebSocket.OPEN) {
            ws.send(
              JSON.stringify({
                driver_id: driverId,
                bpm: smoothed,
                confidence: estimated.confidence,
                timestamp: new Date().toISOString(),
              }),
            );
            setSentCount((n) => n + 1);
          }
        }
      }
    }
  };

  return (
    <main className="min-h-screen bg-neutral-950 text-neutral-100 p-6 flex flex-col gap-6">
      <header className="flex flex-col gap-1">
        <h1 className="text-2xl font-bold">NeuroPit live biometric sensor</h1>
        <p className="text-sm text-neutral-400">
          Hold your fingertip over the rear camera lens (and flashlight if
          available). The page extracts a live heart rate from the camera and
          forwards it to the cognitive twin pipeline.
        </p>
      </header>

      <section className="flex flex-col gap-2 bg-neutral-900 rounded-xl p-4">
        <label className="text-sm">
          Driver to attach the live BPM to
          <select
            value={driverId}
            onChange={(e) => setDriverId(e.target.value)}
            className="ml-3 bg-neutral-800 rounded px-2 py-1"
            disabled={state === "running"}
          >
            <option value="VER">VER</option>
            <option value="HAM">HAM</option>
          </select>
        </label>
        <div className="flex gap-3 mt-2">
          {state !== "running" ? (
            <button
              onClick={startCapture}
              className="bg-amber-500 hover:bg-amber-400 text-neutral-900 font-semibold px-4 py-2 rounded"
            >
              Start sensor
            </button>
          ) : (
            <button
              onClick={stopCapture}
              className="bg-neutral-700 hover:bg-neutral-600 text-neutral-100 font-semibold px-4 py-2 rounded"
            >
              Stop sensor
            </button>
          )}
        </div>
        {errorMessage && (
          <p className="text-red-400 text-sm mt-2">{errorMessage}</p>
        )}
      </section>

      <section className="grid grid-cols-2 gap-4">
        <div className="bg-neutral-900 rounded-xl p-4">
          <div className="text-xs uppercase text-neutral-500">Live BPM</div>
          <div className="text-4xl font-bold mt-1">{bpm ? bpm.toFixed(1) : "—"}</div>
          <div className="text-xs text-neutral-500 mt-1">
            Confidence {(confidence * 100).toFixed(0)}%
          </div>
        </div>
        <div className="bg-neutral-900 rounded-xl p-4">
          <div className="text-xs uppercase text-neutral-500">Status</div>
          <div className="text-sm mt-1">{state}</div>
          <div className="text-xs text-neutral-500 mt-1">
            FPS {fps} · Torch {torchActive ? "on" : "off"} · Sent {sentCount}
          </div>
        </div>
      </section>

      <section className="bg-neutral-900 rounded-xl p-4 text-xs text-neutral-400">
        <p className="font-semibold text-neutral-300 mb-2">Tips for a stable signal</p>
        <ul className="list-disc list-inside space-y-1">
          <li>Hold your finger gently. Pressing too hard cuts off blood flow.</li>
          <li>Cover both the camera and the flashlight if your phone has one.</li>
          <li>Allow about ten seconds before the BPM number stabilises.</li>
          <li>The raw video is not transmitted. Only BPM and confidence are sent.</li>
        </ul>
        <p className="mt-3 text-neutral-500">Gateway socket: {wsUrl}</p>
      </section>

      {/* Hidden camera surface. The video is processed via canvas. */}
      <video ref={videoRef} muted playsInline className="hidden" />
      <canvas ref={canvasRef} className="hidden" />
    </main>
  );
}
