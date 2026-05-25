# Failure modes, dead ends, and design retrospectives

This file is the honest log of approaches that were tried and either
abandoned or rebuilt during the build of NeuroPit. It exists so that a
reader can see what was rejected and why, not only what shipped.

Each entry is a real decision, traceable to specific code or commits in
the public history of this repository. Nothing is invented for effect.

---

## 1. Granite called per cognitive event was a non starter

**What was tried.** The first wiring of IBM Granite called the model
once per cognitive event on the main pipeline thread. Every telemetry
frame produced a score, every score asked Granite for a paragraph, the
paragraph went straight to the broadcast.

**Why it broke.** Granite 3.0 2B Instruct on CPU takes between three and
six seconds per generation. The streamer emits a frame every fifth of a
second per driver. The Granite call became the bottleneck for the whole
twin, and the dashboard stalled while the model thought.

**What was shipped.** The reasoning step was decoupled into its own
worker (`src/backend/reasoning/explainability_worker.py`) that consumes
from an `explanation-events` topic and writes back asynchronously. The
cognitive engine stamps `explainability_pending: true` on the live event
and the explainability worker fills the paragraph in at its own pace.
The audit log captures both rows.

**Why this is the better answer.** Live cognitive numbers stay real
time. Granite explanations arrive a beat later but never block the
dashboard. The architecture diagram in `docs/ARCHITECTURE.md` shows the
two paths.

---

## 2. ML based stress regression was abandoned for heuristics

**What was tried.** Early in the build the stress score was going to be
a small XGBoost regressor trained on simulated driver labels (synthetic
telemetry plus hand annotated stress targets).

**Why it was abandoned.** Two reasons. First, simulated labels are not
ground truth, so the model would have inherited every bias in the
simulator. Second, and more important, a stewards meeting cannot defend
a number that came out of a black box. The brief was clear: every score
has to be explainable to a human who has not read the model card.

**What was shipped.** A transparent dataclass driven formula in
`src/backend/common/weights.py`. Each weight is a named constant, the
combination is a documented convex blend in
`docs/COGNITIVE_METHODOLOGY.md`, and the snapshot of the live weight set
is stamped onto every audit row so the historical numbers stay
reproducible after a tuning pass.

**Tradeoff acknowledged.** Heuristics ceiling out around eighty percent
of the accuracy a tuned model could reach. Below that line the
explainability is worth more than the extra points.

---

## 3. Mocked Kafka in tests caused silent divergences

**What was tried.** The first test pass mocked the `confluent_kafka`
Consumer and Producer with `unittest.mock`. The mocks returned canned
messages and counted produce calls.

**Why it broke.** Two issues showed up the first time the integration
test was run against a real broker. Offset behaviour diverged (mocks
returned messages out of order on rebalance) and the producer flush
semantics were different (mocks never blocked, the real producer does).
Two unit tests passed for weeks while the live cognitive event topic
was actually broken.

**What was shipped.** Worker logic was extracted into pure
`_handle_state(state: dict) -> dict` style functions that take a
parsed dict and return the produced payload. Unit tests cover those
pure functions deterministically. The Kafka transport layer is covered
by `tests/integration/` which only runs when a broker is present. The
CI workflow runs unit tests only, the integration suite is gated on
having Redpanda live.

**Lesson kept.** Mocks are for behaviour at the seams. The broker side
of those seams is exercised live in the integration suite, not faked.

---

## 4. The streamer originally hard coded the 2021 Abu Dhabi session

**What was tried.** First version of the streamer (`src/backend/ingestion/streamer.py`)
loaded a fixed session at module import time. It was the only thing
that could replay because the path was baked in.

**Why it broke.** A demo run from a fresh clone failed because the
FastF1 cache was empty and the network was throttled. The streamer
had no way to point at a different year or event without editing code.

**What was shipped.** The playback session is configured via
`DEFAULT_PLAYBACK_YEAR`, `DEFAULT_PLAYBACK_EVENT`, and related env
vars, all surfaced in `.env.example`. The default is still 2021 Abu
Dhabi (telemetry density is higher there than any 2024 race that is
publicly available) but a judge can flip the year by editing one line
in their local `.env`.

---

## 5. The InfluxDB password was checked in by accident

**What was tried.** During the local infra build, the docker compose
file shipped with a literal admin password (`neuropit_secure_pass_2026`)
and admin token (`neuropit-local-dev-token-999`). The Python settings
carried the same token as a default. The reasoning at the time was
"it is a dev only stack on a single laptop, nobody can reach it."

**Why it broke.** Secret scanners do not care about reachability. A
public repo with a credential string in version control trips every
automated scanner, and a judge with a security checklist would flag it
in five seconds. Plus, anyone forking the repo would inherit the same
admin token and might not notice.

