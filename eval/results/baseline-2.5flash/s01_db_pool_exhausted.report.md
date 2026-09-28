## Incident Report: High 5xx Rate on /v1/checkout

### Summary
At 03:12 UTC, an alert fired indicating a 12% 5xx error rate on the `/v1/checkout` endpoint of the `api-gateway` service. Investigation revealed that the `orders-api` service was experiencing high latency and error rates due to the `postgres` database connection pool being exhausted. This was triggered by a recent deploy to the `worker` service, which significantly increased its email job concurrency.

### Timeline
*   **2026-08-30T02:34:00Z**: `worker` service deployed, increasing email job concurrency from 8 to 64.
*   **2026-08-30T02:52:48Z**: First `api-gateway` 503 errors observed for `/v1/checkout` requests, timing out after 5012ms while waiting for `orders-api`.
*   **2026-08-30T03:07:00Z (approx)**: 5xx rate on `/v1/checkout` exceeds 2% threshold.
*   **2026-08-30T03:12:00Z**: P1 alert fired for `api-gateway` 5xx rate.

### Root Cause
The root cause is `db_connection_pool_exhausted` in the `postgres` database. The `worker` service's deploy at 02:34:00Z, which increased email job concurrency from 8 to 64, led to a surge in database connection requests. This exhausted the `postgres` connection pool (99.295 connections used out of 100 max), preventing the `orders-api` from acquiring necessary database connections. As a result, `orders-api` requests experienced severe latency (P95 5191.84ms) and high error rates (31.185%), causing `api-gateway` to time out (5012ms) and return 503 errors for `/v1/checkout` requests.

### Evidence
*   **Alert**: `api-gateway` reported a 12% 5xx rate on `/v1/checkout`.
*   **Metrics - orders-api**: `error_rate_pct` jumped from 0.397% to 31.185%, and `latency_p95_ms` spiked from 117.548ms to 5191.84ms.
*   **Metrics - postgres**: `connections_used` increased from 38.154 to 99.295, reaching the `max_connections` limit of 100.
*   **Recent Changes**: A `worker` deploy at 02:34:00Z increased email job concurrency from 8 to 64.
*   **Logs - api-gateway**: Showed frequent `503 5012ms upstream=orders-api` errors for `/v1/checkout` requests, indicating upstream timeouts.
*   **Config - api-gateway**: `upstream_timeout_ms` is set to 5000ms, consistent with the 5012ms timeouts observed in logs.

### Remediation
**Action**: `rollback_deploy`
**Target**: `worker`

The `worker` service deploy that increased email job concurrency should be immediately rolled back to restore the previous concurrency setting (8). This will reduce the load on the Postgres connection pool and allow `orders-api` to function correctly.

### Follow-ups
1.  **Post-mortem**: Conduct a post-mortem to understand why the `worker` deploy was not adequately tested for database connection impact.
2.  **Resource Monitoring**: Implement more granular monitoring for database connection pool usage per service to identify resource contention earlier.
3.  **Connection Pool Sizing**: Review and potentially adjust the `postgres` `max_connections` and individual service connection pool sizes, especially for `worker` and `orders-api`, to better handle peak loads.
4.  **Circuit Breakers/Rate Limiting**: Evaluate implementing circuit breakers or rate limiting on the `worker` service's database interactions to prevent it from overwhelming shared resources.