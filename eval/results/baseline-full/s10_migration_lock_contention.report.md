### Incident Report: Orders API Timeouts

**Summary:**
At 2026-08-30T03:12:00Z, `orders-api` experienced a 35% error rate and elevated p95 latency (~5s) due to statement timeouts caused by database lock contention.

**Timeline:**
- **02:55:00Z:** Migration `0143` runs via the `orders-3.8.1-rc` deploy hook, executing a non-concurrent `CREATE INDEX` on `orders(customer_id)` and adding a column.
- **02:53:59Z - 03:12:00Z:** Postgres logs show widespread lock waiting (`AccessShareLock`) and connection pool saturation (`connections_used` reaching ~99%).
- **02:52:36Z+:** `orders-api` begins logging `canceling statement due to statement timeout (5000ms)`.
- **03:12:00Z:** Alert fires for `orders-api` timeouts.

**Root Cause:**
Running a non-concurrent `CREATE INDEX` on an active table (`orders`) holds exclusive locks that block incoming queries from `orders-api`. This backed up the database connection pool and triggered 5-second statement timeouts.

**Evidence:**
- Recent migration added a non-concurrent index on the `orders` table.
- Metric `postgres.locks_waiting` spiked to 74.
- Metric `postgres.connections_used` peaked near max capacity (100).
- Postgres logs: `still waiting for AccessShareLock on relation 16391... after 1000.1 ms`.
- Orders API logs: `canceling statement due to statement timeout (5000ms)`.

**Remediation:**
Terminate the blocking migration/DDL query holding the lock on the `orders` table in PostgreSQL.

**Follow-ups:**
1. Modify all database migration guidelines to mandate `CREATE INDEX CONCURRENTLY` to avoid table-level locking.
2. Review connection pool and timeout settings to fail gracefully.