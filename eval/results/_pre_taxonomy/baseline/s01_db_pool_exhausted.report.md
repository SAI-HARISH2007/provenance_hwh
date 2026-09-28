# Incident Report: Checkout 5xx Errors and Database Exhaustion

## Summary
At 2026-08-30T03:12:00.000Z, the `api-gateway` triggered a P1 alert for elevated 5xx error rates (12.2%) on the `/v1/checkout` endpoint. The root cause is database connection exhaustion on `postgres`, driven by high concurrency from the `orders-api` upstream service, which caused requests to timeout.

## Timeline
- **2026-08-30T02:34:00.000Z**: Worker concurrency increased from 8 to 64 (contributing factor/concurrent change).
- **2026-08-30T03:12:00.000Z**: Alert fires as 5xx rate on `/v1/checkout` exceeds 2% threshold.

## Root Cause
PostgreSQL reached maximum connection limits (`connections_used` at 99.3% of 100 max connections). Consequently, incoming queries from `orders-api` blocked or timed out, manifesting as 503 Service Unavailable errors on the `api-gateway` checkout upstream.

## Evidence
- PostgreSQL connections used: `99.295` / `100` max connections.
- `orders-api` error rate spiked to `31.185%` with p95 latency jumping to over `5191ms`.
- Gateway logs show recurring upstream timeout errors: `"POST /v1/checkout HTTP/1.1" 503 5012ms upstream=orders-api`.

## Remediation
1. Scale out the `orders-api` or adjust connection pooling settings to prevent connection starvation.
2. Alternatively, investigate long-running queries or scale database max connections if resources permit.

## Follow-ups
- Implement proper database connection pooling (e.g., PgBouncer) across all services.
- Review connection limits and timeout configurations on `orders-api`.