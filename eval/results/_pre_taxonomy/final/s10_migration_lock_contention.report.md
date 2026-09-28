# Incident Report: orders-api Timeouts due to Migration Lock Contention

## Summary
At 03:12 UTC, a page fired for `orders-api` reporting 35% timeouts and p95 latency of ~5.2 seconds. Investigation revealed that migration 0143 (run at 02:55 UTC) executed a non-concurrent `CREATE INDEX` on the `orders` table, acquiring an `AccessExclusiveLock` that blocked concurrent reads and writes to the `orders` table. This led to connection pool saturation in Postgres and severe timeouts across `orders-api` and `inventory-api`.

## Timeline
- **02:55 UTC**: Migration 0143 executed (`CREATE INDEX` non-concurrent on `orders(customer_id)`).
- **02:58 UTC**: `orders-api` latency jumps from ~120ms to over 5,000ms as requests stack up waiting for database locks.
- **03:12 UTC**: P1 alert fires for `orders-api`.

## Root Cause
`migration_lock_contention`: A non-concurrent index creation on a high-traffic table (`orders`) held an `AccessExclusiveLock` for an extended period, blocking transactions and exhausting connection limits.

## Evidence
1. **Recent Changes**: Migration `0143` was deployed at 02:55 UTC containing `CREATE INDEX (non-concurrent) on orders(customer_id)`.
2. **Metrics**: `orders-api` p95 latency spiked abruptly from 120ms to 5.2s immediately following the migration.
3. **Probe (`run_probe db postgres`)**: Confirmed `74 waiting on AccessExclusiveLock held by pid 48112 (CREATE INDEX orders_customer_id_idx, running 16m, 38% done)` with 96/100 active connections.

## Proposed Remediation
Terminate the blocking query (`pid 48112`) to release the `AccessExclusiveLock` on the `orders` table, allowing pending transactions to complete and normal traffic to resume. (The index creation should later be retried concurrently using `CREATE INDEX CONCURRENTLY`).
