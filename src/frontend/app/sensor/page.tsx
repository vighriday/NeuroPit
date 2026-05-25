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

import { useEffect, useMemo, useRef, useState } from "react";

type CaptureState =
  | "idle"
  | "requesting"
  | "running"
  | "denied"
  | "no-camera"
  | "error";

const SAMPLE_BUFFER_SIZE = 256; // ~8s at 30fps
const MIN_SAMPLES_FOR_BPM = 96;
const MIN_PLAUSIBLE_BPM = 40;
const MAX_PLAUSIBLE_BPM = 200;
const EMIT_INTERVAL_MS = 1000;

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

function bandpass(samples: number[]): number[] {
  // Cheap difference filter to remove DC drift, then a 3 tap moving
  // average to damp shot noise. Both steps are linear so they preserve
  // the dominant pulse frequency we are trying to extract.
  const detrended: number[] = [];
  for (let i = 1; i < samples.length; i += 1) {
    detrended.push(samples[i] - samples[i - 1]);
  }
  const smoothed: number[] = [];
  for (let i = 1; i < detrended.length - 1; i += 1) {
    smoothed.push((detrended[i - 1] + detrended[i] + detrended[i + 1]) / 3);
  }
  return smoothed;
}

function estimateBpm(samples: number[], fps: number): { bpm: number; confidence: number } {
  if (samples.length < MIN_SAMPLES_FOR_BPM || fps < 5) {
    return { bpm: 0, confidence: 0 };
  }
  const filtered = bandpass(samples);
  if (filtered.length < 4) return { bpm: 0, confidence: 0 };

  // Mean threshold peak counting. A "peak" is a sample above the
  // running mean that is also a local maximum versus its neighbours.
  const mean = filtered.reduce((acc, x) => acc + x, 0) / filtered.length;
  const std = Math.sqrt(
    filtered.reduce((acc, x) => acc + (x - mean) ** 2, 0) / filtered.length,
  );
  const threshold = mean + std * 0.25;

  const peakIndices: number[] = [];
  for (let i = 1; i < filtered.length - 1; i += 1) {
    if (
      filtered[i] > threshold &&
      filtered[i] > filtered[i - 1] &&
      filtered[i] >= filtered[i + 1]
    ) {
      peakIndices.push(i);
    }
  }

  if (peakIndices.length < 2) return { bpm: 0, confidence: 0 };

  const deltas: number[] = [];
  for (let i = 1; i < peakIndices.length; i += 1) {
    deltas.push(peakIndices[i] - peakIndices[i - 1]);
  }
  // Discard implausible deltas (sub 0.3s or above 1.5s).
  const minDelta = fps * 0.3;
  const maxDelta = fps * 1.5;
  const usable = deltas.filter((d) => d >= minDelta && d <= maxDelta);
  if (usable.length < 1) return { bpm: 0, confidence: 0 };

  const avgDelta = usable.reduce((acc, x) => acc + x, 0) / usable.length;
  const bpm = (60 * fps) / avgDelta;
  if (bpm < MIN_PLAUSIBLE_BPM || bpm > MAX_PLAUSIBLE_BPM) {
    return { bpm: 0, confidence: 0 };
  }

  // Confidence shrinks when delta variance is high.
  const deltaMean = avgDelta;
  const deltaStd = Math.sqrt(
    usable.reduce((acc, x) => acc + (x - deltaMean) ** 2, 0) / usable.length,
  );
  const cv = deltaStd / deltaMean;
  const confidence = Math.max(0, Math.min(1, 1 - cv));
  return { bpm: Math.round(bpm * 10) / 10, confidence: Math.round(confidence * 100) / 100 };
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

  const wsUrl = useMemo(
    () => deriveWsUrl(process.env.NEXT_PUBLIC_NEUROPIT_API_URL),
    [],
  );

  useEffect(() => {
    return () => stopCapture();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const stopCapture = () => {
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
    setTorchActive(false);
    setBpm(null);
    setConfidence(0);
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

      const ws = new WebSocket(wsUrl);
      wsRef.current = ws;
      ws.onerror = () => {
        setErrorMessage("Could not connect to NeuroPit gateway. Is it running?");
        setState("error");
        stopCapture();
      };

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
        setBpm(estimated.bpm);
        setConfidence(estimated.confidence);
        const ws = wsRef.current;
        if (ws && ws.readyState === WebSocket.OPEN) {
          ws.send(
            JSON.stringify({
              driver_id: driverId,
              bpm: estimated.bpm,
              confidence: estimated.confidence,
              timestamp: new Date().toISOString(),
            }),
          );
          setSentCount((n) => n + 1);
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
