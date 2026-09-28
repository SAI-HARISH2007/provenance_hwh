# Incident Report: PostgreSQL Connection Pool Exhaustion

## Summary
At 2026-08-30T03:12:00Z, the `api-gateway` fired a P1 alert for 5xx errors on `/v1/checkout` reaching 12% (threshold 2%). Investigation revealed that `orders-api` was failing to acquire database connections from its connection pool (`db error: timeout acquiring connection from pool after 5000ms`), causing 503 errors on checkout requests.

## Timeline
- **2026-08-30T02:34:00Z**: `worker` deploy shipped (`worker-1.4.0: raise email job concurrency 8→64 to clear backlog`).
- **2026-08-30T02:49:03Z**: `orders-api` starts logging connection pool acquisition timeouts.
- **2026-08-30T03:12:00Z**: `api-gateway` P1 alert fires due to elevated 5xx error rate on `/v1/checkout`.

## Root Cause
**db_connection_pool_exhausted**: The recent deployment raising `worker` email job concurrency from 8 to 64 caused the worker service to consume 61 out of the 100 available PostgreSQL connections. This starved `orders-api` (leaving only 34 connections available, below its pool/operational needs), resulting in connection pool timeouts and checkout failures.

## Evidence
1. **Recent Changes**: `worker` concurrency was increased from 8 to 64 at `02:34:00Z`.
2. **Metrics & Logs**: `postgres.connections_used` spiked from 38 to 99.3 immediately following the worker change, matching the start of `orders-api` connection timeout logs at `02:49:03Z`.
3. **Probe**: `run_probe db postgres` confirmed 100/100 connections in use, with 61 held by `user=worker` and 34 by `user=orders`.

## Proposed Remediation
Increase PostgreSQL max connections / connection pool allocation (or scale down worker concurrency back to 8 / increase database pool limits) to accommodate the worker increase and restore availability to `orders-api`.
*Note*: As per safety guidelines and available actions, proposing `increase_db_pool` (or scaling/adjusting pool configuration). Since `increase_db_pool` is available in actions, we propose it to expand database capacity/pool limits.

## Follow-ups
- Review per-service connection budgeting so background workers cannot starve critical API services.
- Implement connection limits or PgBouncer connection pooling.