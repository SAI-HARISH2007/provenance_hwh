# Incident Report: payments-api Third-Party Rate Limiting

## Summary
At 2026-08-30T03:12:00.000Z, a page fired for `payments-api` due to a 38% charge failure rate caused by HTTP 429 (Too Many Requests) responses from the payment vendor (PayGate). The root cause is a concurrent background refund backfill job introduced in the `worker-1.4.1` deploy, which shared the same production API key and exhausted the PayGate API rate limit (600 requests/min).

## Timeline
- **02:46:00.000Z**: `worker-1.4.1` deployed with a one-off refund backfill job (18k refunds, concurrency 32) sharing the production PayGate API key.
- **02:47:28.000Z**: `payments-api` logs first `429 Too Many Requests` from PayGate.
- **02:49:00.000Z**: Error rate metric jumps from ~0.4% to ~38%.
- **03:12:00.000Z**: P2 page fires (`charge_failed 38%`).

## Root Cause
`third_party_rate_limited`: The third-party payment gateway (`PayGate`) rate-limited the application's shared API key due to high-volume background requests from the worker's refund backfill job running at concurrency 32 alongside normal production traffic.

## Evidence
- **Recent Changes**: `worker-1.4.1` deploy note explicitly states: "one-off refund backfill job (18k refunds) at concurrency 32 ... sharing the production API key".
- **Logs**: `payments-api` logs are flooded with `paygate 429 Too Many Requests retry-after=30 (limit 600/min for key pk_live_…c9)` starting at 02:47:28.000Z.
- **Metrics**: `payments-api.error_rate_pct` spiked from 0.4% to ~38% at 02:49:00.000Z.

## Proposed Remediation
Enable the circuit breaker on `payments-api` (`enable_circuit_breaker`) to shed load and fail fast while pausing/throttling the background worker backfill job. This is safe as it isolates the payments pipeline and prevents cascading failures while the backfill job completes or is paused.
