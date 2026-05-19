# Pull request

## Summary

<!-- One paragraph that explains the why. -->

## Scope

- [ ] This change touches code under `src/backend/`.
- [ ] This change touches code under `src/frontend/`.
- [ ] This change touches documentation under `docs/`.
- [ ] This change touches infrastructure under `infrastructure/` or `.github/`.

## PRD mapping

<!-- Which PRD section does this change implement, deepen, or fix? -->

PRD section:

## Cognitive twin impact

- [ ] No change to any cognitive score, weight, or persona rule.
- [ ] Cognitive score, weight, or persona rule changed. `docs/COGNITIVE_METHODOLOGY.md` updated in the same commit.

## Positioning impact

- [ ] No user facing copy changed.
- [ ] User facing copy changed. `docs/POSITIONING.md` consulted. No banned phrases introduced.

## Tests

- [ ] Unit suite passes locally with `make test`.
- [ ] Frontend type check passes locally with `npx tsc --noEmit` inside `src/frontend`.
- [ ] Integration suite ran where applicable (`make integration`).

## Changelog

- [ ] `CHANGELOG.md` updated under the Unreleased section.
