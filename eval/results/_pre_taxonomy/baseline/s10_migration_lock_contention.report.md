# Incident Report: Orders API Timeouts

## Summary
At 2026-08-30T03:12:00.000Z, an alert fired for `orders-api` reporting 35% timeouts on `order_create` and a p95 latency of 5s. Investigation revealed that a non-concurrent index creation migration ran against PostgreSQL, causing heavy lock contention and statement timeouts.

## Timeline
- **02:55:00Z**: Migration 0143 executed (`CREATE INDEX` non-concurrently on `orders(customer_id)`).
- **02:55:18Z**: First wave of statement timeouts observed in `orders-api` logs due to database locks.
- **03:12:00Z**: P1 Alert triggered for `orders-api` due to sustained high error and latency rates.

## Root Cause
A non-concurrent index creation (`CREATE INDEX`) was run on the `orders` table during deployment. This locks the table against writes, leading to statement queueing, lock contention (`locks_waiting: 74`), and hitting the 5000ms statement timeout.

## Evidence
- Recent changes log showing migration: `CREATE INDEX (non-concurrent) on orders(customer_id)` at 02:55:00.000Z.
- Frequent `canceling statement due to statement timeout (5000ms)` errors in `orders-api` logs starting immediately after the migration.
- Postgres metric `locks_waiting` spiked to 74.

## Remediation
1. Terminate the blocking migration / conflicting queries on PostgreSQL.
2. Re-run the index creation properly using `CREATE INDEX CONCURRENTLY` once locks are cleared.

## Follow-ups
- Update migration guidelines and CI linters to prohibit non-concurrent index creation on production tables.
