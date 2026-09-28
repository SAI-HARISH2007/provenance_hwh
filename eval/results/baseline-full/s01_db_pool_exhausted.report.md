# Incident Report: API Gateway 5xx Spike on /v1/checkout

## Summary
At 03:12 UTC, the `api-gateway` triggered a P1 alert due to an elevated 5xx error rate (reaching ~12%) on the `/v1/checkout` endpoint. The root cause was traced to database connection pool exhaustion on the `postgres` database, triggered by an excessive increase in background worker concurrency (`worker` email job concurrency raised from 8 to 64), which depleted available database connections and caused `orders-api` requests to time out acquiring connections.

## Timeline
- **2026-08-30T02:34:00Z**: Worker concurrency increased from 8 to 64 to clear an email job backlog.
- **2026-08-30T02:45:26Z**: First `postgres` log entry: `FATAL: sorry, too many clients already`.
- **2026-08-30T02:47:42Z**: `orders-api` begins logging connection pool timeout errors (`timeout acquiring connection from pool after 5000ms`).
- **2026-08-30T03:12:00Z**: `api-gateway` 5xx alert fires as checkout requests consistently fail via upstream `orders-api` timeouts.

## Root Cause
The recent operational change to raise the worker email job concurrency from 8 to 64 overwhelmed the database connection pool limit (`max_connections: 100`). As workers and API services competed for database connections, `postgres` began rejecting new connections (`sorry, too many clients already`), causing `orders-api` to fail when processing downstream requests from `api-gateway`'s `/v1/checkout` calls.

## Evidence
- PostgreSQL metrics show `postgres.connections_used` rising rapidly from ~38 to nearly 100 (`99.295`).
- Repeated PostgreSQL error logs: `FATAL: sorry, too many clients already`.
- `orders-api` logs showing continuous connection timeouts: `ERROR orders-api: db error: timeout acquiring connection from pool after 5000ms`.
- Concurrent change log showing `worker` concurrency raised to 64 just prior to the connection saturation.

## Remediation
1. Increase the database connection pool size or connection limits, or scale back the `worker` email job concurrency.
2. Apply the action to increase the `orders-api` DB pool size and/or tune PostgreSQL `max_connections`.

## Follow-ups
- Review connection pool sizing across all microservices relative to PostgreSQL's `max_connections`.
- Implement backpressure or rate limiting on background worker database usage to prevent sudden spikes from starving user-facing APIs.