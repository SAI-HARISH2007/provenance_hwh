# Incident Report: Payments-API Outage due to Paygate Third-Party Outage

## Summary
At 2026-08-30T03:12:00Z, a page fired for `payments-api` indicating charge p95 latency > 8s and 62% failure rate. Investigation revealed that the third-party payment gateway (`api.paygate.example`) is experiencing an outage and returning 503 Service Unavailable / timing out.

## Timeline
- **2026-08-29T23:12:00Z**: `payments-api` deployed version `payments-2.14.0` (retry idempotency keys).
- **2026-08-30T02:52:00Z**: `payments-api` begins seeing 503 errors and request timeouts from `paygate`.
- **2026-08-30T03:12:00Z**: Alert fires (`payments-api` charge p95 > 8s and 62% failures).

## Root Cause
Third-party outage (`third_party_outage`). The external payment gateway `api.paygate.example` is down/degraded, causing all downstream payment requests to time out and fail.

## Evidence
1. `payments-api` logs show repeated errors: `paygate 503 Service Unavailable body='upstream maintenance'` and `paygate request timeout after 8000ms url=https://api.paygate.example/charges`.
2. `payments-api` metrics show `error_rate_pct` jumping from ~0.4% to ~64.5% and `latency_p95_ms` jumping from ~120ms to ~8170ms at 02:52Z.
3. `run_probe` on `https://api.paygate.example` confirmed HTTP 503 in 8001ms with vendor status page reporting "Degraded performance — investigating".

## Proposed Remediation
Enable circuit breaker (`enable_circuit_breaker`) on `payments-api` toward `paygate` to fail fast, protect system resources, and escalate to vendor (`escalate_to_vendor`).