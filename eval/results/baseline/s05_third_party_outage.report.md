# Incident Report: Payments API Degradation

## Summary
Starting at 2026-08-30T03:12:00.000Z, the `payments-api` service experienced high error rates (~64%) and elevated p95 latency (>8s). This was caused by an outage/upstream maintenance at the third-party payment gateway (`paygate.example`).

## Timeline
- **02:50:32Z**: First timeout error logged for `paygate` requests.
- **02:52:04Z**: First 503 Service Unavailable response (`upstream maintenance`) received from paygate.
- **03:12:00Z**: P1 alert fired for `payments-api` charge p95 > 8s and 62% failures.

## Root Cause
The third-party payment gateway (`paygate.example`) is experiencing downtime/maintenance, returning request timeouts and 503 Service Unavailable errors. Since the circuit breaker on `payments-api` is turned off, requests hang for up to the 8-second timeout threshold, degrading the API gateway and user experience.

## Evidence
- Log entries showing repeated timeouts: `paygate request timeout after 8000ms url=https://api.paygate.example/charges`
- Log entries showing upstream maintenance: `paygate 503 Service Unavailable body='upstream maintenance'`
- Metrics: `payments-api` error rate jumped to 64.5% and latency p95 rose to 8.17s.

## Remediation
Enable the circuit breaker on `payments-api` to fail fast and prevent thread/connection exhaustion while the third-party vendor resolves the outage.

## Follow-ups
- Escalate to the `paygate` vendor to check status on maintenance.
- Review default circuit breaker settings and alerting thresholds for third-party dependencies.