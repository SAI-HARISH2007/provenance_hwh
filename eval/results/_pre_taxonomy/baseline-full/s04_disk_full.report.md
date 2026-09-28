# Incident Report: Orders API Outage Due to Disk Full

## Summary
At 2026-08-30T03:12:00Z, the `orders-api` service experienced a P1 alert due to a 58% failure rate on order creations. The root cause was identified as Postgres running out of disk space (`postgres.disk_pct` reached 100%), which prevented database writes and file extensions.

## Timeline
- **01:02**: Postgres config updated (`log_min_duration_statement=0`) contributing to accelerated disk usage.
- **02:46**: `inventory-api` starts logging database I/O errors.
- **02:47**: `orders-api` starts logging insert failures (`could not extend file`).
- **03:12**: P1 Alert fired for `orders-api` error rate.

## Root Cause
Postgres disk exhaustion (`disk_full`), driven in part by verbose statement logging enabled earlier in the day, leading to 100% disk utilization and complete blocking of database write operations.

## Evidence
- `postgres.disk_pct` metric ramped up from 41% to 100% over the last 30 minutes.
- `orders-api` logs show repeated errors: `insert failed: could not extend file "base/16384/2619"`.
- `inventory-api` logs show `reservation write failed: database I/O error`.

## Remediation
Free disk space on the Postgres volume (e.g., clearing stale logs or vacuuming/pruning excessive logging data from `log_min_duration_statement=0`), then revert the verbose logging configuration.

## Follow-ups
1. Revert `log_min_duration_statement` to a higher threshold or disable it.
2. Implement disk utilization alerting well before 100% threshold.
3. Review log rotation and retention policies for Postgres.