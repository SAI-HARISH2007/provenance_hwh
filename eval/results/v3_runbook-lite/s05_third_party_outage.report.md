# Incident Report: payments-api degradation due to external paygate outage

## Summary
At 2026-08-30T03:12:00.000Z, `payments-api` fired a P1 alert (`charge p95 > 8s and 62% failures`). Investigation revealed that the third-party payment gateway (`api.paygate.example`) is experiencing an outage / upstream maintenance, returning 503 errors and timing out requests. Because the circuit breaker was disabled (`off`), `payments-api` continued calling the failing vendor, causing high latency (p95 > 8s) and request failures across gateway and payment services.

## Timeline
- **02:52Z**: `payments-api` logs begin showing 503 errors and request timeouts (8000ms) from `api.paygate.example`.
- **02:55Z**: Vendor status page confirms: `Degraded performance — investigating`.
- **03:12Z**: P1 Alert fires (`payments-api` charge p95 > 8s and 62% failures).

## Root Cause
`third_party_outage` — The third-party payment gateway (`api.paygate.example`) is experiencing degraded performance / maintenance, and `payments-api` lacks an active circuit breaker to fail fast.

## Evidence
- `query_logs`: Frequent `503 Service Unavailable` and `request timeout after 8000ms url=https://api.paygate.example/charges` entries.
- `run_probe` (`http`, `https://api.paygate.example`): Returned `503` in 8001ms with vendor status page `Degraded performance — investigating`.
- `get_config` (`payments-api`): Confirmed `"CIRCUIT_BREAKER": "off"`.

## Proposed Remediation
Enable the circuit breaker on `payments-api` (`enable_circuit_breaker`) to allow failing fast while the third-party vendor is down, preventing thread/connection exhaustion and high latency in our services. Escalate to the vendor as well.

## Follow-ups
- Enable automated circuit breakers with adaptive trip thresholds for third-party integrations.
- Review retry idempotency key handling to ensure retries do not exacerbate downstream vendor load during outages.
