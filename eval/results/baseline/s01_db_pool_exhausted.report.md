# Incident Report: API Gateway 5xx Errors on Checkout

## Summary
At 2026-08-30T03:12:00Z, the `api-gateway` triggered a P1 alert for elevated 5xx error rates (12.2%) on `/v1/checkout`. Investigation revealed that the underlying database (`postgres`) connection pool was exhausted, causing downstream requests to `orders-api` to time out.

## Timeline
- **2026-08-30T02:34:00Z**: Worker concurrency increased from 8 to 64.
- **2026-08-30T03:12:00Z**: `api-gateway` fires P1 alert due to 5xx error rate exceeding threshold (12% for 5m).
- **2026-08-30T03:12:00Z**: Incident response initiated.

## Root Cause
The `postgres` connection pool is exhausted (`connections_used` at 99.3% of 100 max connections). This starvation prevents `orders-api` from acquiring database connections during checkout operations, resulting in 504/503 gateway timeouts and high P95 latency (>5s).

## Evidence
- Postgres metrics show `connections_used` at 99.29%.
- Orders-api error rate spiked to 31.18% with p95 latency jumping to over 5.1 seconds.
- API Gateway logs consistently show: `POST /v1/checkout HTTP/1.1 503 5012ms upstream=orders-api`.

## Remediation
1. Increase the maximum connection pool limit on PostgreSQL or adjust connection pooling configuration in services.
2. Scale or optimize connection usage, particularly reviewing recent changes in background workers or high-concurrency jobs.

## Follow-ups
- Implement connection pooling proxies (e.g., PgBouncer) to protect PostgreSQL from connection exhaustion.
- Review connection pool limits across all microservices relative to replica counts and database max_connections.