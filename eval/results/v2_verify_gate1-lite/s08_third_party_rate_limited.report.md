# Incident Report: payments-api Rate Limited by PayGate Vendor

## Summary
At 2026-08-30T03:12:00.000Z, the `payments-api` service started failing with `charge_failed 38% (HTTP 429 from vendor)`. Investigation revealed that a one-off refund backfill job deployed to the `worker` service at 02:46:00.000Z was making concurrent requests directly to the PayGate vendor API (`/refunds`) using the shared production API key, exhausting the rate limit (600 requests/minute) shared by `payments-api`.

## Timeline
- **02:46:00.000Z**: `worker` deployed with `worker-1.4.1: one-off refund backfill job (18k refunds) at concurrency 32`, sharing the production API key with `payments-api`.
- **02:47:28.000Z**: `payments-api` logs first `429 Too Many Requests` from PayGate (`retry-after=30`).
- **02:49:00.000Z**: `payments-api` error rate spikes from ~0.4% to ~38%.
- **03:12:00.000Z**: Alert fires.

## Root Cause
`third_party_rate_limited`: The shared production PayGate API key was rate-limited (600/min) due to high-concurrency refund backfill requests from the `worker` service, causing `payments-api` transactions to fail with HTTP 429.

## Proposed Remediation
Enable the circuit breaker on `payments-api` (`enable_circuit_breaker`) to gracefully handle upstream vendor rate limits and prevent cascading failures while the background refund backfill completes or is throttled.
