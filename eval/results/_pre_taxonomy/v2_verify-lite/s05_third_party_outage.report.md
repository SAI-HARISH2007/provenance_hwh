# Incident Report: Payments API Degradation Due to Paygate Outage

## Summary
At 2026-08-30T03:12:00Z, `payments-api` fired a P1 alert indicating that the charge p95 latency exceeded 8 seconds and error rates reached ~64%. Investigation revealed that the third-party payment gateway (`paygate.example`) is experiencing a degraded performance / outage, returning `503 Service Unavailable` and timing out requests after 8000ms.

## Timeline
- **2026-08-30T02:52:31Z**: `payments-api` logs first record of `paygate 503 Service Unavailable` error responses.
- **2026-08-30T02:53:09Z**: First payment request timeout errors start appearing in `payments-api` logs.
- **2026-08-30T03:12:00Z**: P1 alert fires for `payments-api` (`charge p95 > 8s and 62% failures`).
- **Present**: Probe against `https://api.paygate.example/charges` confirms external vendor outage (`503` in 8001ms, vendor status page reports "Degraded performance — investigating").

## Root Cause
Third-party outage (`third_party_outage`). The external payment gateway `paygate.example` is failing and timing out, causing downstream request failures and latency spikes in `payments-api`.

## Evidence
1. **Alert**: `payments-api` P1 alert (`charge p95 > 8s and 62% failures`).
2. **Metrics**: `payments-api.error_rate_pct` jumped to ~64% and `latency_p95_ms` jumped to ~8171ms around 02:52 UTC.
3. **Logs**: `payments-api` logs show repeated errors: `paygate 503 Service Unavailable body='upstream maintenance'` and `paygate request timeout after 8000ms url=https://api.paygate.example/charges`.
4. **Probe**: `run_probe` on `https://api.paygate.example/charges` returned `503` in 8001ms with vendor status: `'Degraded performance — investigating'`.

## Proposed Remediation & Safety
- **Action**: `enable_circuit_breaker` on `payments-api` targeting `paygate`.
- **Why it is safe**: Enabling a circuit breaker stops outgoing calls to the failing third-party vendor, failing fast instead of holding threads/connections for 8 seconds, protecting `payments-api` resources from exhaustion while the vendor recovers.
- **Follow-ups**: Escalate to vendor (`escalate_to_vendor`) and monitor vendor status.