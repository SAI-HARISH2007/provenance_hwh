# Incident Report: Payments-API Rate Limited by PayGate due to Worker Refund Backfill

## Summary
At 2026-08-30T03:12:00.000Z, an alert fired for `payments-api` showing a 38% error rate (`charge_failed`, HTTP 429 from vendor). Investigation revealed that a background worker deploy (`worker-1.4.1`) running a one-off refund backfill job at concurrency 32 was flooding the shared PayGate API key with requests, exhausting the rate limit and causing legitimate payment charges to fail with HTTP 429.

## Timeline
- **2026-08-30T02:46:00.000Z**: `worker` deployed `worker-1.4.1` with a one-off refund backfill job (18k refunds) at concurrency 32, sharing the production API key.
- **2026-08-30T03:10:00.000Z**: `payments-api` error rate spikes from ~0.4% to nearly 40%.
- **2026-08-30T03:12:00.000Z**: Alert fires indicating high charge failure rates (HTTP 429 from vendor).

## Root Cause
The root cause is **third_party_rate_limited**. The background worker (`worker-1.4.1`) executed a high-concurrency refund backfill job using the shared PayGate API key, saturating the rate limit (600 req/min) and causing incoming payment charges from `payments-api` to be rate-limited (HTTP 429).

## Evidence
- **Alert**: `payments-api` page for `charge_failed 38% (HTTP 429 from vendor)`.
- **Recent Changes**: `worker-1.4.1` backfill job at concurrency 32 sharing production API key.
- **Metrics**: `payments-api.error_rate_pct` jumped from 0.4% to ~38.6%.
- **Probe (`run_probe http`)**: Confirmed PayGate vendor itself is healthy (`status -> 200`), but the rate-limit dashboard showed the API key at 100% of 600/min with 92% of calls originating from `user-agent worker/1.4.1`.

## Proposed Remediation
Update worker configuration (`update_config`) to throttle or pause the refund backfill job (reducing concurrency or pausing batch processing) to relieve pressure on the shared PayGate API key, allowing normal payments traffic to resume. (Action target: `worker`).

## Follow-ups
1. Implement separate API keys or rate-limit budgets for batch/backfill jobs versus real-time production traffic.
2. Add backfill concurrency throttling or off-peak scheduling requirements.
