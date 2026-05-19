# NeuroPit

![NeuroPit logo](docs/assets/neuropit-logo.png)

NeuroPit is a real time Cognitive Twin Operating System for motorsport. Telemetry is infrastructure. Cognition is the product.

Built for the IBM AI Builders Challenge powered by IBM SkillsBuild. Open source under Apache 2.0.

## Thesis

Telemetry can probabilistically reveal the hidden cognitive and emotional state of the driver. Every Formula team already measures the car. None of them meaningfully measures the human nervous system operating inside it. NeuroPit closes that gap.

Other systems ask: what is happening to the car. NeuroPit asks: what is happening to the human nervous system operating the car. The category is Human Machine Cognitive Intelligence for Motorsport. The moat is real time probabilistic cognition inference from racing telemetry, paired with IBM Granite explainability grounded in the motorsport ontology.

## What NeuroPit is not

- Not a telemetry analytics dashboard.
- Not a strategy copilot.
- Not a generic AI racing assistant.
- Not a telemetry insights tool.

## What NeuroPit is

A probabilistic human state inference system. The Cognitive Twin is the unit of value. Every other layer in the architecture exists to produce, ground, defend, and surface that twin.

## Cognitive pipeline

```text
Telemetry
  -> Behavioral Signal Extraction
  -> Probabilistic Cognitive Inference
  -> Emotional State Modeling
  -> Persona Drift Detection
  -> Explainable Human State Reasoning
  -> Cognitive Strategy Intelligence
```

The pipeline is event driven from end to end. The car is measured. The driver is inferred. We do not pretend otherwise.

## The full Cognitive Twin

Every evaluation tick produces the nine score twin documented in PRD section fifteen.

- Stress score
- Confidence score
- Fatigue score
- Cognitive load score
- Attention stability
- Strategic reliability
- Panic probability
- Emotional drift score
- Tunnel vision probability

A discrete persona label (Panic, Aggressive, Fatigue, Defensive, Flow State, Recovery), a nine emotion probability distribution, and a `high` / `moderate` / `unstable` confidence band travel alongside on every emission.

## What ships in V1

- Behavioral telemetry intelligence layer that derives per driver micro signals from OpenF1 and FastF1 streams replayed through Redpanda.
- Probabilistic Cognitive Inference Engine that fuses behavioural signals with telemetry conditioned synthetic biometrics into the full nine score twin.
- Dedicated Emotional State Engine emitting a normalised distribution across confidence, fear, panic, frustration, aggression, recovery, overconfidence, hesitation, and caution.
- Persona drift state machine for behavioural mode transitions.
- Predictive Failure Engine across the four PRD horizons (five seconds, one lap, three laps, full race).
- Ghost Lap AI reconstructing cognitive normalised laps with per cause lost time attribution.
- Counterfactual Simulation Engine covering the five canonical scenarios from PRD section twenty.
- Multi Agent Strategy Parliament producing a defensible cognitive strategy recommendation.
- IBM Granite explainable cognitive reasoning through watsonx.ai, with a local templated stub so the surface never goes dark.
- IBM Docling motorsport cognition ontology compiled into Qdrant, plus a retriever that grounds every Granite reading.
- Post race cognitive intelligence report assembling cognitive summary, confidence reconstruction, Ghost Lap, counterfactuals, and reasoning timeline per driver.
- FastAPI cognitive gateway with JWT plus role based access (Team Principal, Race Strategist, Driver Engineer, Neuro Analyst) and Fernet at rest encryption for biometric payloads.
- Telemetry replay tool that re publishes raw frames from InfluxDB onto the cognitive pipeline.
- Mission Control surface in Next.js with dedicated Ghost Lap, Counterfactual, and Explainability views into the Cognitive Twin.

## Quick start

You will need Python 3.11 or newer, Node 20 or newer, and Docker.

```bash
cp .env.example .env
make install
make infra-up
make bootstrap
make backend          # one terminal
make gateway          # another terminal
make stream           # another terminal
cd src/frontend && npm install && npm run dev
```

Open `http://localhost:3000`. Within ten seconds the live link banner switches to LIVE TELEMETRY and the Cognitive Twin starts streaming.

