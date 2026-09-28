# Incident Report: orders-api Timeouts Due to Migration Lock Contention

## Summary
At 2026-08-30T03:12:00.000Z, `orders-api` began experiencing 35% error rates and p95 latencies exceeding 5 seconds due to statement timeouts. The root cause was a non-concurrent `CREATE INDEX` on the `orders` table introduced in migration 0143, which acquired an `AccessExclusiveLock` on the `orders` table and blocked all incoming queries from `orders-api`.

## Timeline
- **02:55:00Z**: Migration 0143 executed (`ALTER TABLE orders ADD COLUMN gift_note TEXT DEFAULT ''; CREATE INDEX (non-concurrent) on orders(customer_id)`).
- **02:52:39Z - 03:12:00Z**: `orders-api` queries began timing out after 5000ms due to waiting on the table lock.
- **03:12:00Z**: Alert fired for `orders-api` (`35% timeouts on order_create; p95 5s`).
- **03:15:00Z**: Investigation confirmed 74 connections waiting on PID 48112 (`CREATE INDEX orders_customer_id_idx`).

## Root Cause
`migration_lock_contention`: A non-concurrent index creation (`CREATE INDEX orders_customer_id_idx`) acquired an `AccessExclusiveLock` on the `orders` table. Because `orders` is heavily accessed by `orders-api`, all transactions attempting to read or write to `orders` queued behind the index build, exhausting connection pool time limits and hitting the 5000ms statement timeout.

## Evidence
- `recent_changes`: Migration 0143 ran at 02:55:00Z without CONCURRENTLY.
- `run_probe` (`postgres`): Showed 96/100 connections used, with 74 queries waiting on `AccessExclusiveLock` held by pid 48112 (`CREATE INDEX orders_customer_id_idx`, running 16m, 38% done).
- `query_logs` (`orders-api`): Frequent `canceling statement due to statement timeout (5000ms)` errors.

## Proposed Remediation
Terminate the blocking query (PID 48112) via `terminate_blocking_query` to immediately release the `AccessExclusiveLock` on the `orders` table and restore normal database access for `orders-api`. In follow-up, the migration should be rewritten to use `CREATE INDEX CONCURRENTLY`.
