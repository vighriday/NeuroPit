# Event Taxonomy

This is the working list of every Kafka topic NeuroPit uses, what flows through it, and who reads it. It maps directly to Section 39 of the PRD and to the topic names that already appear inside `src/backend/init_infrastructure.py`.

If you add a new topic anywhere in the code, add it here first. If a payload changes shape, bump the version on the schema example. The dashboard, the API gateway, and the cognitive engine all assume the names below.

## Conventions

Every topic uses the driver_id as the partition key when one is available. Global events fall back to the literal string `global`. Payloads are UTF 8 JSON. Timestamps are always ISO 8601 in UTC. We keep the schema flat where we can so that downstream consumers do not need to walk deeply nested objects in the hot path.

We deliberately keep the topic count small in V1. Each topic carries one well defined intent.

## Live topics in V1

### cognitive-prescriptions
Carries one prescription envelope per cognitive evaluation. Produced by the prescription worker after joining the cognitive state with the latest predictive failure forecast for the same driver. The Mission Control surface subscribes through the gateway. Every prescription is also appended to the audit log so the call is reproducible.

Example payload:

```json
{
  "kind": "prescription",
  "driver_id": "VER",
  "timestamp": "2026-05-19T12:00:00.100Z",
  "prescription": {
    "driver_id": "VER",
    "timestamp": "2026-05-19T12:00:00.100Z",
    "optimality": {
      "cognitive_efficiency": 32.6,
      "performance_lost_s": 1.01,
      "weighted_distance": 2.24,
      "centroid": {"stress_score": 62.0, "confidence_score": 78.0, "fatigue_score": 44.0, "cognitive_load_score": 66.0, "panic_probability": 18.0},
      "deltas": {"stress_score": 16.0, "confidence_score": -37.0, "fatigue_score": 19.0, "cognitive_load_score": 5.0, "panic_probability": 6.0},
      "contributions": {"confidence_score": 0.87, "fatigue_score": 0.07, "stress_score": 0.05, "panic_probability": 0.01, "cognitive_load_score": 0.004},
      "sample_count": 0,
      "persona_seed": "Aggressive"
    },
    "primary": {
      "code": "box_now",
      "label": "Pit window: immediate",
      "surface": "strategy",
      "summary": "Panic probability and tunnel vision risk a session ending incident. Pit now.",
      "score": 62.0,
      "triggers": ["forecast_panic_above_55"],
      "blocked_by": [],
      "projected_twin": {"stress_score": 58.0, "panic_probability": 0.0, "fatigue_score": 53.0},
      "projected_efficiency": 41.2
    },
    "alternatives": [],
    "rationale": "Persona Aggressive on a moderate confidence band. Cognitive efficiency 33/100 with 1.01s left on the table. Biggest envelope drift on confidence. Prescribed action: Pit window: immediate.",
    "forecast_used": true
  }
}
```

Producers: `PrescriptionWorker`.
Consumers: gateway websocket bridge, audit log, downstream operator surfaces.

### incoming-telemetry-raw
Every frame that comes off the playback streamer lands here first. This is the firehose. Average rate is around ten messages per driver per second, which lines up with FastF1 telemetry density.

Example payload:

```json
{
  "timestamp": "2026-05-19T12:00:00.100Z",
  "driver_id": "VER",
  "session_id": "2021_AbuDhabi",
  "speed": 312.4,
  "rpm": 11650,
  "gear": 7,
  "throttle": 98.2,
  "brake": 0.0,
  "steering_angle": 4.1,
  "drs": 12,
  "x": 1024.0,
  "y": -512.0,
  "z": 0.0,
  "status": "OnTrack"
}
```

Producers: `HistoricalRaceStreamer`.
Consumers: `FeatureExtractor`, `InfluxDBWriter`.

### telemetry-features
Behavioural features derived from a sliding window of frames. One message per processing step per driver, not per raw frame, so this topic is roughly five times quieter than the raw topic.

Example payload:

