# Cognitive Inference Methodology

This document explains, in plain language, how NeuroPit goes from raw racing telemetry to a number that describes the driver's mental state. It is the source of truth for every weight, every threshold, and every assumption that lives inside the Probabilistic Cognitive Inference Engine.

We chose this approach deliberately. Training a real neural network on synthetic data inside a hackathon window would have produced something that looked like AI on the slide deck but was impossible to defend in a code review. A weighted probabilistic engine is honest about what it knows and what it does not, and it gives IBM Granite something concrete to reason over.

## Reading guide

Each section below covers one cognitive output. Every output has the same four parts.

1. What we are trying to measure.
2. What signals we use.
3. The function, written out so you can rebuild it from scratch.
4. The reasoning behind the weights.

If you ever want to retune a weight, edit this document first, then the code. The audit log captures the active set of weights on every cognitive event, so old race replays still make sense after the constants move.

## 1. Stress Score

What we are trying to measure. A zero to one hundred estimate of mental pressure. High stress is not the same as fast driving. A driver can be fast and calm, fast and overloaded, or slow and panicking. We are after the second case.

Signals used.

- `steering_instability` from `SignalProcessor`.
- `panic_oscillation` from `SignalProcessor`.
- `synthetic_hr` from `BiometricSynthesizer`, used only above a baseline of one hundred forty beats per minute.

Function.

```
steering_term = min(steering_instability * 10, 100)
hr_term       = max(0, synthetic_hr - 140) * 1.5
stress_score  = clamp_0_100(steering_term * 0.40
                          + hr_term     * 0.40
                          + panic_oscillation * 0.20)
```

Reasoning. Forty percent on steering because most stress signatures in publicly available motorsport literature surface through micro corrections of the wheel before they surface anywhere else. Forty percent on heart rate elevation because once the body is committed to a stress response the cardiovascular signal is the most reliable confirmation. Twenty percent on panic oscillation because pure panic is rare. We want it represented but we do not want it to dominate the score on a single noisy lap.

## 2. Confidence Score

What we are trying to measure. A zero to one hundred estimate of driver decisiveness. Confidence collapses before laptimes do, so it is a useful leading indicator for the strategist.

Signals used.

- `throttle_commitment` from `SignalProcessor`.
- `braking_hesitation` from `SignalProcessor`.

Function.

```
throttle_term  = min(throttle_commitment * 5, 100)
hesitation_pen = braking_hesitation * 0.05
confidence_score = clamp_0_100(100 - ((100 - throttle_term) * 0.60
                                     + hesitation_pen))
```

Reasoning. Throttle commitment carries sixty percent of the weight because the decision to commit to throttle out of a corner is the most direct behavioural marker of trust in the car. Braking hesitation is treated as a penalty rather than as a positive signal. We do not want a smooth braker to be punished. We want a pumping braker to be flagged.

## 3. Fatigue Score

What we are trying to measure. A zero to one hundred estimate of cumulative cognitive exhaustion across a session. Fatigue is the only score that explicitly carries state from one window to the next.

Signals used.

- `stress_score` from the same evaluation tick.
- `steering_instability` from `SignalProcessor`.
- A persistent `cumulative_fatigue` value per driver, stored inside the engine.

Function.

```
delta = (stress_score          * 0.0005)
      + (steering_instability  * 0.001)

cumulative_fatigue = cumulative_fatigue + delta
fatigue_score      = min(cumulative_fatigue, 100)
```

Reasoning. The constants are deliberately small. Fatigue should creep upward across a race rather than spike on a single corner. A driver with a sustained stress score in the seventies for thirty minutes of racing reaches a fatigue score of roughly sixty three. That matches the qualitative reports from real drivers in long stints.

## 4. Persona Drift

What we are trying to measure. The discrete behavioural mode the driver is operating in right now. We map continuous cognitive scores into one of six labels.

Decision rules, evaluated in order. The first rule that matches wins.

1. Panic when `stress_score` is above eighty five and `panic_oscillation` is above twenty.
2. Aggressive when `stress_score` is above seventy and `throttle_commitment` is above eighty.
3. Fatigue when `fatigue_score` is above sixty and `confidence_score` is below forty.
4. Defensive when `confidence_score` is below fifty.
5. Flow State when `stress_score` is below forty and `confidence_score` is above eighty.
6. Recovery as the default.

Reasoning. We start with the highest stakes label, Panic, so the strategist sees the right warning even when other modes also apply. Flow State is the rarest label and the rules reflect that. Recovery is the catch all because most of a race is, in fact, recovery between stress events.

## 5. Tunnel Vision

A boolean flag promoted into a probability for downstream consumers.

```
tunnel_vision_prob = 100.0 if stress_score > 85 else 0.0
```

This is intentionally crude in V1. It exists so that the audit log and the dashboard both have a stable field name to read. The first real model that replaces it will keep the same field so nothing downstream needs to change.

## 6. Confidence Band