**What was shipped.** The compose file now refuses to start unless
`INFLUXDB_INIT_PASSWORD` and `INFLUXDB_TOKEN` are set in `.env`. The
Python settings default to the empty string. `.env.example` documents
both as `replace-with-...` placeholders. The fix is in commit
`6ec3e2e`. The leaked values are scrubbed from the working tree but
they remain in git history for any commit predating the fix.

**Lesson kept.** Even on a dev only stack, never write a credential
into a public file. The cost of using an env var is zero, the cost of
not using one is a security flag during judging.

---

## 6. Encryption key warning was firing thousands of times per session

**What was tried.** The Fernet cipher helper in
`src/backend/security/crypto.py` emitted a warning every time it built
a cipher with no `ENCRYPTION_KEY` set (which is the default in dev).

**Why it broke.** Every encrypted biometric write went through the
helper. During a real boot the warning fired roughly once per
telemetry frame, flooding the logs with thousands of identical lines.
A judge reading the log to verify the pipeline would have to scroll
past a wall of noise to find a real event.

**What was shipped.** A module level `_dev_key_warning_emitted` flag
de-duplicates the warning so it fires once per process. The intent
of the warning (operator notice that the dev fallback key is active)
is preserved. The fix is in commit `b75bc82`.

---

## 7. The Judge Quickstart told judges to `cd NeuroPit`

**What was tried.** The repository was originally called `NeuroPit`.
The Judge Quickstart in the README told the reader to run
`git clone ... && cd NeuroPit`.

**Why it broke.** The repository was renamed to `neuropit-may-2026` to
match the IBM challenge naming convention (`teamname-challengemonth-year`).
The README was not updated. A judge running the one line setup would
hit `No such directory` on the very first step.

**What was shipped.** Every reference to `cd NeuroPit` was updated to
`cd neuropit-may-2026` in commit `6b82336`. A full dry run was then
performed against a fresh clone to catch any other path mismatches.

---

## 8. The Makefile broke after the env var refactor

**What was tried.** Once InfluxDB credentials moved into mandatory
env vars (see entry five above), the existing Makefile targets
`infra-up` and `infra-down` called `docker compose` without an
`--env-file` flag.

**Why it broke.** Docker Compose v2 looks for `.env` next to the
compose file (which lives under `infrastructure/`), not at the
repository root. The `.env` file is at the repo root by convention.
The stack refused to come up with `required variable
INFLUXDB_INIT_PASSWORD is missing a value`.

**What was shipped.** Both `make infra-up` and `make infra-down`
now pass `--env-file .env` explicitly. The raw command fallback in
the README was updated to match. The fix is in commit `b75bc82`.

**Lesson kept.** Refactoring a config surface is the easy part.
Tracing every downstream consumer of that surface is the long
tail and the part where regressions hide.

---

## 9. The requirements.txt was unresolvable on a fresh clone

**What was tried.** Initial pin set was `fastf1==3.1.2` plus
`pandas==2.2.3`.

**Why it broke.** `fastf1` 3.1.2 declares `pandas<2.1.0` in its
metadata. A fresh `pip install -r requirements.txt` hit
`ResolutionImpossible` before installing anything. The development
venv had been running newer floor versions for weeks so the
conflict was invisible during day to day work.

**What was shipped.** Every hard pin was loosened to a floor
(`>=X,<X+1`) so pip can pick a coherent set. The dev venv versions
were used as the floor where they were known to work. Commit
`03f419f`. The 178 unit tests still pass on the bumped versions.

**Lesson kept.** Run the install path the judge would run, on a
clone that is not your day to day workspace. The error you cannot
reproduce on your own machine is the one the judge will hit first.

---

## 10. Granite explanations on a 16 GB laptop run the 2B variant

**What was tried.** The original plan was to ship Granite 3.1 8B
Instruct as the default explainer because the 8B model produces
notably better paragraphs.

**Why it broke.** The 8B model on CPU on a 16 GB machine spills to
swap during inference, so a single paragraph takes north of thirty
seconds. The recorded demo would have to either skip live
explanations or pause every reasoning step.

**What was shipped.** The default model id is set to
`ibm-granite/granite-3.0-2b-instruct`, which fits in memory and
returns paragraphs in under three seconds on CPU. The README
documents the swap path: a developer with a 32 GB machine or a
CUDA GPU can flip `GRANITE_MODEL_ID` to the 8B variant in `.env`
and get the better paragraphs.

---

## What this list is not

This is not a comprehensive defect log. It is a curated set of
decisions that are useful to know about because they shape the
final architecture. Surface bugs (typos, lint, frontend pixel work)
are tracked in commit history rather than here.

If you are evaluating this project and you want to see the long tail,
`git log --oneline` is the source of truth. The repository has been
public from day one of the submission window.
