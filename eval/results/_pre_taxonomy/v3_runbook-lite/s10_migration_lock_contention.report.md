# Incident Report: Orders-API Timeouts due to Migration Lock Contention

## Summary
At 2026-08-30T03:12:00.000Z, a P1 page fired for `orders-api` experiencing 35% timeouts on `order_create` (p95 latency 5s). Investigation revealed that a non-concurrent index creation migration (`CREATE INDEX ON orders(customer_id)`) executed during the deployment of `orders-3.8.1-rc` at 02:55 UTC took an `AccessExclusiveLock` on the `orders` table, blocking 74 concurrent transactions/connections.

## Timeline
- **02:55:00 UTC**: Migration 0143 runs (`ALTER TABLE orders ADD COLUMN gift_note...; CREATE INDEX ON orders(customer_id)` non-concurrently).
- **02:55 - 03:12 UTC**: `postgres.locks_waiting` spikes to 74 and stays maxed out.
- **03:12:00 UTC**: `orders-api` page fires due to connection/transaction timeouts.
- **03:15 UTC**: Investigation confirms pid 48112 holding `AccessExclusiveLock` for over 16 minutes.

## Root Cause
`migration_lock_contention`: Migration 0143 ran a non-concurrent `CREATE INDEX` on the `orders` table, acquiring an `AccessExclusiveLock` that blocked all read and write queries on `orders` (affecting `order_create`).

## Evidence
- `recent_changes`: Migration 0143 shipped at 02:55:00 UTC (`CREATE INDEX (non-concurrent) on orders(customer_id)`).
- `get_metrics` (`postgres.locks_waiting`): Spiked to 74 exactly at 02:55 UTC and remained at 74.
- `run_probe` (`db` on `postgres`): Confirmed `74 waiting on AccessExclusiveLock held by pid 48112 (CREATE INDEX orders_customer_id_idx, running 16m)`.

## Proposed Remediation
Terminate the blocking query (`terminate_blocking_query` on pid 48112) to release the lock, allowing normal queries to proceed. Subsequently, re-run the index creation properly using `CREATE INDEX CONCURRENTLY`.

## Follow-ups
- Ensure all future schema migrations use `CONCURRENTLY` for index creation on production tables.
- Update CI/CD migration linting to forbid non-concurrent index creation on large tables.