```json
{
  "timestamp": "2026-05-19T12:00:00.500Z",
  "driver_id": "VER",
  "session_id": "2021_AbuDhabi",
  "features": {
    "steering_instability": 12.4,
    "braking_hesitation": 850.0,
    "throttle_commitment": 62.3,
    "panic_oscillation": 8.1
  }
}
```

Producers: `FeatureExtractor`, `FeaturePipeline`.
Consumers: `BiometricSynthesizer`, `CognitiveInferenceEngine`, `InfluxDBWriter`.

### biometrics-enriched
Synthetic heart rate, HRV, and respiration estimates driven from the feature stream. These are always tagged as synthetic when they reach the audit log so nobody confuses them with real wearable data.

Example payload:

```json
{
  "timestamp": "2026-05-19T12:00:00.500Z",
  "driver_id": "VER",
  "synthetic_hr": 168.4,
  "synthetic_hrv": 32.7,
  "respiration_rate": 25.6
}
```

Producers: `BiometricSynthesizer`.
Consumers: `CognitiveInferenceEngine`.

### cognitive-state-inference
The output of the Probabilistic Cognitive Inference Engine. This is the topic the dashboard cares about most. One message per driver per processing step.

Example payload:

```json
{
  "timestamp": "2026-05-19T12:00:00.500Z",
  "driver_id": "VER",
  "stress_score": 78.4,
  "confidence_score": 64.1,
  "fatigue_score": 22.7,
  "tunnel_vision_prob": 0.0,
  "persona_state": "Aggressive",
  "confidence_band": "moderate",
  "explainability_pending": true
}
```

Producers: `CognitiveInferenceEngine`.
Consumers: Granite explanation worker, FastAPI gateway, InfluxDB writer.

### incoming-race-events
Catch all for non telemetry race context such as lap completions, pit calls, flag changes, and weather updates. Lower volume, higher signal.

Example payload:

```json
{
  "timestamp": "2026-05-19T12:00:01.000Z",
  "event_type": "lap_complete",
  "driver_id": "VER",
  "details": { "lap_number": 14, "lap_time_ms": 89230 }
}
```

### anomaly-events
Reserved for the Predictive Failure Engine that lands in Phase 4. Carries an anomaly type, a confidence number, and a short reason string.

### stress-events
Threshold breach broadcasts pulled out of the cognitive stream. Used by the dashboard for amber and red alerts and by the audit log for post race review.

### overtake-events
Driver action level events that need to be correlated with cognitive state. Useful for the Ghost Lap analysis later.

### emotional-events
Emotional state transitions. We keep these separate from the cognitive scores because state transitions are discrete and easier to query when they live in their own topic.

### weather-events
Track surface and weather conditions. We seed these from the FastF1 weather frames during playback so the cognitive engine can factor in rain and ambient temperature.

### strategy-events
Reserved for the Strategy Parliament agents. Carries proposals, votes, and the final consensus that Granite synthesises.

### simulation-events
Reserved for the Counterfactual Simulation Engine. Carries scenario inputs and outputs so they can be replayed later from the audit log.

## Partition strategy

For V1 every topic uses three partitions and replication factor one because the entire stack runs on a single Redpanda broker. When we move to a multi broker setup we raise replication factor to three for the topics in the critical cognitive path, namely `incoming-telemetry-raw`, `telemetry-features`, `biometrics-enriched`, and `cognitive-state-inference`. The rest stay at one until they start carrying production traffic.

## Retention strategy

Default retention is twelve hours which is enough for a full race weekend rehearsal on a developer laptop. The audit log on disk is the long term store, not Kafka.

## Adding a new topic

1. Add the topic to the `required_topics` list in `src/backend/init_infrastructure.py`.
2. Add an entry to this document with an example payload and the producer and consumer list.
3. Update the affected pipeline modules.
4. Note the change in `CHANGELOG.md` under the relevant version.

---

NeuroPit · Built by Hriday Vig · IBM AI Builders Challenge 2026 powered by IBM SkillsBuild.
