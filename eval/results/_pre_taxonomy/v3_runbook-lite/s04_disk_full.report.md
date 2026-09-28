# Incident Report: orders-api failure due to Disk Full on PostgreSQL

## Summary
On 2026-08-30 at 03:12 UTC, a P1 alert fired for `orders-api` with a 58% failure rate on `order_create`. Investigation revealed that PostgreSQL's disk partition `/var/lib/postgresql` was 100% full due to extremely verbose query logging enabled earlier, leading to database write errors and failing order insertions/inventory reservations.

## Timeline
- **2026-08-30 01:02 UTC**: Config change applied to PostgreSQL: `log_min_duration_statement=0` enabled for slow-query investigation.
- **2026-08-30 02:45-02:49 UTC**: `inventory-api` and `orders-api` start logging database I/O errors and `could not extend file` errors.
- **2026-08-30 03:12 UTC**: P1 alert fires for `orders-api` order_create failure rate.
- **2026-08-30 03:12 UTC**: Investigation via `run_probe disk postgres` confirms disk usage is at 100% (200G/200G), with `/var/lib/postgresql/log` taking 96G and growing at 1.1G/min.

## Root Cause
**disk_full**: Enabling `log_min_duration_statement=0` logged every single executed query at maximum verbosity, rapidly filling the postgres data/log volume until free space was exhausted. When disk space reached 100%, PostgreSQL was unable to extend data files (`could not extend file`), causing all writes/inserts to fail.

## Evidence
1. `run_probe disk postgres` result: `postgres /var/lib/postgresql: 100% used (200G/200G); /var/lib/postgresql/log = 96G, growing 1.1G/min`.
2. `query_logs` for `orders-api`: `ERROR orders-api: insert failed: could not extend file "base/16384/2619"`.
3. `query_logs` for `inventory-api`: `ERROR inventory-api: reservation write failed: database I/O error`.
4. `recent_changes`: Config change on `postgres` setting `log_min_duration_statement=0`.

## Proposed Remediation
Free disk space by rotating/truncating/clearing PostgreSQL log files or reverting the verbose logging config change and cleaning up logs to restore write availability.
Action: `free_disk_space` on target `postgres`.

## Follow-ups
1. Revert or adjust `log_min_duration_statement` to a reasonable threshold (e.g., 250ms or higher) instead of 0.
2. Implement disk space monitoring and log rotation policies for the database server.