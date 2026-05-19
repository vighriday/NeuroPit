# NeuroPit cognitive methodology seed

This is the seed document that ships with the repository so the Docling compiler has something to ingest immediately after a fresh checkout. The compiler will split this file into overlapping passages, embed each passage, and store the result inside the Qdrant `motorsport_ontology` collection.

## Why cognitive state matters in motorsport

Modern Formula racing teams already measure the car in extraordinary detail. They do not measure the driver in any meaningful way. The pit wall sees laptimes, tyre temperatures, and brake bias positions, but it does not see whether the driver is mentally overloaded, whether confidence is collapsing, or whether panic is starting to accumulate after a near miss.

A driver who has just survived a wet braking incident at three hundred kilometres per hour does not return to a neutral mental state on the next straight. Their steering becomes microscopically less stable. Their throttle commitment drops. Their heart rate variability tightens. These changes are invisible to the dashboard but they are present in the telemetry the car is already producing.

## The probabilistic cognitive inference engine

NeuroPit treats the driver as a probabilistic signal that can be inferred from observable behaviour. The engine uses weighted deterministic functions in V1 rather than a hastily trained model, because a weighted function can be defended in a strategist meeting and a hastily trained model cannot.

Stress is modelled as a forty percent contribution from steering instability, a forty percent contribution from elevated heart rate above a one hundred and forty beat per minute baseline, and a twenty percent contribution from panic oscillation signatures. Confidence is modelled as a function of throttle commitment with a penalty for braking pump variance. Fatigue accumulates over the race based on sustained stress and steering instability.

## Persona drift

The cognitive engine assigns a discrete behavioural label to every evaluation, drawn from a fixed list of six labels: Panic, Aggressive, Fatigue, Defensive, Flow State, and Recovery. The labels are computed by a simple state machine that prefers higher stakes labels over lower stakes ones when multiple rules match.

## Trust and uncertainty

Every score ships with a confidence band of high, moderate, or unstable. The band is computed from data completeness and sensor agreement so the dashboard never displays a number without telling the strategist how reliable that number is.

## IBM Granite explainability

The Granite reasoning layer takes the numerical cognitive state and turns it into a single short paragraph in plain English. When the watsonx.ai endpoint is unreachable, a local stub takes over and produces a templated paragraph from the same inputs. The dashboard cannot tell the two apart from a contract perspective, which means a demo never goes dark just because the cloud is having a bad day.
