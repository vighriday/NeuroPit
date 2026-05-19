# Tests

The test suite is split into two folders so a new contributor can run the fast checks without standing up the full infrastructure.

## Unit tests

Pure Python, no broker, no database. Cover the signal processor maths, the persona drift rules, the trust and uncertainty layer, the audit log writer, and the cognitive equations against the documented weights.

```
make test
```

There is no excuse for these tests to fail on any developer machine.

## Integration tests

Smoke tests against a running Redpanda broker. They publish synthetic frames into the same topics the live system uses and assert that the downstream worker reacts the way it should. They are skipped by default and only run when you pass the `integration` marker explicitly.

```
docker compose -f infrastructure/docker-compose.yml up -d
python -m src.backend.init_infrastructure
make integration
```

## Adding a new test

New behavioural rules belong in `tests/unit` next to the module they cover. New end to end flows belong in `tests/integration` and must be marked with `pytest.mark.integration` so they stay out of the default run.
