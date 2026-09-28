# Incident Report: Payments API Degradation

## Summary
At 2026-08-30T03:12:00.000Z, the `payments-api` service triggered a P1 alert due to high latency (p95 > 8s) and an error rate spike exceeding 60%. Investigation revealed that the third-party payment gateway (`paygate`) is encountering timeouts and returning 503 Service Unavailable errors.

## Timeline
- **2026-08-30T02:50:32.000Z**: First `paygate` timeout logged in `payments-api`.
- **2026-08-30T02:52:03.000Z**: First explicit `503 Service Unavailable` body='upstream maintenance' received from Paygate.
- **2026-08-30T03:12:00.000Z**: `payments-api` error rate spikes to ~62% and latency p95 exceeds 8 seconds, triggering P1 alert.

## Root Cause
Third-party payment gateway outage/maintenance at `api.paygate.example`. Because the circuit breaker was disabled (`'CIRCUIT_BREAKER': 'off'`), `payments-api` exhausted threads/time waiting for 8000ms per request, impacting downstream checkout requests through the API gateway.

## Evidence
- `payments-api.error_rate_pct` increased from 0.4% to ~64%.
- Log entries showing: `ERROR payments-api: paygate request timeout after 8000ms` and `ERROR payments-api: paygate 503 Service Unavailable body='upstream maintenance'`.

## Remediation
Enable the circuit breaker on `payments-api` to fail fast and prevent thread exhaustion while the third-party vendor resolves the outage.

## Follow-ups
1. Enable automated circuit breakers and fallback responses for external vendor integrations.
2. Escalate to the Paygate vendor regarding the unannounced maintenance/outage.