Step by step demo script in [`docs/DEMO_RUNBOOK.md`](docs/DEMO_RUNBOOK.md). Canonical narrative in [`docs/POSITIONING.md`](docs/POSITIONING.md).

## Architecture

```text
                +-------------------------+
                |   OpenF1 / FastF1       |
                +-------------+-----------+
                              |
                              v
                +-------------------------+
                |  Historical Race Streamer|
                +-------------+-----------+
                              |
                              v
                Redpanda  (incoming-telemetry-raw)
                              |
       +----------------------+---------------------+
       |                                            |
       v                                            v
+----------------+                          +----------------+
| Behavioral     |                          | InfluxDB write |
| signal engine  |                          +----------------+
+--------+-------+
         |
         v
   telemetry-features
         |
         v
+----------------+
| Biometric synth|
| (telemetry     |
|  conditioned)  |
+--------+-------+
         |
         v
   biometrics-enriched
         |
         v
+-------------------------+
| Probabilistic Cognitive |
| Inference Engine        |
| (full nine score twin)  |
+-----------+-------------+
            |
            +--------------------+--------------------+
            |                    |                    |
            v                    v                    v
+-------------------+   +---------------------+   +----------------+
| Emotional State   |   | Predictive failure  |   | InfluxDB write |
| Engine            |   | engine              |   +----------------+
+-------------------+   +---------------------+
            |
            v
+-------------------+
| IBM Granite       |
| explainable       |
| cognitive reason  |
| + Qdrant grounding|
+--------+----------+
         |
         v
+-------------------------+
| Cognitive Gateway (JWT) |
+-----------+-------------+
            |
            v
+-------------------------+
| Mission Control surface |
|  + Ghost Lap            |
|  + Counterfactual       |
|  + Explainability       |
+-------------------------+
```

Full architecture at [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md). Topic taxonomy at [`docs/EVENT_TAXONOMY.md`](docs/EVENT_TAXONOMY.md). Cognitive methodology at [`docs/COGNITIVE_METHODOLOGY.md`](docs/COGNITIVE_METHODOLOGY.md). PRD compliance map at [`docs/PRD_COMPLIANCE_AUDIT.md`](docs/PRD_COMPLIANCE_AUDIT.md).

## Cognitive Inference Methodology

NeuroPit V1 uses a probabilistic cognitive inference architecture where cognitive states are derived from telemetry behaviour, synthetic physiological signals, environmental conditions, and race context variables through weighted deterministic inference functions. This was selected on purpose. It maximises explainability, preserves deterministic reasoning, supports IBM trustworthy AI principles, and gives the system a stable foundation for the learned behavioral models that will replace these functions in later phases.

The exact weights and their reasoning live in `docs/COGNITIVE_METHODOLOGY.md`. Every cognitive emission carries the active weight version so historical replays remain reproducible after the constants move.

## Tests

```bash
make test              # unit suite, no broker required
make integration       # smoke tests against a running Redpanda
```

The unit suite is the safety net for every cognitive equation, every persona rule, every prediction horizon, every counterfactual scenario, every Granite path, every cognitive gateway route, and every security helper.

## Optional cloud paths

The cloud paths are optional. When watsonx.ai credentials and the Qdrant cloud cluster are not configured, NeuroPit runs entirely on the local Docker stack with the local Granite stub and the local Qdrant Docker container.

- IBM watsonx.ai API key and project id for live Granite explainable cognitive reasoning.
- InfluxDB Cloud free tier bucket called `neuropit-telemetry` if you do not want to rely on the local Docker image.
- Qdrant Cloud free tier cluster for hosted motorsport cognition ontology storage.

## Licence

Apache 2.0. See [`LICENSE`](LICENSE) and [`NOTICE`](NOTICE) for attributions.

## Acknowledgements

NeuroPit was conceived, designed, and built for the IBM AI Builders Challenge powered by IBM SkillsBuild. The project relies on FastF1, OpenF1, IBM Granite, IBM Docling, Langflow, Redpanda, InfluxDB, Qdrant, FastAPI, and Next.js.
