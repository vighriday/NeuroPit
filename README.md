# NeuroPit

NeuroPit is a real time Cognitive Twin Operating System for motorsport. The car has been measured for decades. The mind inside the car has not. NeuroPit treats the driver as a probabilistic cognitive entity that can be inferred from the telemetry the car is already producing, and it does so under explainable AI principles that a race strategist can defend in a stewards meeting.

This is not a telemetry analytics dashboard. Telemetry is the input layer. The product is the Cognitive Twin.

Built for the IBM AI Builders Challenge powered by IBM SkillsBuild. Open source under Apache 2.0.

## What makes NeuroPit different

Generic AI racing tools follow the pattern telemetry to analytics to strategy. NeuroPit follows a different abstraction.

```text
Telemetry
  -> Behavioral Signal Extraction
  -> Probabilistic Cognitive Inference
  -> Emotional State Modeling
  -> Persona Drift Detection
  -> Explainable Human State Reasoning
  -> Cognitive Strategy Intelligence
```

Other systems ask what is happening to the car. NeuroPit asks what is happening to the human nervous system operating the car. The moat is not the dashboard or the strategy copilot. The moat is real time probabilistic cognition inference from racing telemetry, paired with IBM Granite explainability that grounds every reading in the motorsport ontology.

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

Plus a discrete persona label (Panic, Aggressive, Fatigue, Defensive, Flow State, Recovery), an emotional state distribution across nine emotions, and a confidence band (`high`, `moderate`, `unstable`) that travels with every output.

## What ships in V1

- Streaming pipeline that ingests historical Formula racing telemetry through OpenF1 and FastF1, plays it back through a Redpanda broker, and engineers behavioural features per driver.
- Probabilistic Cognitive Inference Engine that fuses behavioural features with telemetry conditioned synthetic biometrics into the full nine score twin.
- Dedicated Emotional State Engine that emits a normalised distribution across confidence, fear, panic, frustration, aggression, recovery, overconfidence, hesitation, and caution.
- Persona drift state machine.
- Predictive Failure Engine across the four PRD horizons (five seconds, one lap, three laps, full race).
- Ghost Lap AI reconstructing cognitive normalised laps with a per cause lost time breakdown.
- Counterfactual Simulation Engine covering the five canonical scenarios from PRD section twenty.
- Multi Agent Strategy Parliament with seven specialised agents and a tally based consensus.
- IBM Granite explainability through watsonx.ai, with a local templated stub so the demo never goes dark.
- Docling backed motorsport ontology compiler and Qdrant retriever so every Granite explanation can be grounded in real motorsport literature.
- Post race intelligence report assembling cognitive summary, confidence reconstruction, Ghost Lap, counterfactuals, and explanation timeline per driver.
- FastAPI gateway with JWT plus role based access (Team Principal, Race Strategist, Driver Engineer, Neuro Analyst) and Fernet at rest encryption for biometric payloads.
- Telemetry replay tool that re publishes raw frames from InfluxDB onto Kafka.
- Mission Control surface in Next.js with dedicated Ghost Lap, Counterfactual, and Explainability dashboards.

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

Step by step demo script in [`docs/DEMO_RUNBOOK.md`](docs/DEMO_RUNBOOK.md).

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
| Feature engine |                          | InfluxDB write |
+--------+-------+                          +----------------+
         |
         v
   telemetry-features
         |
         v
+----------------+
| Biometric synth|
+--------+-------+
         |
         v
   biometrics-enriched
         |
         v
+-------------------------+
| Cognitive Inference     |
| (full nine score twin)  |
+-----------+-------------+
            |
            +--------------------+--------------------+
            |                    |                    |
            v                    v                    v
+-------------------+   +---------------------+   +----------------+
| Emotional engine  |   | Predictive failure  |   | InfluxDB write |
+-------------------+   +---------------------+   +----------------+
            |
            v
+-------------------+
| Granite reasoning |
| + Qdrant grounding|
+--------+----------+
         |
         v
+-------------------------+
| FastAPI gateway + JWT   |
+-----------+-------------+
            |
            v
+-------------------------+
| Mission Control (Next)  |
|  + Ghost Lap            |
|  + Counterfactual       |
|  + Explainability       |
+-------------------------+
```

Full architecture at [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md). Topic taxonomy at [`docs/EVENT_TAXONOMY.md`](docs/EVENT_TAXONOMY.md). Cognitive methodology at [`docs/COGNITIVE_METHODOLOGY.md`](docs/COGNITIVE_METHODOLOGY.md). PRD compliance map at [`docs/PRD_COMPLIANCE_AUDIT.md`](docs/PRD_COMPLIANCE_AUDIT.md).

## Cognitive Inference Methodology

NeuroPit V1 uses a probabilistic cognitive inference architecture where cognitive states are derived from telemetry behaviour, synthetic physiological signals, environmental conditions, and race context variables through weighted deterministic inference functions. This was selected on purpose. It maximises explainability, preserves deterministic reasoning, supports IBM trustworthy AI principles, and gives the system a stable foundation for the learned models that will replace these functions in later phases.

The exact weights and their reasoning live in `docs/COGNITIVE_METHODOLOGY.md`. Every cognitive emission carries the active weight version so historical replays remain reproducible after the constants move.

## Tests

```bash
make test              # unit suite, no broker required
make integration       # smoke tests against a running Redpanda
```

The unit suite is the safety net for every cognitive equation, every persona rule, every prediction horizon, every counterfactual scenario, every Granite path, every gateway route, and every security helper.

## Optional cloud paths

The cloud paths are optional. When watsonx.ai credentials and the Qdrant cloud cluster are not configured, NeuroPit runs entirely on the local Docker stack with the local Granite stub and the local Qdrant Docker container.

- IBM watsonx.ai API key and project id for live Granite explanations.
- InfluxDB Cloud free tier bucket called `neuropit-telemetry` if you do not want to rely on the local Docker image.
- Qdrant Cloud free tier cluster for hosted vector storage.

## Licence

Apache 2.0. See [`LICENSE`](LICENSE) and [`NOTICE`](NOTICE) for attributions.

## Acknowledgements

NeuroPit was conceived, designed, and built for the IBM AI Builders Challenge powered by IBM SkillsBuild. The project relies on FastF1, OpenF1, IBM Granite, IBM Docling, Langflow, Redpanda, InfluxDB, Qdrant, FastAPI, and Next.js.
