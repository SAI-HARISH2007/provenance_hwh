# Incident Report: Payments API Rate Limited by Vendor

## Summary
At 2026-08-30T03:12:00Z, the `payments-api` service triggered a P2 alert due to a 38% failure rate returning HTTP 429 errors from the vendor (PayGate). Investigation revealed that a recent background worker deployment (`worker-1.4.1`) initiated a high-concurrency refund backfill job sharing the same production API key as the core application traffic, exhausting the vendor's rate limit of 600 requests per minute.

## Timeline
- **02:46:00Z**: Worker service deployed with one-off refund backfill job (18k refunds at concurrency 32).
- **02:47:26Z**: First `429 Too Many Requests` error logged by PayGate for API key `pk_live_...c9`.
- **03:12:00Z**: `payments-api` alert fires as error rate spikes to ~38%.

## Root Cause
Third-party rate limiting (`third_party_rate_limited`) caused by the `worker` service bypassing internal service isolation and directly consuming the shared vendor rate limit during a bulk backfill operation.

## Evidence
- Recent changes log indicating the refund backfill job invocation at concurrency 32.
- Vendor responses showing frequent HTTP 429 errors specifying rate limits for the shared live API key (`limit 600/min for key pk_live_…c9`).
- Metric spikes in `payments-api.error_rate_pct` reaching ~39% starting shortly after the worker backfill deployment.

## Remediation
The backfill job has naturally progressed or can be throttled/paused if still running. No explicit emergency action is required other than establishing proper rate-limit isolation and pagination for future backfills.

## Follow-ups
1. Ensure background backfill jobs use dedicated vendor API keys with distinct rate limits or implement strict internal rate limiting (token bucket) to avoid exhausting primary traffic capacity.
2. Implement circuit breakers and fallback/retry jitter within `payments-api` for upstream vendor limits.