Every cognitive event ships with a confidence band of `high`, `moderate`, or `unstable`. The band is computed from three inputs.

1. `data_completeness` which is the fraction of expected telemetry fields that were not null in the contributing window.
2. `sensor_agreement` which is the fraction of contributing signals that move in the same direction.
3. `biometric_freshness` which is the time since the last biometric sample.

Rules of thumb. High band when completeness is above ninety percent and agreement is above seventy percent. Moderate band when completeness is above seventy percent. Unstable band otherwise. The exact constants live next to the function in code and are unit tested.

## 7. Why this approach

A weighted probabilistic engine is interpretable. Every score can be defended against a question of the form "why is this number what it is." That matters because the dashboard is going to show this number to a race strategist who has to make a million pound decision. Saying "the model said so" is not an answer. Saying "stress increased because steering instability rose by forty percent and heart rate rose by twelve beats per minute over the previous six laps" is.

The engine is also a stable foundation for the learned models that follow. The features fed into a trained sequence model are exactly the same features that drive these equations. The output schema does not change. The only thing that changes is the function that maps features to scores. That is the right way to evolve a cognitive system.

## 8. Versioning

Every adjustment to the constants above bumps `VERSION` in `src/backend/common/weights.py` and lands in the same commit as the change. The audit log writes the active constants alongside the cognitive event so historical replays remain reproducible.

## Driver Performance Envelope and the Optimality Gap

The Cognitive Twin describes the driver. The Driver Performance Envelope describes the driver's own fast lap cognitive signature. The Optimality Gap is the signed distance between the two. This section documents every constant inside `src/backend/prescription/envelope.py` and `src/backend/prescription/optimality.py`.

What we are trying to measure. A real time estimate of how close the driver is to their own peak performance cognitive state, plus an honest estimate of how much laptime they are leaving on the table this lap because of cognitive distance from that state.

Why not a deep network. A learned model trained inside a hackathon window on synthetic priors would not be defensible in a code review or a stewards' meeting. The envelope is a non parametric centroid in five dimensional cognitive space. Every constant is interpretable. Phase 3 of the roadmap swaps the inference function for a learned model without changing this contract.

The five envelope dimensions. `stress_score`, `confidence_score`, `fatigue_score`, `cognitive_load_score`, `panic_probability`. These five carry most of the laptime relevant signal. Attention stability, strategic reliability, emotional drift, and tunnel vision are still surfaced on the dashboard but they correlate strongly with the five envelope dimensions and including them would over weight the same underlying signal.

Per dimension weights inside the distance calculation.

```
stress_score          0.18
confidence_score      0.32
fatigue_score         0.18
cognitive_load_score  0.14
panic_probability     0.18
```

Confidence carries the biggest coefficient because confidence collapses before laptime collapses in publicly available footage. Panic and stress matter for safety but tend to lag confidence. Cognitive load gets a slightly smaller weight because at moderate values it is part of normal racing.

Bootstrap. On first sight of a driver the envelope is seeded from a persona prior. Flow State has low stress, high confidence, modest cognitive load, near zero panic. Aggressive deliberately pushes stress and load. Panic is the worst case prior. Each prior carries a tolerance vector that widens for noisier states. Priors live in `PERSONA_PRIORS` inside `envelope.py`.

Online refinement. Every cognitive event with a `high` confidence band moves the centroid with an exponential moving average at smoothing factor 0.04. Events with a `moderate` band are dampened. Events with an `unstable` band are ignored. Tolerances shrink slowly with evidence but never below the floor of six points. The envelope's `sample_count` is surfaced to Mission Control so the operator can see how much evidence is behind the centroid.

Distance to efficiency.

```
cognitive_efficiency = 100 * exp(-0.5 * weighted_distance)
```

Distance zero maps to efficiency one hundred. Distance one (one tolerance band per dimension) maps to ~61. Distance two maps to ~14. Small drifts inside the tolerance band do not panic the operator. Bigger drifts collapse the score quickly.

Distance to seconds left on the table.

```
performance_lost_s = 0.45 * weighted_distance
```

The anchor is documented in `DISTANCE_TO_SECONDS`. A normalised distance of one band maps to roughly forty five hundredths of a second. The shape was chosen so a clearly out of envelope driver shows up as "leaving half a second on the table" rather than "leaving five seconds on the table".

Per dimension contributions. The Optimality Report returns the share of weighted distance attributable to each dimension. The dashboard surfaces the top contributor so the strategist sees "biggest envelope drift on confidence" rather than a single opaque number.

## Action space and guardrails

The prescriptive engine is only allowed to emit one of the nine actions defined in `src/backend/prescription/actions.py`. The action space is small on purpose. A judge can read the whole file in thirty seconds and verify no action was hallucinated.

Each action carries an expected effect on the cognitive twin per dimension. The engine projects the counterfactual twin five seconds out by applying the effect once and clipping every dimension to zero to one hundred. The projected efficiency under the action is what the Mission Control panel surfaces next to the action label.

