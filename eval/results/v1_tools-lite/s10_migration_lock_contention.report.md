# Incident Report: Orders API Timeouts Due to Migration Lock Contention

## Summary
At 02:55 UTC on 2026-08-30, migration 0143 ran as part of the `orders-3.8.1-rc` deploy hook, executing a non-concurrent `CREATE INDEX` on the `orders` table (`orders(customer_id)`). This acquired an `AccessExclusiveLock` on the `orders` table, blocking subsequent read and write queries from the `orders-api`. Consequently, `orders-api` experienced a surge in P95 latency (spiking to 5.2 seconds) and 35% timeouts (`canceling statement due to statement timeout (5000ms)`).

## Timeline
- **02:55:00 UTC**: Migration 0143 executes `CREATE INDEX (non-concurrent) on orders(customer_id)` via deploy hook.
- **02:52:39 - 02:56:56 UTC**: `orders-api` begins logging statement timeouts (note: log timestamps start slightly prior due to query duration/logging granularity, fully spiking right after migration).
- **02:55+: UTC**: `orders-api` p95 latency jumps from ~120ms to ~5200ms.
- **03:12:00 UTC**: Alert fires on `orders-api` for 35% timeouts and p95 latency of 5s.

## Root Cause
**Migration lock contention** (`migration_lock_contention`). A non-concurrent index creation on a heavily-accessed production table (`orders`) acquired an exclusive lock, causing database connection exhaustion/waiting queries and query timeouts across the API.

## Evidence
- `recent_changes`: Shows migration 0143 running at 02:55:00 UTC: `ALTER TABLE orders ADD COLUMN gift_note TEXT DEFAULT ''; CREATE INDEX (non-concurrent) on orders(customer_id)`.
- `query_logs`: `orders-api` flooded with `ERROR orders-api: canceling statement due to statement timeout (5000ms)`.
- `get_metrics`: `orders-api.latency_p95_ms` jumped from ~120ms to ~5.2s right around 02:55-02:56 UTC.
- `run_probe`: Postgres probe confirms: `96/100 connections; 74 waiting on AccessExclusiveLock held by pid 48112 (CREATE INDEX orders_customer_id_idx, running 16m, 38% done)`.

## Proposed Remediation
Terminate the blocking query (`pid 48112`) to release the `AccessExclusiveLock` on the `orders` table. This is safe because dropping/terminating the uncompleted non-concurrent index creation query immediately relieves lock contention, unblocking queries and restoring normal service operation. Afterward, the migration should be rewritten to create the index concurrently (`CREATE INDEX CONCURRENTLY`).

## Follow-ups
1. Enforce linting/checks in CI/CD migrations to forbid non-concurrent index creation on production tables.
2. Re-run index creation using `CREATE INDEX CONCURRENTLY` during off-peak hours.