# Security Policy

## Supported versions

NeuroPit is in active development. Security fixes are applied to the `main` branch and the latest tagged release.

| Version | Supported |
| --- | --- |
| 0.3.x | Yes |
| 0.2.x | Yes |
| 0.1.x | No |
| < 0.1 | No |

## Reporting a vulnerability

Please do not file a public GitHub issue for a security report.

Email vighriday@gmail.com with the following content.

- A short title that identifies the affected component.
- A reproducible description of the issue, including the exact commit, the configuration, and the steps that triggered the problem.
- Any logs, screenshots, or proof of concept attached.

The maintainer will acknowledge the report within seventy two hours and aim to ship a fix or a documented mitigation within fourteen days for high severity findings.

## Scope

The following surfaces are in scope.

- The cognitive inference engine and every supporting worker under `src/backend/`.
- The FastAPI cognitive gateway and the JWT plus role based access enforcement.
- The Fernet at rest encryption helper for biometric payloads.
- The Mission Control surface under `src/frontend/`.

The following are out of scope unless the report identifies a NeuroPit specific misconfiguration.

- IBM watsonx.ai, IBM Granite, IBM Docling, Redpanda, InfluxDB, Qdrant, Langflow, FastAPI, and Next.js themselves. Please report to the upstream projects.

## Defaults

The `.env.example` file ships safe development defaults. Production deployments must rotate `API_JWT_SECRET` and `ENCRYPTION_KEY`. The biometric synthesiser encrypts heart rate, HRV, and respiration payloads at write through the Fernet helper.
