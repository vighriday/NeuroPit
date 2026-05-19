"""Orchestrator that spins up every NeuroPit backend worker in one process.

This is the convenience entry point used during the demo. It launches the
feature extractor, the biometric synthesiser, the cognitive engine, the
predictive failure engine, the explainability worker, and the InfluxDB
writer in parallel. A graceful KeyboardInterrupt terminates every child.

The FastAPI gateway runs in its own uvicorn process via
`python -m src.backend.api.gateway` so it can hot reload while the workers
keep streaming.
"""

from __future__ import annotations

import logging
import multiprocessing
import os
import sys
import time

# Make sure the repository root is on sys.path when the script is launched as a file.
sys.path.append(os.path.join(os.path.dirname(__file__), "..", ".."))

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def run_features():
    from src.backend.inference.feature_extractor import FeatureExtractor

    FeatureExtractor().run()


def run_biometrics():
    from src.backend.inference.biometric_synthesizer import BiometricSynthesizer

    BiometricSynthesizer().run()


def run_cognition():
    from src.backend.inference.cognitive_engine import CognitiveInferenceEngine

    CognitiveInferenceEngine().run()


def run_failure_engine():
    from src.backend.prediction.failure_engine import PredictiveFailureEngine

    PredictiveFailureEngine().run()


def run_explainability():
    from src.backend.reasoning.explainability_worker import ExplainabilityWorker

    ExplainabilityWorker().run()


def run_emotional_state():
    from src.backend.inference.emotional_state_worker import EmotionalStateWorker

    EmotionalStateWorker().run()


def run_influx_writer():
    from src.backend.integration.influx_writer import InfluxDBWriter

    InfluxDBWriter().run()


WORKERS = (
    ("FeatureExtractor", run_features),
    ("BiometricSynthesizer", run_biometrics),
    ("CognitiveEngine", run_cognition),
    ("EmotionalStateWorker", run_emotional_state),
    ("PredictiveFailureEngine", run_failure_engine),
    ("ExplainabilityWorker", run_explainability),
    ("InfluxDBWriter", run_influx_writer),
)


def main():
    logger.info("Starting NeuroPit backend workers")

    processes = [multiprocessing.Process(target=target, name=name) for name, target in WORKERS]
    for p in processes:
        p.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("Interrupt received, terminating workers")
        for p in processes:
            p.terminate()
            p.join()
        logger.info("All workers shut down")


if __name__ == "__main__":
    main()
