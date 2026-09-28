# Incident Report: payments-api Rate Limited by Vendor

## Summary
At 2026-08-30T03:12:00.000Z, the `payments-api` service alerted on a 38% error rate due to HTTP 429 (Too Many Requests) from the third-party payment vendor (`PayGate`). This was triggered by a concurrent one-off refund backfill job running in the `worker` service that shared the primary production API key.

## Timeline
- **02:46:00 UTC**: One-off refund backfill job deployed on `worker` (concurrency 32, calling PayGate directly).
- **02:47:30 UTC**: First `429 Too Many Requests` error logged by `payments-api`.
- **02:50:00 UTC**: `payments-api.error_rate_pct` spikes from ~0.4% to ~38%.
- **03:12:00 UTC**: P2 alert fired: `charge_failed 38% (HTTP 429 from vendor)`.

## Root Cause
The `worker` service executed an 18k refund backfill at a concurrency of 32 using the shared production API key (`pk_live_...c9`). This consumed the vendor's per-minute rate limit (600 requests/min), starving legitimate customer checkout traffic in `payments-api`.

## Evidence
- Recent deployment log indicating the backfill job calling PayGate directly with the shared API key.
- `payments-api` logs showing recurring `paygate 429 Too Many Requests retry-after=30 (limit 600/min for key pk_live_…c9)` errors.
- Metric jump in `payments-api.error_rate_pct` to ~38% matching the start of the backfill.

## Remediation
As an offline backfill job, rate-limiting or completion will naturally resolve the issue shortly. No direct service rollback or restart is required, but future background scripts must use dedicated API keys or rate limit themselves accordingly.

## Follow-ups
1. Ensure internal guidelines prohibit background backfills from utilizing primary production keys without dedicated rate-limiting.
2. Implement separate API credentials or rate limiters for batch/worker jobs.