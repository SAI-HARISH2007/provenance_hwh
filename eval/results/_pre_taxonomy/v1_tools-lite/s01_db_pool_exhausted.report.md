# Incident Report: orders-api DB Connection Pool Exhaustion

## Summary
At 2026-08-30T03:12:00Z, `api-gateway` fired an alert for a 12% 5xx error rate on `/v1/checkout` (threshold 2%). Investigation revealed that `orders-api` was failing to acquire database connections from its pool within the 5000ms timeout, returning 503 errors to the gateway. The root cause is PostgreSQL connection pool exhaustion (100/100 connections in use), primarily driven by a recent concurrency increase on the `worker` service (`worker-1.4.0: raise email job concurrency 8->64` at 02:34 UTC) which rapidly consumed available database connections.

## Timeline
- **2026-08-30T02:34:00Z**: Worker service concurrency increased from 8 to 64 by Priya.
- **2026-08-30T02:49:03Z**: First `orders-api` log error: `timeout acquiring connection from pool after 5000ms`.
- **2026-08-30T03:12:00Z**: P1 Alert fired for `api-gateway` 5xx rate on `/v1/checkout`.

## Root Cause
`db_connection_pool_exhausted` (specifically on PostgreSQL, caused by `worker` job concurrency expansion consuming connections, leaving insufficient pool capacity for `orders-api`).

## Evidence
1. **Logs**: `orders-api` logs showed repeated `timeout acquiring connection from pool after 5000ms` errors.
2. **Metrics**: `postgres.connections_used` metric showed a sharp climb starting around 02:34 UTC, reaching 99.3%.
3. **Probe**: `run_probe` on `postgres` confirmed 100/100 connections in use (61 by `worker`, 34 by `orders`).
4. **Recent Changes**: Worker email concurrency raise (`8 -> 64`) perfectly correlated with the timing of the connection exhaustion buildup.

## Proposed Remediation
Increase PostgreSQL max connections / connection pool sizing or scale back/tune the worker concurrency to prevent worker from starving customer-facing services like `orders-api`. (Action: `increase_db_pool` on `postgres`). This is safe as it accommodates the higher worker load while restoring connection availability to web traffic.
