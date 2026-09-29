# Incident Report: orders-api Timeouts and Postgres Lock Contention

## Summary
At 2026-08-30T03:12:00.000Z, `orders-api` experienced a P1 alert for 35% timeouts on `order_create` with p95 latency reaching 5s. Investigation revealed migration 0143 ran a non-concurrent `CREATE INDEX` on `orders(customer_id)`, which acquired an `AccessExclusiveLock` on the `orders` table and has been blocking writes and reads for 16 minutes, causing connection pool exhaustion and timeouts.

## Timeline
- **02:55:00Z**: Migration 0143 runs `CREATE INDEX` (non-concurrent) on `orders(customer_id)` as part of `orders-3.8.1-rc` deploy hook.
- **03:12:00Z**: `orders-api` alerts fire due to 35% timeouts and p95 5s latency.

## Root Cause
Migration lock contention: A non-concurrent `CREATE INDEX` statement (`pid 48112`) is holding an `AccessExclusiveLock` on the `orders` table, causing 74 database connections to wait and exhausting the Postgres connection pool.

## Evidence
- Postgres probe shows: `96/100 connections; 74 waiting on AccessExclusiveLock held by pid 48112 (CREATE INDEX orders_customer_id_idx, running 16m, 38% done)`
- Recent changes show migration 0143 executing a non-concurrent index creation at 02:55Z.

## Proposed Remediation
Terminate the blocking migration query (`pid 48112`) to release the `AccessExclusiveLock` on the `orders` table. Once terminated, concurrent queries will unblock and the connection pool will recover. Afterwards, the index creation should be re-attempted concurrently (`CREATE INDEX CONCURRENTLY`).

## Follow-ups
1. Ensure all future migrations use `CREATE INDEX CONCURRENTLY` to avoid table-level locking in production.
2. Review deploy hook practices to prevent running blocking DDL during normal operations.