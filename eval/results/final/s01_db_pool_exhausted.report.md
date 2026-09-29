# Incident Report: PostgreSQL Connection Pool Exhaustion Caused by Worker Concurrency Increase

## Summary
On 2026-08-30 at 03:12 UTC, `api-gateway` triggered a P1 alert due to a 12% 5xx error rate on `/v1/checkout`. The root cause was PostgreSQL connection pool exhaustion (`db_connection_pool_exhausted`), caused by a recent configuration change/deploy on the `worker` service (`worker-1.4.0`) that raised its email job concurrency from 8 to 64. This consumed nearly all available database connections, starving `orders-api` of connection pool slots and causing checkout failures.

## Timeline
- **02:34 UTC**: Worker concurrency raised from 8 to 64 (`worker-1.4.0` deployment by Priya).
- **02:35 - 03:00 UTC**: PostgreSQL connections steadily climbed from ~38 to 100.
- **02:49 UTC**: `orders-api` began logging connection timeout errors (`timeout acquiring connection from pool after 5000ms`).
- **03:12 UTC**: `api-gateway` P1 alert fires (`5xx rate 12% on /v1/checkout`).

## Root Cause
- **Service**: `worker`
- **Root Cause Category**: `db_connection_pool_exhausted`
- **Mechanism**: Raising the worker job concurrency from 8 to 64 caused the worker service to open far more concurrent database connections (consuming 61 out of 100 total connections), exhausting the PostgreSQL connection pool limit and leaving insufficient connections for `orders-api` to process incoming checkout requests.

## Evidence
- `recent_changes`: At `02:34:00.000Z`, `worker` was deployed with concurrency raised `8 -> 64`.
- `get_metrics` (`postgres.connections_used`): Showed a direct climb starting right after the deploy, reaching the max limit (`99.295`).
- `run_probe` (`db` / `postgres`): Confirmed `100/100 connections in use; 61 from user=worker, 34 from user=orders, 5 superuser reserved`.
- `query_logs` (`orders-api`): Showed persistent `db error: timeout acquiring connection from pool after 5000ms`.

## Proposed Remediation
- **Action**: `update_config` (on `worker` to lower concurrency back to 8, or scale/cap its DB pool). Specifically, lowering `concurrency` back down to 8 (or an appropriate safe value like 16) restores normal connection usage.
- **Why it is safe**: Reverting the concurrency change directly addresses the resource consumer without restarting stateful services or rolling back unrelated code.

## Follow-ups
- Implement per-service connection pool limits / max connection settings in PostgreSQL (e.g. via `SET ROLE` or connection pooling / pgBouncer) to prevent background workers from starving critical user-facing APIs.
- Evaluate worker database access patterns and query efficiency.
