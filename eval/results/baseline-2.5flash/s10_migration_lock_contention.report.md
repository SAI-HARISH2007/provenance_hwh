## Incident Report: orders-api timeouts due to PostgreSQL Migration Lock Contention

### Summary
The `orders-api` service is experiencing a P1 alert with 35% timeouts and p95 latency of 5 seconds on the `order_create` endpoint. Investigation reveals that a recent PostgreSQL migration, specifically a `CREATE INDEX (non-concurrent)` operation on the `orders` table, has caused significant lock contention in the database. This contention is leading to a high number of waiting queries, database connection pool exhaustion, and subsequent statement timeouts in the `orders-api`.

### Timeline
*   **2026-08-30T02:42:00Z (approx)**: PostgreSQL metrics show normal `connections_used` (~37) and `locks_waiting` (0).
*   **2026-08-30T02:52:36Z**: First `canceling statement due to statement timeout (5000ms)` error observed in `orders-api` logs.
*   **2026-08-30T02:55:00Z**: PostgreSQL migration `0143` (ALTER TABLE and CREATE INDEX (non-concurrent) on orders) was initiated via a deploy hook for `orders-3.8.1-rc`.
*   **2026-08-30T02:55:00Z - 03:12:00Z**: `orders-api` error rate and latency steadily increase. PostgreSQL `connections_used` rises to ~96 and `locks_waiting` jumps to 74.
*   **2026-08-30T03:12:00Z**: P1 alert fired for `orders-api` due to 35% timeouts on `order_create` with p95 latency of 5s.

### Root Cause
The root cause is `migration_lock_contention` on the `postgres` database. The `CREATE INDEX (non-concurrent)` operation in migration `0143` on the `orders` table acquired an `ACCESS EXCLUSIVE` lock, blocking other queries to the table. This led to a backlog of database queries, exhausting the `orders-api`'s database connection pool and causing requests to timeout after 5 seconds, as configured by `DB_POOL_TIMEOUT_S`.

### Evidence
*   The alert message explicitly states "35% timeouts on order_create; p95 5s", directly matching the observed `orders-api` latency and error rate metrics.
*   `orders-api` metrics show a drastic increase in `latency_p95_ms` from ~117ms to ~5218ms and `error_rate_pct` from ~0.4% to ~36% within the last 30 minutes.
*   PostgreSQL metrics show a critical increase in `locks_waiting` from 0 to 74 and `connections_used` from ~37 to ~96 (near `max_connections: 100`), indicating severe database contention and resource exhaustion.
*   A recent change log indicates a PostgreSQL migration `0143` at `02:55:00Z` involving `ALTER TABLE orders` and `CREATE INDEX (non-concurrent) on orders(customer_id)`. A non-concurrent index creation is known to take long-held exclusive locks.
*   `orders-api` logs are filled with `ERROR orders-api: canceling statement due to statement timeout (5000ms)`, which aligns with the `DB_POOL_TIMEOUT_S: 5` configuration.

### Remediation
**Action:** `rollback_deploy`
**Target:** `orders-api`

Rolling back the `orders-api` deploy (version `orders-3.8.1-rc` which initiated the migration) is the most effective immediate action. This should terminate the ongoing migration process, release the database locks, and restore normal database operations, thereby resolving the timeouts and connection pool exhaustion.

### Follow-ups
1.  Investigate the `CREATE INDEX (non-concurrent)` operation: Determine why a non-concurrent index was chosen and if `CREATE INDEX CONCURRENTLY` could be used for future migrations to avoid blocking operations.
2.  Review migration deployment process: Ensure that blocking database migrations are carefully planned and executed during maintenance windows or with appropriate concurrency controls.
3.  Monitor `postgres` `locks_waiting` and `connections_used` metrics closely after rollback to confirm recovery.
4.  Analyze the impact on `inventory-api`'s latency, which also spiked, to understand if it was a cascading effect or a shared dependency issue.