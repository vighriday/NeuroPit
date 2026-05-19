# NeuroPit Architecture

This is the working architecture document for NeuroPit V1. If you are reading this for the first time, start here. If you are about to add a new layer, update this file before you write a line of code.

NeuroPit is a real time Cognitive Twin Operating System for motorsport. The car has been measured for decades. The mind inside the car has not. NeuroPit treats the driver as a probabilistic cognitive entity that can be inferred from the telemetry the car is already producing, and it does that under explainable AI principles a strategist can defend in a stewards meeting. Telemetry is infrastructure. Cognition is the product.

## Category and moat

The category is Human Machine Cognitive Intelligence for Motorsport. The unit of value is the Cognitive Twin. The moat is real time probabilistic cognition inference from racing telemetry, paired with IBM Granite explainable cognitive reasoning grounded in the motorsport cognition ontology.

NeuroPit is deliberately not framed as a telemetry analytics dashboard, a strategy copilot, or a generic AI racing assistant. Other systems ask what is happening to the car. NeuroPit asks what is happening to the human nervous system operating the car. The dashboard, the REST endpoints, and the WebSocket are surfaces over the twin. They are not the product.

## What we are building, plainly

A behavioural telemetry intelligence pipeline that derives per driver micro signals from real racing telemetry, fuses those signals with telemetry conditioned synthetic biometrics, computes the full nine score Cognitive Twin (stress, confidence, fatigue, cognitive load, attention stability, strategic reliability, panic probability, emotional drift, tunnel vision), runs the Emotional State Engine, the Predictive Failure Engine, the Ghost Lap AI, the Counterfactual Simulator, and the Strategy Parliament on top of that twin, asks IBM Granite to deliver explainable cognitive reasoning grounded in the motorsport cognition ontology, and renders everything on a Mission Control surface with dedicated Ghost Lap, Counterfactual, and Explainability views.

The seven things that differentiate NeuroPit are the Cognitive Twin, the Emotional State Engine, the Persona Drift state machine, the IBM Granite explainable cognitive reasoning layer grounded by Docling and Qdrant, the trust and uncertainty band that ships with every emission, the Strategy Parliament, and the audit log that captures every reasoning step. Everything else is plumbing that exists to make those seven things possible.

## Principles we will not bend on

1. The pipeline is event driven from end to end. Nothing materialises state outside the stream.
2. The car is measured. The driver is inferred. We do not pretend otherwise.
3. Every cognitive output ships with a confidence band and a written explanation. No exceptions.
4. Local first. The whole stack has to boot on a developer laptop with Docker and free tier cloud accounts.
5. Apache 2.0 from day one. Every third party component is attributed in the NOTICE file.
6. Interpretable signal engineering wins over hastily trained models for V1, and we say so out loud.
7. Surfaces are not the product. The Cognitive Twin is the product.

## Logical layers

We organise the runtime into five tiers. Each tier owns a small number of layers. Each layer owns a small number of files.

Tier A is acquisition. It contains the data acquisition layer that pulls historical telemetry from OpenF1 and FastF1, and the event streaming layer that fans that telemetry out through Redpanda.

Tier B is behavioural telemetry intelligence. It contains the telemetry processing layer, the behavioural feature engineering layer that turns raw frames into per driver micro signals, and the biometric synthesis layer that produces telemetry conditioned heart rate and HRV estimates.

Tier C is cognitive intelligence. This is the layer the rest of the system exists to serve. It contains the Probabilistic Cognitive Inference Engine, the Emotional State Engine, the Persona Drift state machine, the Predictive Failure Engine, and the Counterfactual Simulation Engine.

Tier D is explainable cognitive reasoning and trust. It contains the IBM Granite reasoning layer, the trust and uncertainty layer that attaches confidence bands to every cognitive output, the multi agent cognitive strategy layer orchestrated through Langflow, and the motorsport cognition ontology layer that uses Docling to compile literature into a Qdrant collection.

Tier E is the surface. It contains the Mission Control visualisation layer built in Next.js, the audit layer that writes every cognitive decision to disk, the post race cognitive intelligence reporting layer, and the historical cognition retrieval layer that lets the team query past sessions through vector search.

Tier F is prescriptive cognition. The Cognitive Twin is diagnostic. The Prescriptive Engine in `src/backend/prescription/` turns each evaluation into a typed pit wall action, a quantified Optimality Gap against the driver's own performance envelope, a projected counterfactual twin five seconds out, and a Granite explained rationale. The What If Replay engine in `src/backend/whatif/` reuses the immutable audit log: it takes any past window for a driver, applies typed mutations to the original inputs, and re runs the same deterministic cognitive maths so the strategist can answer "what would have happened if we had calmed the radio earlier" without ever leaving real session data. Both pieces ride the same audit, the same Granite path, and the same trust band as the diagnostic tier. They are not bolt ons. They are the operational tier on top of the twin.

