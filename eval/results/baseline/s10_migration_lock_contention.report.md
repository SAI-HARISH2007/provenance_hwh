# Incident Report: Orders API Timeouts and PostgreSQL Lock Contention

## Summary
At 2026-08-30T03:12:00Z, the `orders-api` experienced a P1 alert due to 35% error rates and p95 latencies spiking to over 5 seconds. The root cause was a non-concurrent index creation migration (`CREATE INDEX`) on the `postgres` database table `orders`, which created heavy lock contention, exhausted connection pools, and triggered 5-second statement timeouts across API requests.

## Timeline
- **02:55:00Z**: Migration 0143 is executed, adding a column and performing a non-concurrent `CREATE INDEX` on `orders(customer_id)`.
- **02:55:07Z+**: `orders-api` begins logging numerous statement timeout errors (`canceling statement due to statement timeout (5000ms)`).
- **03:12:00Z**: P1 alert fired for `orders-api` due to 35% request timeouts and 5s p95 latency.

## Root Cause
A non-concurrent database index migration (`CREATE INDEX` without `CONCURRENTLY`) acquired an exclusive lock on the `orders` table, blocking concurrent transactions, causing lock contention (`locks_waiting: 74`), exhausting database connections, and causing dependent API requests to time out.

## Evidence
- Recent changes log showing non-concurrent index creation: `CREATE INDEX (non-concurrent) on orders(customer_id)`
- Postgres metrics showing high locks and connection saturation: `locks_waiting: now 74`, `connections_used: now 96.147` (max 100)
- Orders API error logs: `ERROR orders-api: canceling statement due to statement timeout (5000ms)`

## Remediation
1. Terminate the blocking migration query on the database using `pg_terminate_backend` or by canceling the active transaction.
2. Re-run the index creation using `CREATE INDEX CONCURRENTLY` during a scheduled window to prevent table-level locking.

## Follow-ups
- Update CI/CD migration linting rules to disallow non-concurrent index creation on production tables.
- Review database connection pool limits and alert thresholds for `locks_waiting`.