Guardrails are independent of the scoring engine. A high score cannot bypass a safety rule. Currently:

- `radio_push` is blocked when `panic_probability > 55`.
- `request_undercut_window` is blocked when `confidence_score < 55`.
- `defensive_mode` is blocked when persona is Flow State.
- `box_now` is blocked when persona is Flow State and panic probability is below 50.

The scoring rules live in `src/backend/prescription/engine.py`. Each action has explicit triggers that contribute to its score. The engine sorts non blocked actions by score, picks the top one as the primary recommendation, and surfaces the next three as alternatives. Blocked actions sink to the bottom of the ranking and are clearly labelled with the guardrail that vetoed them.

The five second forecast (`anomaly-events` topic) feeds the scoring engine as well. A high forecast panic collapse probability boosts `radio_calm` and `box_now`, and dampens `radio_push` even when the live state looks safe.

## What If Replay

The cognitive engine writes a JSONL audit row for every evaluation. Each row stores the engineered feature vector and the biometric snapshot that produced the score. The What If Replay engine in `src/backend/whatif/replay.py` reads those rows back, applies typed mutations to one or more rows, and re runs the exact same deterministic cognitive maths over the mutated inputs.

Mutations use a dotted path inside the audit row (`inputs.biometrics.synthetic_hr`, `inputs.features.throttle_commitment`, etc.). The mutation API rejects unknown paths, whitespace, and characters outside `[A-Za-z0-9_.]` so the surface is small and predictable.

The recomputation in `replay.py` mirrors `CognitiveInferenceEngine.evaluate` line for line. A unit test pins the maths so the two files cannot drift between live evaluation and replay.

What If is grounded in real session data. It is not a synthetic counterfactual. The strategist can defend the result because the inputs are the exact ones the system saw at race time.

## Supplementary score weights

The five envelope dimensions above carry most of the laptime relevant signal, but the dashboard also surfaces four supplementary scores. Their weights are versioned in `src/backend/common/weights.py` and stamped into every audit row.

### Cognitive load (`CognitiveLoadWeights`)

A convex blend of the inputs that grow the driver's processing burden.

| Weight | Field | Value |
| --- | --- | --- |
| `micro_correction` | micro correction frequency | 0.25 |
| `throttle_jitter` | throttle jitter | 0.20 |
| `panic` | panic oscillation | 0.20 |
| `stress` | live stress score | 0.35 |

### Attention stability (`AttentionStabilityWeights`)

Higher is better. Destabilising signals are inverted before they enter the blend.

| Weight | Field | Value |
| --- | --- | --- |
| `confidence` | live confidence score | 0.40 |
| `inv_stress` | 100 minus stress | 0.25 |
| `inv_steering_instability` | 100 minus steering instability | 0.20 |
| `inv_micro_correction` | 100 minus micro correction | 0.15 |

### Strategic reliability (`StrategicReliabilityWeights`)

Likelihood of executing the planned race strategy.

| Weight | Field | Value |
| --- | --- | --- |
| `confidence` | live confidence score | 0.35 |
| `attention` | attention stability | 0.30 |
| `inv_fatigue` | 100 minus fatigue | 0.20 |
| `inv_panic` | 100 minus panic probability | 0.15 |

### Panic probability (`PanicProbabilityWeights`)

Discrete probability that the driver tips into a panic episode.

| Weight | Field | Value |
| --- | --- | --- |
| `panic_oscillation_gain` | gain on the high frequency steering signature | 3.5 |
| `stress_term` | weight on live stress | 0.45 |
| `tunnel_vision_term` | weight on the tunnel vision flag | 0.25 |

### Predictive Failure Engine (`FailureForecastWeights`)

The Predictive Failure Engine in `src/backend/prediction/failure_engine.py` projects six race critical failure probabilities across four horizons. Each probability is a convex combination, then each horizon scales the result by the listed decay so the further out the forecast, the lower the confidence.

| Probability | Inputs (weight) |
| --- | --- |
| `crash_likelihood` | tunnel vision (0.5), stress (0.3), inverse confidence (0.2) |
| `lock_up_probability` | stress (0.6), inverse confidence (0.4) |
| `spin_probability` | inverse confidence (0.5), stress (0.3), Panic persona flag (0.2) |
| `failed_overtake_probability` | inverse confidence (0.5), Defensive or Fatigue persona flag (0.5), default 0.2 otherwise |
| `concentration_collapse` | fatigue (0.4), recent stress (0.4), Fatigue persona flag (0.2) |
| `strategic_noncompliance` | Aggressive persona flag (0.5), stress (0.3), inverse confidence (0.2) |

Horizon decay: `5s` 1.00, `1lap` 0.85, `3laps` 0.70, `full_race` 0.55.

---

NeuroPit · Built by Hriday Vig · IBM AI Builders Challenge 2026 powered by IBM SkillsBuild.
