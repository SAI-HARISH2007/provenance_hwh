# Incident Report: Payments-API Outage

## Summary
At 2026-08-30T03:12:00.000Z, an alert fired for `payments-api` indicating high latency (p95 > 8s) and a 62% failure rate. Investigation revealed that the external payment gateway (`paygate.example`) is returning 503 Service Unavailable and timing out after 8000ms.

## Timeline
- **2026-08-30T02:50:32.000Z**: First timeout error logged from `payments-api` calling `paygate`.
- **2026-08-30T02:52:04.000Z**: First upstream 503 error received with body `upstream maintenance`.
- **2026-08-30T03:12:00.000Z**: Alert triggered for `payments-api` as failure rates spiked to ~64.5%.

## Root Cause
Third-party outage affecting the external payment gateway (`paygate.example`), which is undergoing upstream maintenance and failing to process requests in a timely manner.

## Evidence
- `paygate request timeout after 8000ms url=https://api.paygate.example/charges`
- `paygate 503 Service Unavailable body='upstream maintenance'`
- `payments-api` error rate surged to 64.5% and p95 latency increased to over 8.1s.

## Remediation
- Enable the circuit breaker on `payments-api` to prevent request pile-ups, fail fast, and protect downstream services.
- Escalate to the third-party vendor (`paygate`) regarding the ongoing maintenance/outage.

## Follow-ups
- Monitor vendor status page for resolution.
- Once the third party recovers, disable or adjust the circuit breaker thresholds.