# Incident Report: Payments API Rate Limited by Vendor

## Summary
At 2026-08-30T03:12:00.000Z, the `payments-api` service triggered an alert due to a 38% charge failure rate returning HTTP 429 errors from the vendor (PayGate). Investigation revealed that a concurrent background job in the `worker` service was exhausting the shared API rate limit.

## Timeline
- **00:12**: `payments-api` deployed version `payments-2.14.0` (retry idempotency keys).
- **02:46**: `worker` deployed version `worker-1.4.1` with a high-concurrency (32) refund backfill job (18k refunds) calling PayGate directly using the shared production API key.
- **02:47**: First rate limit (429 Too Many Requests) errors logged in `payments-api` due to API key saturation.
- **03:12**: Alert fires: `charge_failed 38% (HTTP 429 from vendor)`.

## Root Cause
The `worker` service deployment introduced a high-concurrency refund backfill job that saturated the shared PayGate API key rate limit (600 requests/min), starving legitimate transaction requests from `payments-api`.

## Evidence
- Recent changes log showing the worker backfill job deployment at 02:46.
- Persistent `paygate 429 Too Many Requests` log entries matching the time of the worker deployment.
- Error rate spike on `payments-api` reaching ~38%.

## Remediation
- Rollback or stop the offending background job/deployment on the `worker` service to immediately free up API rate limit quota.

## Follow-ups
- Ensure background jobs and backfill scripts utilize dedicated API keys or rate limiters.
- Implement circuit breakers and better isolation for third-party vendor integrations.