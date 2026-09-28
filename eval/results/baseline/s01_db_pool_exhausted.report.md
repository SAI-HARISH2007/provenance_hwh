# Incident Report: API Gateway 5xx Spike on /v1/checkout

## Summary
At 2026-08-30T03:12:00.000Z, the `api-gateway` alerted on an elevated 5xx error rate (12.2%) on `/v1/checkout`. The root cause was determined to be Postgres database connection pool exhaustion (`connections_used` at 99.3%), leading to upstream timeout errors in `orders-api`.

## Timeline
- **02:34:00Z**: Worker concurrency increased from 8 to 64.
- **02:52:48Z**: First 503 error logged on `/v1/checkout` due to upstream timeout (`orders-api`).
- **03:12:00Z**: Alert fires as 5xx error rate exceeds the 2% threshold over a 5-minute window.

## Root Cause
Postgres connection pool exhaustion (`connections_used: 99.3%` against a max of `100`). This starvation prevents `orders-api` from acquiring database connections during checkout flows, causing requests to hang until the API gateway upstream timeout (5000ms) is reached.

## Evidence
- `postgres`: `connections_used` spiked to 99.295% (up from 38.1%).
- `orders-api`: `error_rate_pct` jumped to 31.18%, and p95 latency skyrocketed to over 5.1 seconds.
- `api-gateway` logs consistently show `503 5012ms upstream=orders-api` for `/v1/checkout` requests.

## Remediation
1. Increase the maximum database connection pool size or inspect and terminate leaked/idle connections on Postgres.
2. Scale out or tune connection pooling (e.g., PgBouncer) if application concurrency has grown.

## Follow-ups
- Audit database connection usage across `orders-api` and worker services.
- Implement circuit breakers or better backpressure mechanisms to prevent cascading gateway timeouts.