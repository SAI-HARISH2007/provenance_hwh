# Incident Report: Orders API Failures Due to Disk Full on Postgres

## Summary
At 2026-08-30T03:12:00Z, `orders-api` experienced a P1 alert due to a 58% error rate on order creation. Investigation revealed that Postgres ran out of disk space (`100% used`) due to massive query logging enabled earlier by a configuration change.

## Timeline
- **2026-08-30T01:02:00Z**: Config change enabled `log_min_duration_statement=0` on Postgres for slow-query investigation.
- **2026-08-30T02:47:16Z**: `orders-api` starts logging errors: `insert failed: could not extend file "base/16384/2619"`.
- **2026-08-30T03:12:00Z**: `orders-api` order_create failure rate alert fires.

## Root Cause
`disk_full`: Enabling `log_min_duration_statement=0` caused Postgres to log every single query, filling the disk `/var/lib/postgresql` to 100% (96GB of logs growing at 1.1G/min). This prevented Postgres from extending table files, causing all insert operations to fail.

## Evidence
- `orders-api` logs: `insert failed: could not extend file "base/16384/2619"`
- Postgres disk probe: `100% used (200G/200G); /var/lib/postgresql/log = 96G, growing 1.1G/min`
- Recent changes: `log_min_duration_statement=0` enabled at 01:02:00Z.

## Proposed Remediation
1. Free disk space by truncating/clearing excess log files in `/var/lib/postgresql/log`.
2. Revert the Postgres logging configuration (`log_min_duration_statement` back to default/disabled) to prevent immediate re-accumulation.