## How a frame travels through the system

A telemetry frame begins its life inside `src/backend/ingestion/streamer.py`. The streamer loads a real Formula session from FastF1, merges the car physics with positional data, and replays the session frame by frame at a configurable speed. Each frame is wrapped in a `TelemetryFrame` model and published to the `incoming-telemetry-raw` topic on Redpanda.

Two things happen in parallel from there. The InfluxDB writer in `src/backend/integration/influx_writer.py` persists the raw frame to time series storage so the replay tool can re publish it later. The behavioural feature extractor in `src/backend/inference/feature_extractor.py` adds the frame to a per driver sliding window and emits a behavioural feature vector to the `telemetry-features` topic every few frames.

The biometric synthesiser in `src/backend/inference/biometric_synthesizer.py` consumes the feature stream and emits telemetry conditioned heart rate, HRV, and respiration estimates to the `biometrics-enriched` topic. The Probabilistic Cognitive Inference Engine in `src/backend/inference/cognitive_engine.py` joins the feature and biometric streams per driver, computes the full nine score Cognitive Twin, and writes the result to the `cognitive-state-inference` topic along with a persistence row in InfluxDB.

The cognitive event is then picked up by the IBM Granite explainable cognitive reasoning worker. The worker queries the motorsport cognition ontology through the Qdrant retriever, threads the grounding passages into Granite, generates a short reasoning paragraph, and pushes it to the `explanation-events` topic. The Emotional State Engine subscribes in parallel and publishes the nine emotion distribution to `emotional-events`. The cognitive gateway subscribes to all three topics and fans them out over WebSocket to the Mission Control surface.

The surface never displays a number without its explanation and its confidence band. That is a hard rule.

## Topic taxonomy

Topic names, partition counts, payload shapes, and ownership rules live in `docs/EVENT_TAXONOMY.md`. If the topic list in `src/backend/init_infrastructure.py` disagrees with the taxonomy document, the taxonomy document wins and the code is wrong.

## Cognitive methodology

The exact weights and reasoning behind every cognitive score live in `docs/COGNITIVE_METHODOLOGY.md`. Read that before adjusting the engine.

## Latency targets

The PRD asks for cognitive alerts under three hundred milliseconds. The local stack is built to meet that target. Ingestion to Kafka publish runs at around twenty milliseconds per frame. Behavioural feature window processing runs at around sixty milliseconds. Biometric synthesis adds another twenty. Cognitive inference adds forty. The IBM Granite stub adds thirty. The surface re renders inside thirty. The IBM Granite cloud call is best effort, around two hundred and fifty milliseconds when it is up, and the stub takes over automatically when it is not.

## Failure handling

Missing telemetry fields drop the confidence band one step instead of guessing. A Kafka outage causes the producer to buffer and flips the surface banner to amber. InfluxDB downtime is logged and skipped. IBM Granite cloud outage is invisible because the local stub fills in. Biometric stalls trigger a feature only fallback in the Cognitive Inference Engine. None of these conditions are allowed to silently lower the displayed score without lowering the displayed confidence first.

## Reproducibility

The whole system should boot from one command. `docker compose up` brings the infrastructure online. `python -m src.backend.init_infrastructure` creates topics and Qdrant collections. `python -m src.backend.ingestion.streamer` plays back the chosen session. Pinned dependencies live in `src/backend/requirements.txt`. Replay seeds live in `.env.example`. The cognitive weights are versioned in `docs/COGNITIVE_METHODOLOGY.md` and stamped onto every audit log row so historical replays still make sense after the constants move.

## Where the roadmap goes from here

The roadmap deepens the Cognitive Twin rather than spreading the surface. Phase 4 already lives in this release through the Predictive Failure Engine, the Ghost Lap AI, and the Counterfactual Simulation Engine. Phase 5 already lives here through the Strategy Parliament and the Docling backed Qdrant ontology. Phase 6 already ships through the post race cognitive intelligence reports. Phase 7 already ships through the JWT cognitive gateway, the Fernet biometric encryption, and the audit log. The next phases swap the deterministic cognitive functions for learned behavioral models on the same feature inputs without changing the surface contract.

---

NeuroPit · Built by Hriday Vig · IBM AI Builders Challenge 2026 powered by IBM SkillsBuild.
