# Incident Report

## Summary
Starting at 02:55 UTC on 2026-08-30, `orders-api` experienced a 35% error rate and p95 latencies exceeding 5 seconds due to statement timeouts caused by database locking.

## Timeline
- **02:55:00Z**: Migration `0143` runs via the deploy hook for `orders-3.8.1-rc`, performing a non-concurrent `CREATE INDEX` on `orders(customer_id)` along with an `ALTER TABLE`.
- **02:55:07Z+**: `orders-api` logs begin flooding with statement timeouts (5000ms).
- **03:12:00Z**: P1 alert fires for `orders-api` reporting 35% timeouts.

## Root Cause
A non-concurrent index creation (`CREATE INDEX` without `CONCURRENTLY`) acquired an exclusive lock on the `postgres` `orders` table, blocking concurrent transactions and causing statement timeouts and lock contention (`locks_waiting: 74`).

## Evidence
- Recent changes show migration `0143` executing a non-concurrent index creation at `02:55:00.000Z`.
- Logs show repeated `canceling statement due to statement timeout (5000ms)`.
- Postgres metrics show `locks_waiting` spiked to 74.

## Remediation
Terminate the blocking index creation or DDL query on the postgres database to release locks on the `orders` table, and re-run the index creation using `CREATE INDEX CONCURRENTLY` in a future migration.

## Follow-ups
- Update CI/CD migration checks to forbid non-concurrent index creation on large production tables.
- Review connection pool and statement timeout configurations.