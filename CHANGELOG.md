# Changelog

All notable changes to NeuroPit live here. We follow [Keep a Changelog](https://keepachangelog.com/en/1.0.0/) and the project version moves under [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

The intention is that someone landing on the repository for the first time can scan this file and understand what shipped when, what is in progress, and where to look for the detail.

## [Unreleased]

### Positioning lockdown

- New `docs/POSITIONING.md` as the canonical narrative reference for every surface, slide, and demo line. Lists the language to use and the language to avoid. Mandatory reading before changing any user facing copy.
- README rewritten to lead with the thesis ("telemetry can probabilistically reveal the hidden cognitive and emotional state of the driver"), the category (Human Machine Cognitive Intelligence for Motorsport), and the abstraction shift ("other systems ask what is happening to the car. NeuroPit asks what is happening to the human nervous system operating the car"). Explicit "what NeuroPit is not" section added.
- `docs/ARCHITECTURE.md` reframed around the Cognitive Twin as the unit of value and the moat. Surfaces are described as surfaces over the twin, not as the product. A new seventh principle says so out loud.
- Mission Control hero, the Ghost Lap page, the Counterfactual page, and the Explainability page now lead with cognitive language (Cognitive Twin Operating System, cognitive normalised lap, cognitive aware what if, explainable cognitive reasoning). The browser tab title is "NeuroPit Cognitive Twin OS".
- FastAPI gateway renamed to "NeuroPit Cognitive Gateway". Gateway description, the Cognitive Inference Engine docstring, and the IBM Granite client docstring all use the mandated vocabulary. Banned phrases such as "telemetry platform", "telemetry insights", "AI assistant", and "strategy copilot" are removed from all surfaces.
- PRD compliance audit sections 1 to 11 and 44 to 48 refreshed to point at the new positioning document.

## [0.2.0] - 2026-05-19

This release closes every PRD gap that was open after 0.1.0. NeuroPit is now positioned, in code and in documentation, as a real time Cognitive Twin Operating System for motorsport rather than a telemetry analytics platform. Telemetry is the input. The Cognitive Twin is the product.

### Cognitive completeness

- Cognitive Inference Engine emits the full nine score twin described in PRD section fifteen: stress, confidence, fatigue, cognitive load, attention stability, strategic reliability, panic probability, emotional drift, tunnel vision. Persona state and confidence band travel alongside on every emission.
- New cognitive weights for cognitive load, attention stability, strategic reliability, panic probability, and emotional drift are versioned alongside the existing constants in `src/backend/common/weights.py` and stamped onto every audit log row.
- `docs/COGNITIVE_METHODOLOGY.md` still describes the underlying equations. The audit log captures the active weights so historical replays remain reproducible after the constants move.

### Emotional state engine

- New `src/backend/inference/emotional_state.py` that emits a normalised probability distribution across confidence, fear, panic, frustration, aggression, recovery, overconfidence, hesitation, and caution.
- New `src/backend/inference/emotional_state_worker.py` that joins the cognitive, feature, and biometric streams and publishes to the `emotional-events` topic.
- New `/emotional` FastAPI endpoint that returns the same distribution for any cognitive state payload.

### Telemetry intelligence

- `line_consistency` and `reaction_smoothness` features added to `src/backend/feature_engineering/signal_processor.py` so the PRD section fourteen feature set is now complete.

### Knowledge grounding

- New `src/backend/knowledge/retriever.py` that pulls the top three motorsport ontology passages from Qdrant for a given query and degrades cleanly when Qdrant or the optional embedding library are not available.
- IBM Granite explanations are now grounded against the retrieved passages on both the cloud and the stub path. The grounding entries travel inside the explanation payload so the dashboard can render the source documents alongside the reasoning paragraph.

### Post race intelligence

- New `src/backend/reporting/post_race.py` that assembles the per driver cognitive summary, confidence reconstruction timeline, Ghost Lap result, full counterfactual sweep, and Granite explanation tail from the audit log.
- New `/reports/{session_id}` FastAPI endpoint backed by that builder. The literal `all` segment returns the cross session report when only one session has been recorded so far, which matches the demo flow.

### Security and privacy enforcement

- New `src/backend/security/auth.py` dependency that enforces bearer tokens on every protected gateway route. The Mission Control surface continues to work in development because the dependency falls back to an anonymous Neuro Analyst claim set when the JWT secret is left at its dev default.
- New `/auth/token` FastAPI endpoint that mints a JWT for a known role so the dashboard can switch personas at runtime.
- Biometric synthesiser now encrypts the heart rate, HRV, and respiration payload through the project Fernet helper before publishing. The plaintext numeric fields still flow so downstream consumers do not change.

### Reliability and replay

- New `src/backend/integration/influx_replay.py` that reads historical raw telemetry from InfluxDB and republishes it onto the raw topic so a broker outage does not cost the demo any data.

### Shared domain models

- `src/backend/ingestion/models.py` now contains `Race`, `Session`, `CognitiveState`, `EmotionalState`, `Simulation`, `StrategyRecommendation`, and `ConfidenceReport` in addition to the existing telemetry models. Every API schema in `src/backend/api/schemas.py` mirrors the domain models so the dashboard sees the same shapes the workers emit.

### Mission Control surface

- New `/ghost-lap`, `/counterfactual`, and `/explainability` pages under `src/frontend/app/`. Each one talks to the FastAPI gateway and renders the cognitive intelligence behind the corresponding REST endpoint.
- Persistent navigation in `src/frontend/components/Nav.tsx`. Shared API helpers in `src/frontend/lib/api.ts`.
- Mission Control tile grid extended from three tiles to eight to surface the new cognitive load, attention stability, strategic reliability, panic probability, and emotional drift scores. The trajectory chart now plots panic probability alongside stress, confidence, and fatigue, and the right hand panel renders the live emotional distribution.

### Tests

- One hundred and two unit tests in total, all green, with new coverage for the cognitive engine end to end, the emotional state engine, the Qdrant retriever, the post race report builder, the biometric encryption pipeline, the security helpers, the gateway scope enforcement, and the shared domain models.

### Positioning

- README, ARCHITECTURE, and PRD compliance audit rewritten to consistently use the Cognitive Twin Operating System framing. Telemetry is described as infrastructure. Cognition is described as the product. The moat is real time probabilistic cognition inference from racing telemetry plus IBM Granite explainability grounded against the motorsport ontology.

## [0.1.0] - 2026-05-19

This is the first end to end release of NeuroPit. The system can ingest a real Formula session, infer the driver's cognitive state in near real time, explain that state through IBM Granite or a local stub, project failure probabilities across four horizons, simulate counterfactual race scenarios, and surface every output on a Mission Control dashboard.

### Documentation

- `docs/ARCHITECTURE.md` written in plain language so a new contributor can read the whole system in one sitting.
- `docs/EVENT_TAXONOMY.md` describing every Kafka topic, payload, producer, and consumer.
- `docs/COGNITIVE_METHODOLOGY.md` documenting the weights and reasoning behind the Probabilistic Cognitive Inference Engine.
- `docs/DEMO_RUNBOOK.md` capturing the exact commands and talking points for the live demo.
- `tests/README.md` and `data/knowledge_sources/README.md` describing the test layout and the knowledge ingestion workflow.

### Hardening and shared infrastructure

- Every backend module now reads its broker, database, and replay configuration through `src.backend.config.get_settings` instead of hardcoded localhost strings.
- New `src/backend/common` package containing a versioned cognitive weight registry, the trust and uncertainty layer, the persona drift state machine, and a thread safe JSON Lines audit log writer.
- Cognitive Inference Engine rewritten to use the shared weights, attach a confidence band to every emission, stamp the active weight version onto each record, and append a full audit trail per evaluation.
- Bootstrap script now reads broker, Qdrant, and replay settings from configuration and adds the `explanation-events` topic that the Granite explainability worker subscribes to.

### Testing

- New `tests/unit` suite covering the signal processor, the cognitive weight registry, the persona drift rules, the trust and uncertainty layer, the audit log writer, the cognitive equations, the predictive failure engine, the Ghost Lap AI, the counterfactual simulator, the Granite client, the strategy parliament, the Docling compiler, the FastAPI gateway, and the security helpers.
- The old broker dependent scripts `src/backend/test_phase_2.py` and `src/backend/test_phase_3.py` have moved into `tests/integration` as proper pytest modules marked with the `integration` marker so the default test run no longer requires Redpanda.
- Top level `Makefile` exposing `make test`, `make integration`, `make infra-up`, `make bootstrap`, `make stream`, `make backend`, `make gateway`, and `make frontend` so a new contributor only needs one entry point.

### Forecasting and simulation

- New `src/backend/prediction/failure_engine.py` projecting crash, lock up, spin, failed overtake, concentration collapse, and strategic non compliance probabilities across the five second, one lap, three lap, and full race horizons listed in the PRD.
- New `src/backend/simulation/ghost_lap.py` reconstructing a cognitive normalised lap from per lap stress, fatigue, and panic summaries and exposing a clear per cause lost time breakdown.
- New `src/backend/simulation/counterfactual.py` implementing the five canonical scenarios from PRD section twenty, each carrying a rationale string and the explicit adjustments applied to the baseline lap.

### IBM integration and reasoning

- New `src/backend/reasoning/granite_client.py` that talks to IBM watsonx.ai when credentials are configured and silently falls back to a local templated stub when they are not, so the dashboard always has an explanation to show.
- New `src/backend/reasoning/explainability_worker.py` subscribing to the cognitive state topic and publishing a Granite explanation per evaluation to the explanation events topic.
- New `src/backend/strategy/parliament.py` implementing the seven specialised strategy agents from the PRD with a tally based consensus and a transcript that Granite can synthesise.
- New `src/backend/knowledge/docling_compiler.py` for ingesting PDFs, HTML, Markdown, and plain text from `data/knowledge_sources` into the Qdrant motorsport ontology, with a deterministic hashing fallback when sentence transformers are not installed.
- Reference Langflow definition committed under `orchestration/langflow/neuropit_strategy_flow.json` for visual review of the cognitive strategy pipeline.
- Seed knowledge document under `data/knowledge_sources/neuropit_methodology_seed.md` so the compiler has something to ingest immediately after a fresh checkout.

### Gateway and dashboard

- New FastAPI gateway under `src/backend/api/` exposing healthcheck, ghost lap, counterfactual, parliament, and a single WebSocket fanout that bridges the Kafka cognitive and explanation topics to Mission Control.
- Mission Control dashboard rewritten to consume the WebSocket envelope so the live stress, confidence, fatigue, persona, confidence band, and Granite reasoning panels reflect the actual pipeline rather than synthetic frontend data.
- `run_backend.py` now also boots the predictive failure engine and the explainability worker so a single command brings every backend service online.

### Security and privacy

- New `src/backend/security` package containing JWT token issuance and verification, a role registry covering Team Principal, Race Strategist, Driver Engineer, and Neuro Analyst, and a Fernet based encryption helper for biometric payloads at rest.
- Retention helper that returns whether a biometric record is past its configured retention window, ready to wire into the privacy enforcement loop described in PRD section thirty four.

### Working notes

- These documents are the source of truth. If the code disagrees with them, the documents win and the code needs a fix.
- The OSS community files such as the Code of Conduct, the Contributing guide, the Security policy, and the GitHub issue templates are intentionally postponed and will be added once the core platform stabilises.

## [0.0.1] - 2026-05-19

### Initial scaffolding

- Initial project scaffolding and directory structure.
- Top level `README.md` introducing the Probabilistic Cognitive Inference methodology and the V1 scope.
- Layered backend folders under `src/backend` for `ingestion`, `feature_engineering`, `inference`, and `integration`.
- Next.js Mission Control scaffold under `src/frontend` with a working stress, confidence, and fatigue panel.
- Docker Compose definitions for Redpanda, InfluxDB 2, and Qdrant inside `infrastructure/`.
- FastF1 backed historical race streamer, Kafka producer, and feature extraction pipeline.
- Cognitive Inference Engine and Biometric Synthesiser wired into the event stream.
- Infrastructure bootstrap script that creates the full topic taxonomy and the Qdrant collections.
- Apache 2.0 LICENSE and NOTICE files attributing every third party component used in V1.
