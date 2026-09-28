# Incident Report: payments-api Rate Limited by PayGate

## Summary
At 2026-08-30T03:12:00.000Z, a P2 page fired for `payments-api` indicating a 38% charge failure rate due to HTTP 429 (Too Many Requests) from the upstream payment vendor (PayGate). Investigation revealed that a one-off worker deploy (`worker-1.4.1`) launched at 02:46:00 UTC to backfill 18k refunds at concurrency 32 shared the same production PayGate API key, exhausting the 600 req/min rate limit and starving regular API traffic.

## Timeline
- **00:12 UTC**: `payments-api` deployed (retry idempotency keys).
- **02:46 UTC**: `worker-1.4.1` deployed with a one-off refund backfill job (18k refunds, concurrency 32) sharing the production API key.
- **02:47 UTC**: First PayGate 429 Too Many Requests error logged in `payments-api`.
- **02:49 UTC**: Error rate spikes from ~0.4% to ~38%.
- **03:12 UTC**: P2 Alert fires for `payments-api`.

## Root Cause
Third-party rate limited (`third_party_rate_limited`): The upstream payment vendor (PayGate) rate-limited the shared API key due to high-volume refund requests originating from a concurrent worker backfill job (`worker-1.4.1`), causing `payments-api` requests to fail with HTTP 429 errors.

## Evidence
1. **Alert & Metrics**: `payments-api` error rate jumped from ~0.4% to ~38% starting right after 02:46 UTC.
2. **Recent Changes**: `worker-1.4.1` deployed at 02:46:00 UTC running a backfill of 18k refunds at concurrency 32, sharing the production API key.
3. **Logs**: `payments-api` error logs repeatedly show `paygate 429 Too Many Requests retry-after=30 (limit 600/min for key pk_live_…c9)`.
4. **Probe**: HTTP probe to `https://api.paygate.example/status` returned 200, but the vendor dashboard confirmed key `…c9` at 100% capacity with 92% of calls coming from `worker/1.4.1`.

## Proposed Remediation
Enable the circuit breaker on `payments-api` (`enable_circuit_breaker`) to gracefully handle vendor rate-limiting and protect client requests while the worker backfill job completes or is paused. This is safe as it isolates the payments application from upstream rate-limiting failures and prevents cascading timeouts.

## Follow-ups
1. Pause or throttle the worker refund backfill job to respect rate limits.
2. Separate API keys for batch/worker backfill jobs from customer-facing API traffic.
3. Keep the circuit breaker configuration reviewed for vendor outages and rate limits.
