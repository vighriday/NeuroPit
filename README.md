# NeuroPit

NeuroPit is a real time cognitive intelligence platform for Formula racing. Racing teams already measure the car in great detail. They do not measure the driver. NeuroPit treats the driver as a probabilistic signal that can be inferred from the telemetry the car is already producing, and it does that in a way the team can trust because every output ships with a written explanation and a confidence band.

This project was built for the IBM AI Builders Challenge powered by IBM SkillsBuild and is open source under the Apache 2.0 licence.

## What you get out of the box

- A streaming pipeline that ingests real Formula telemetry through OpenF1 and FastF1, plays it back through Redpanda, and engineers behavioural features per driver in a sliding window.
- A Probabilistic Cognitive Inference Engine that fuses those features with telemetry conditioned synthetic biometrics and emits stress, confidence, fatigue, tunnel vision, and persona drift readings for every evaluation tick.
- A Predictive Failure Engine that projects crash, lock up, spin, failed overtake, concentration collapse, and strategic non compliance probabilities across four horizons.
- A Ghost Lap AI and a Counterfactual Simulation Engine that reconstruct idealised laps and explore alternate race realities.
- A Multi Agent Strategy Parliament that runs seven specialised agents and produces a defensible consensus recommendation.
- IBM Granite explainability through watsonx.ai with a local templated stub so the dashboard never goes dark.
- IBM Docling backed knowledge ingestion into Qdrant with sentence transformers when available and a deterministic hashing fallback when it is not.
- A Mission Control dashboard built in Next.js that subscribes to a single FastAPI WebSocket and renders the cognitive trajectory in real time.
- A trust and uncertainty layer, an audit log that records every cognitive evaluation alongside the active weights, JWT plus role based access for the gateway, and a Fernet helper for at rest biometric encryption.

## Cognitive inference methodology

NeuroPit V1 uses a probabilistic cognitive inference architecture where cognitive states such as stress, fatigue, confidence, and aggression are derived from telemetry behaviour, synthetic physiological signals, environmental conditions, and race context variables through weighted deterministic inference functions.

This approach was selected on purpose. It maximises explainability, preserves deterministic reasoning, supports IBM's trustworthy AI principles, and gives the system a stable foundation for the learned models that will replace these functions in later phases. The full methodology lives in [`docs/COGNITIVE_METHODOLOGY.md`](docs/COGNITIVE_METHODOLOGY.md).

## Architecture at a glance

```text
OpenF1 / FastF1
   |
   v
Streamer  ->  Redpanda  ->  Feature extractor  ->  Biometric synthesiser
                                  |                        |
                                  v                        v
                            Cognitive Inference Engine
                                  |
        +-------------------------+----------------------------+
        |                         |                            |
        v                         v                            v
  Predictive Failure       Granite Explainability         InfluxDB
        Engine                Worker (watsonx.ai
                                or local stub)
        |                         |
        +-----------+-------------+
                    |
                    v
              FastAPI gateway
                    |
                    v
        Mission Control (Next.js + WebSocket)
```

The full document is at [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md). The Kafka topic taxonomy is at [`docs/EVENT_TAXONOMY.md`](docs/EVENT_TAXONOMY.md). The build plan that maps every PRD requirement to a phase is at [`docs/MASTER_BUILD_PLAN.md`](docs/MASTER_BUILD_PLAN.md).

## Quick start

You will need Python 3.11 or newer, Node 20 or newer, and Docker.

```bash
cp .env.example .env
make install
make infra-up
make bootstrap
make backend          # in one terminal
make gateway          # in another terminal
make stream           # in another terminal to start playing back the default session
cd src/frontend && npm install && npm run dev
```

Open the dashboard at `http://localhost:3000`. The Mission Control panel will populate as the cognitive engine emits events. The Granite reasoning panel will show explanations from watsonx.ai when credentials are configured and from the local stub otherwise.

For the full step by step walkthrough used during the demo, see [`docs/DEMO_RUNBOOK.md`](docs/DEMO_RUNBOOK.md).

## Tests

```bash
make test              # fast unit suite, no broker required
make integration       # smoke tests against a running Redpanda
```

Seventy three unit tests at last count. See [`tests/README.md`](tests/README.md) for the test layout.

## Prerequisites for the cloud path

The cloud path is optional. When the watsonx.ai credentials and the Qdrant cloud cluster are not configured, NeuroPit runs entirely on the local Docker stack with no loss of functionality.

- IBM watsonx.ai API key and project id for the Granite explanation calls.
- InfluxDB Cloud free tier bucket called `neuropit-telemetry` if you do not want to rely on the local Docker image.
- Qdrant Cloud free tier cluster if you want hosted vector storage.

## Licence

Apache 2.0. See [`LICENSE`](LICENSE) and [`NOTICE`](NOTICE) for attributions.

## Acknowledgements

NeuroPit was conceived, designed, and built for the IBM AI Builders Challenge powered by IBM SkillsBuild. The project leans on FastF1, OpenF1, IBM Granite, IBM Docling, Langflow, Redpanda, InfluxDB, Qdrant, FastAPI, and Next.js.
