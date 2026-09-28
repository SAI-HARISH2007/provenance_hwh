# Incident Report: payments-api Degraded due to Third-Party Outage

## Summary
At 2026-08-30T03:12:00Z, `payments-api` fired a P1 alert indicating charge p95 latency exceeded 8 seconds and error rates reached ~62%. Investigation revealed that the external third-party payment gateway (`paygate`) is experiencing an outage (`503 Service Unavailable` / timeouts). Because `payments-api` has its circuit breaker turned off, requests hang for the full timeout duration (8000ms) before failing, causing cascading latency and high error rates.

## Timeline
- **2026-08-30T02:52:00Z**: Third-party `paygate` begins returning `503 Service Unavailable` and timing out.
- **2026-08-30T02:52:31Z**: `payments-api` logs initial upstream `503` errors and timeouts.
- **2026-08-30T03:12:00Z**: P1 alert fires for `payments-api` (p95 > 8s, 62% failures).
- **2026-08-30T03:15:00Z**: Probe and logs confirm third-party outage and disabled circuit breaker.

## Root Cause
**Third-party outage** (`third_party_outage`). The external payment gateway (`api.paygate.example`) is down / degraded, and `payments-api` lacks an active circuit breaker to fast-fail requests, resulting in thread/connection exhaustion and inflated p95 latency.

## Evidence
1. **Alert**: `payments-api` charge p95 > 8s and 62% failures (`get_alert`).
2. **Metrics**: Error rate jumped from ~0.4% to ~64.5% starting at 02:52Z (`get_metrics`).
3. **Logs**: Repeated errors: `paygate 503 Service Unavailable body='upstream maintenance'` and `paygate request timeout after 8000ms` (`query_logs`).
4. **Probe**: `GET https://api.paygate.example/status` returned `503` in 8001ms with vendor status page indicating degraded performance (`run_probe`).
5. **Config**: `CIRCUIT_BREAKER` is explicitly set to `"off"` in `payments-api` config (`get_config`).

## Proposed Remediation
Enable the circuit breaker on `payments-api` (`enable_circuit_breaker`) to fast-fail requests when the external payment gateway is unresponsive, protecting our system resources and reducing p95 latency. Escalate to the vendor (`paygate`) regarding their ongoing outage.

## Follow-ups
- Set up automatic circuit breaking or aggressive fallback/hedging for external payment dependencies.
- Improve external dependency health monitoring and alerting.