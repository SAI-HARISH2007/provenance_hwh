# Incident Report: Orders and Inventory Failures due to Disk Exhaustion

## Summary
At 2026-08-30T03:12:00.000Z, `orders-api` fired a P1 alert for a 58% failure rate on `order_create`. Investigation revealed that Postgres disk space was 100% exhausted due to massive log growth, causing database write failures (`could not extend file`) across `orders-api` and `inventory-api`.

## Timeline
- **2026-08-30T01:02:00.000Z**: Config change enabled `log_min_duration_statement=0` on Postgres for slow query investigation, causing every single SQL statement to be logged.
- **2026-08-30T02:45-02:50.000Z**: Postgres disk filled up completely (100%), with `/var/lib/postgresql/log` reaching 96GB and growing at 1.1G/min.
- **2026-08-30T03:12:00.000Z**: `orders-api` P1 alert fired due to failed inserts.

## Root Cause
`disk_full`: Enabling `log_min_duration_statement=0` filled the Postgres data/log volume to 100%, preventing file extension and database writes.

## Evidence
- `run_probe disk postgres`: `/var/lib/postgresql: 100% used (200G/200G); /var/lib/postgresql/log = 96G, growing 1.1G/min`
- `orders-api` logs: `insert failed: could not extend file "base/16384/2619"`
- `recent_changes`: Config change `log_min_duration_statement=0` at 01:02 UTC.

## Proposed Remediation
Free disk space by clearing or truncating the excessive Postgres query logs and disabling/reverting the overly verbose `log_min_duration_statement` setting.
