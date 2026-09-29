# Incident Report: Payments-API Rate Limiting (HTTP 429)

## Summary
At 2026-08-30T03:12:00Z, `payments-api` experienced a 38% failure rate due to HTTP 429 (Too Many Requests) responses from the upstream payment vendor (PayGate). The root cause was an unthrottled one-off refund backfill job executed by the `worker` service, which exhausted the shared API rate limit quota (600 requests/minute).

## Timeline
- **2026-08-30T02:46:00Z**: `worker` deployed with a one-off refund backfill job (18k refunds at concurrency 32), sharing the production PayGate API key.
- **2026-08-30T02:47:26Z**: First `429 Too Many Requests` error logged in `payments-api`.
- **2026-08-30T03:12:00Z**: Alert fires indicating `charge_failed 38% (HTTP 429 from vendor)`.

## Root Cause
The `worker` service ran a high-concurrency background job directly calling the payment vendor's `/refunds` endpoint using the same production API key utilized by `payments-api`, consuming the entire rate-limiting pool and starving live customer transactions.

## Evidence
- Recent changes log showing the worker backfill deployment at concurrency 32 sharing the production key.
- Frequent `429 Too Many Requests` error logs referencing the shared API key limit (`pk_live_…c9`).
- Spike in `payments-api` error rate up to ~38% starting shortly after the worker deploy.

## Remediation
1. Pause or throttle the background refund backfill job in the `worker` service.
2. Ensure background jobs use separate API credentials or implement strict rate-limiting/token-bucket backoff.

## Follow-ups
- Separate API keys/quotas between background batch workers and real-time user-facing APIs.
- Add concurrency limits and rate-limiting safeguards to background migration/backfill scripts.