# NeuroPit developer shortcuts.
#
# The make targets below mirror the commands documented in the README so a
# contributor only needs to remember one entry point. Each target is safe to
# run on a developer laptop with the local docker stack online.

PYTHON ?= python

.PHONY: help install infra-up infra-down bootstrap stream backend gateway frontend test unit integration lint clean

help:
	@echo "NeuroPit developer commands"
	@echo "  install      install backend python dependencies"
	@echo "  infra-up     bring up Redpanda, InfluxDB and Qdrant via docker compose"
	@echo "  infra-down   stop the local docker stack"
	@echo "  bootstrap    create kafka topics and qdrant collections"
	@echo "  stream       replay the default historical session through the streamer"
	@echo "  backend      run the full backend worker pool"
	@echo "  test         run the fast unit test suite"
	@echo "  integration  run the integration tests (requires running infra)"

install:
	$(PYTHON) -m pip install -r src/backend/requirements.txt

infra-up:
	docker compose -f infrastructure/docker-compose.yml up -d

infra-down:
	docker compose -f infrastructure/docker-compose.yml down

bootstrap:
	$(PYTHON) -m src.backend.init_infrastructure

stream:
	$(PYTHON) -m src.backend.ingestion.streamer

backend:
	$(PYTHON) -m src.backend.run_backend

gateway:
	$(PYTHON) -m src.backend.api.gateway

frontend:
	cd src/frontend && npm run dev

test unit:
	$(PYTHON) -m pytest tests/unit

integration:
	$(PYTHON) -m pytest -m integration tests/integration

clean:
	rm -rf .pytest_cache .mypy_cache .ruff_cache **/__pycache__
