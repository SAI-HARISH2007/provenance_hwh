# Incident Report: Orders API Outage Due to Disk Full

## Summary
At 2026-08-30T03:12:00Z, `orders-api` and `inventory-api` experienced a surge in error rates (~58% and ~56% respectively) because the underlying Postgres database ran out of disk space (reaching 100%). This prevented table extensions and write operations.

## Timeline
- **2026-08-30T01:02:00Z**: Postgres configuration updated (`log_min_duration_statement=0`) for slow-query investigation.
- **2026-08-30T02:46:56Z**: `inventory-api` starts logging `reservation write failed: database I/O error`.
- **2026-08-30T02:47:53Z**: `orders-api` starts logging `insert failed: could not extend file "base/16384/2619"`.
- **2026-08-30T03:12:00Z**: `orders-api` error rate reaches 58%, triggering the P1 alert.

## Root Cause
The Postgres database ran out of disk space (`postgres.disk_pct` hit 100%). This was likely accelerated by excessive logging enabled earlier in the day combined with normal database growth.

## Evidence
- `postgres.disk_pct` metric shows a steady climb reaching `100`.
- `orders-api` logs: `ERROR orders-api: insert failed: could not extend file "base/16384/2619"`
- `inventory-api` logs: `ERROR inventory-api: reservation write failed: database I/O error`

## Remediation
1. Free disk space on the Postgres host (e.g., clear old log files or temporary files).
2. Revert or adjust the `log_min_duration_statement` setting to prevent excessive log generation.

## Follow-ups
- Set up disk space utilization alerting well before 100% threshold.
- Review log retention and rotation policies for database logs.