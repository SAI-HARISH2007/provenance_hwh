# Incident Report: payments-api HTTP 429 Rate Limiting

## Summary
At 2026-08-30T03:12:00.000Z, the `payments-api` service experienced a degradation with 38% of charge attempts failing due to HTTP 429 (Too Many Requests) responses from the `PayGate` vendor. The root cause is a concurrent background refund backfill job running on the `worker` service that exhausts the vendor API rate limit sharing the production API key.

## Timeline
- **02:46:00Z**: Worker service deploys a one-off refund backfill job (18k refunds) at concurrency 32, calling PayGate directly with the shared API key.
- **02:47:26Z**: First `429 Too Many Requests` error logged in `payments-api` due to rate-limit exhaustion.
- **03:12:00Z**: Alert fires indicating `charge_failed 38% (HTTP 429 from vendor)`.

## Root Cause
The `worker` service's high-concurrency refund backfill job is consuming the shared rate limit quota (`600/min` for key `pk_live_…c9`), leaving insufficient quota for `payments-api` transactions.

## Evidence
- Recent changes log showing the worker backfill deployment at concurrency 32.
- Continuous `429 Too Many Requests` error logs from `payments-api` citing the shared API key limit.

## Remediation
1. Pause or throttle the background refund backfill job on the `worker` service.
2. Ensure dedicated vendor rate limits or separate API keys are used for background workers.

## Follow-ups
- Implement rate-limit aware clients in background batch jobs.
- Isolate API keys between transactional traffic (`payments-api`) and bulk background jobs (`worker`).
- Enable circuit breakers and proper retry/backoff mechanisms across services.