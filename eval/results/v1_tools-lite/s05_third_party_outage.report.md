# Incident Report: Payments API Degradation

## Summary
At 2026-08-30T03:12:00.000Z, a P1 alert fired for `payments-api` indicating that charge p95 latency exceeded 8 seconds and error rates reached ~62%. Investigation revealed that the third-party payment gateway (`paygate.example`) is experiencing an outage/degraded performance returning 503 Service Unavailable and timing out after 8000ms.

## Timeline
- **2026-08-30T02:42:00.000Z**: Feature flag `new_pricing_engine` updated (unrelated).
- **2026-08-30T02:52:31.000Z**: `payments-api` logs first `paygate 503 Service Unavailable` and subsequent request timeouts.
- **2026-08-30T03:12:00.000Z**: P1 alert fired due to elevated p95 latency (>8s) and high failure rate (~62%).

## Root Cause
**Third-party outage / rate limiting**: The external payment gateway provider (`api.paygate.example`) is returning 503 errors and timing out, causing downstream request accumulation and high failure rates in `payments-api`.

## Evidence
- `query_logs` for `payments-api` with `level: ERROR` shows frequent errors: `paygate 503 Service Unavailable body='upstream maintenance'` and `paygate request timeout after 8000ms url=https://api.paygate.example/charges`.
- `get_metrics` for `payments-api` shows error rate jumping from <0.5% to ~64.5% and p95 latency jumping from ~120ms to ~8.2s starting at 02:52 UTC.
- `run_probe` (`http`) to `https://api.paygate.example/charges` confirmed vendor status: `503 in 8001ms; vendor status page: 'Degraded performance — investigating'`.
- `get_config` for `payments-api` shows `CIRCUIT_BREAKER` is currently `off`.

## Proposed Remediation
Enable the circuit breaker on `payments-api` (`enable_circuit_breaker` action) and escalate to the vendor (`escalate_to_vendor`). Enabling the circuit breaker prevents thread/connection pool exhaustion and fast-fails requests while the third-party vendor is degraded. This is safe as it isolates our service from external upstream failures.
