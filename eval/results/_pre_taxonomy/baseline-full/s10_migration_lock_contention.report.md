# Incident Report: Orders API Timeouts and PostgreSQL Lock Contention

## Summary
At 2026-08-30T03:12:00.000Z, an alert fired for `orders-api` experiencing 35% error rates and a p95 latency of 5s due to statement timeouts. The root cause was an ongoing non-concurrent index creation migration on the `orders` table (`ALTER TABLE orders ADD COLUMN ...; CREATE INDEX`), which blocked incoming queries, exhausted database connection pools, and caused widespread timeouts in dependent services.

## Timeline
- **02:55:00.000Z**: Migration 0143 run via deploy hook of `orders-3.8.1-rc`, executing a non-concurrent `CREATE INDEX` on `orders(customer_id)`.
- **02:53:59.000Z**: PostgreSQL logs first record of processes waiting for `AccessShareLock` on relation 16391.
- **02:56:19.000Z**: `orders-api` and `inventory-api` metrics show latency spiking to ~5 seconds and error rates climbing to ~35%.
- **03:12:00.000Z**: P1 alert fired for `orders-api` timeouts.

## Root Cause
A non-concurrent `CREATE INDEX` operation locks the table against writes (and some reads depending on the exact lock phase), causing concurrent transactions from the orders API to queue up behind it and eventually hit statement timeouts (5000ms).

## Evidence
- Migration log: `ALTER TABLE orders ADD COLUMN gift_note TEXT DEFAULT ''; CREATE INDEX (non-concurrent) on orders(customer_id)`
- Postgres metrics: `postgres.locks_waiting` jumped to 74 and `postgres.connections_used` spiked near `max_connections` (100).
- App logs: `orders-api: canceling statement due to statement timeout (5000ms)`

## Remediation
1. Terminate the blocking index creation or migration query (`terminate_blocking_query`).
2. Re-run the index creation using `CREATE INDEX CONCURRENTLY` in a future migration to prevent table locking.

## Follow-ups
- Update migration guidelines and linters to forbid non-concurrent index creation on production tables.
- Adjust connection pool settings and alerting thresholds for database lock wait times.