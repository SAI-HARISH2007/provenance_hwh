# Incident Report: orders-api Failures due to Disk Full on PostgreSQL

## Summary
At 2026-08-30T03:12:00Z, `orders-api` fired a P1 alert for a 58% failure rate on order creation. Investigation revealed that PostgreSQL ran out of disk space (`100% used`) due to an excessively verbose query log configuration (`log_min_duration_statement=0`), which caused database write failures (`could not extend file`) across the database and crippled order creation.

## Timeline
- **01:02:00Z**: Config change applied to `postgres`: `log_min_duration_statement=0` enabled for slow-query investigation.
- **02:47:16Z**: `orders-api` begins logging insert failures (`could not extend file`).
- **02:52:00Z**: `inventory-api` deploy (`inventory-1.9.3`).
- **03:12:00Z**: P1 alert fires for `orders-api` (`order_create failure rate 58%`).
- **03:12:00Z (Investigation)**: Disk probe on PostgreSQL confirms `/var/lib/postgresql` is at 100% usage (200G/200G), with postgres logs taking up 96GB and growing at 1.1GB/min.

## Root Cause
`disk_full` (PostgreSQL disk exhaustion caused by a debug logging configuration change that logged every statement, filling the disk with logs and preventing database file extension).

## Evidence
- `recent_changes`: `postgres: enable log_min_duration_statement=0 for slow-query investigation`
- `query_logs` (orders-api): Repeated `ERROR orders-api: insert failed: could not extend file "base/16384/2619"` starting around 02:47Z.
- `run_probe` (disk, target=postgres): `/var/lib/postgresql: 100% used (200G/200G); /var/lib/postgresql/log = 96G, growing 1.1G/min`.

## Proposed Remediation
1. Free disk space on PostgreSQL by truncating or rotating/deleting excess logs in `/var/lib/postgresql/log` (or reverting the `log_min_duration_statement` configuration change).
2. Safe because cleaning up bloated log files and reverting unnecessary verbose query logging restores normal disk capacity and allows PostgreSQL to extend data files normally.

## Follow-ups
- Revert `log_min_duration_statement` or raise the threshold to avoid flooding logs.
- Add disk usage alerts for PostgreSQL at 80% and 90% thresholds.
