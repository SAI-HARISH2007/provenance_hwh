# Incident Report: orders-api DB Connection Pool Exhaustion

## Summary
At 2026-08-30T03:12:00Z, the `api-gateway` fired a P1 alert due to high 5xx error rates (12%) on `/v1/checkout`. Investigation revealed that `orders-api` was timing out trying to acquire database connections from its pool. The root cause is the recent deployment of `worker-1.4.0` at 02:34 UTC, which increased email job concurrency from 8 to 64. Each worker concurrent job holds database connections, completely exhausting the PostgreSQL connection pool (100/100 connections used, with 61 held by the worker user).

## Timeline
- **2026-08-30T02:34:00Z**: `worker` deployed (`worker-1.4.0`), raising email job concurrency from 8 to 64.
- **2026-08-30T02:34:00Z - 03:00:00Z**: PostgreSQL `connections_used` metric steadily climbs from ~38 to 99/100.
- **2026-08-30T02:53:52Z**: `orders-api` logs first `db error: timeout acquiring connection from pool after 5000ms`.
- **2026-08-30T03:12:00Z**: `api-gateway` alerts on high 5xx rate on `/v1/checkout`.

## Root Cause
`db_connection_pool_exhausted`: The worker concurrency increase to 64 caused the background workers to consume nearly all available database connections, starving `orders-api` of connections and causing checkout requests to fail.

## Evidence
1. **Recent Changes**: `worker-1.4.0` deployed at 02:34:00Z with `concurrency: 8 -> 64`.
2. **Metrics**: PostgreSQL `connections_used` spiked synchronously following the worker deploy.
3. **Probe**: `run_probe db postgres` confirmed 100/100 connections in use, with 61 held by `user=worker`.
4. **Logs**: `orders-api` logs show repeated `db error: timeout acquiring connection from pool after 5000ms`.

## Proposed Remediation
Update the `worker` configuration to lower concurrency back to 8 (or an appropriate safer limit like 16) to free up database connections for `orders-api`.
- Target: `worker`
- Action: `update_config` (setting concurrency back to 8)

## Follow-ups
1. Implement per-service connection pool limits / budgeting in PostgreSQL.
2. Review sizing guidelines before scaling background job worker concurrency in the future.