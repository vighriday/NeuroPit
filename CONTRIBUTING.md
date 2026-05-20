# Contributing to NeuroPit

Welcome. NeuroPit is a real time Cognitive Twin Operating System for motorsport. The README, the architecture document, the cognitive methodology, and the event taxonomy live in the `docs/` folder. Read those before you write code.

## What we accept

- Bug fixes against the existing cognitive engine, the emotional state engine, the predictive failure engine, the Ghost Lap AI, the counterfactual simulator, the strategy parliament, the explainability worker, the gateway, or the Mission Control surface.
- New features that map cleanly to an unimplemented layer of the architecture in `docs/ARCHITECTURE.md`.
- New tests against existing code. We treasure tests.
- Documentation improvements that preserve the Cognitive Twin Operating System positioning. Telemetry is infrastructure. Cognition is the product.

## What we do not accept by default

- Pull requests that drift the project into telemetry analytics framing. Telemetry is infrastructure. Cognition is the product.
- Pull requests that fork the API contract without updating the schemas in `src/backend/api/schemas.py` and the shared models in `src/backend/ingestion/models.py`.
- Pull requests that swap the local first execution model for a hyperscale cloud commitment without an architecture amendment in `docs/ARCHITECTURE.md`.

## Local development

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

If you only need to work on the cognitive engine, the signal processor, or any of the pure Python modules, the unit suite runs without infrastructure.

```bash
make test
```

A full integration sweep needs Redpanda online.

```bash
make integration
```

## Pull request expectations

1. Branch from `main`. Name the branch `feature/<short-slug>` or `fix/<short-slug>`.
2. Write a unit test before the fix or feature. The unit suite must stay green.
3. Update `docs/COGNITIVE_METHODOLOGY.md` if you adjust a weight. Update `docs/EVENT_TAXONOMY.md` if you add a topic.
4. Open the pull request against `main`. Use the pull request template. Tick the boxes that apply.
5. CI must pass. The unit suite, the import smoke, and the frontend type check all run on every pull request.

## Code style

- Python: type hints on public function signatures. Module level docstrings explain the intent in plain language. No multi paragraph docstrings on every function.
- TypeScript: strict mode is on. The frontend type check runs with `npx tsc --noEmit`. Run it before opening a pull request.
- Commits: imperative present tense subject. Short body that explains the why, not the what.

## Security

If you discover a vulnerability please follow `SECURITY.md`. Do not open a public issue.

## License

NeuroPit is licensed under Apache 2.0. Copyright 2026 Hriday Vig. By contributing, you agree that your contributions will be licensed under the same license.

## Maintainer

[Hriday Vig](https://github.com/vighriday). NeuroPit was built solo for the IBM AI Builders Challenge 2026 powered by IBM SkillsBuild.

---

NeuroPit · Built by Hriday Vig · IBM AI Builders Challenge 2026 powered by IBM SkillsBuild.
