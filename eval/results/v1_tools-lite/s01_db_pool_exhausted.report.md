# Incident Report: Orders API DB Connection Exhaustion

## Summary
On 2026-08-30 at 03:12 UTC, `api-gateway` alerted on a 12% 5xx error rate on `/v1/checkout`. Investigation revealed that `orders-api` was failing to acquire database connections from its pool due to pool exhaustion, resulting in 503 gateway timeouts.

## Timeline
- **2026-08-30T02:34:00Z**: Worker job concurrency increased from 8 to 64 to clear the email job backlog.
- **2026-08-30T02:49:03Z**: First `orders-api` error log: `db error: timeout acquiring connection from pool after 5000ms`.
- **2026-08-30T03:12:00Z**: P1 alert fires on `api-gateway` for 5xx rate exceeding 2%.

## Root Cause
`db_connection_pool_exhausted` (PostgreSQL connection pool exhausted). 
The recent worker concurrency increase (from 8 to 64) caused the `worker` service to consume the vast majority of PostgreSQL connections (61 out of 100 connections), leaving insufficient connection capacity for `orders-api` (only 34 connections), causing connection acquisition timeouts on checkout requests.

## Evidence
- `orders-api` logs: Repeated `db error: timeout acquiring connection from pool after 5000ms`.
- `postgres` metrics: `connections_used` spiked and reached 99.29%.
- `run_probe` on `postgres`: Confirmed 100/100 connections in use, with 61 held by `worker` and 34 by `orders`.

## Proposed Remediation
Increase PostgreSQL connection pool limit / max connections or scale database connection capacity (`increase_db_pool`), alongside tuning worker connection usage.