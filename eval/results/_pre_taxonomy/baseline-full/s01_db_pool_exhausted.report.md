# Incident Report: API Gateway 5xx Spike on /v1/checkout

## Summary
At 03:12 UTC, the `api-gateway` triggered a P1 alert for a 5xx error rate exceeding 12% on `/v1/checkout`. The root cause was identified as database connection exhaustion on the `postgres` database, triggered by high connection demand from `orders-api` following a recent worker concurrency increase.

## Timeline
- **2026-08-30T02:34:00Z**: Worker job concurrency raised from 8 to 64 to clear backlog.
- **2026-08-30T02:45:26Z**: First Postgres `FATAL: sorry, too many clients already` log appears.
- **2026-08-30T02:47:42Z**: `orders-api` begins logging DB pool timeout errors.
- **2026-08-30T03:12:00Z**: `api-gateway` 5xx error rate alert fires (12%).

## Root Cause
The concurrent job increase on the worker service alongside normal traffic caused total client connections to hit Postgres's `max_connections` limit (100). This starved `orders-api` of database connections, causing checkout requests to time out waiting for a connection from the pool (`DB_POOL_SIZE: 20`).

## Evidence
- `postgres.connections_used` climbed from ~38 to 99.3.
- Repeated Postgres logs: `FATAL: sorry, too many clients already`.
- `orders-api` logs: `db error: timeout acquiring connection from pool after 5000ms`.
- `api-gateway` error logs showing 503 responses with `upstream=orders-api`.

## Remediation
1. Increase Postgres `max_connections` or scale/tune connection pooling across services.
2. Temporarily lower worker concurrency if necessary while adjusting database resource limits.

## Follow-ups
- Review connection pool sizing across all microservices relative to database capacity.
- Implement proper rate limiting and circuit breakers on upstream dependencies.