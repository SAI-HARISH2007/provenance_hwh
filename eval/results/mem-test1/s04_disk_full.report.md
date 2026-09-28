# Incident Report: orders-api & inventory-api Failures Due to Full Disk

## Summary
At 2026-08-30T03:12:00Z, `orders-api` fired a P1 alert for 58% failure rate on `order_create`. Investigation revealed that `inventory-api` and `orders-api` were both failing with database errors (`database I/O error` and `could not extend file ...: No space left on device` equivalents in Postgres). A probe on the postgres disk confirmed that `/var/lib/postgresql` was at 100% capacity due to a massive Postgres log directory (96GB, growing at 1.1GB/min), caused by a recent config change that enabled verbose logging (`log_min_duration_statement=0`).

## Timeline
- **01:02 UTC**: Config change shipped: `postgres: enable log_min_duration_statement=0` by raj.
- **02:45 UTC**: `inventory-api` begins logging `database I/O error`.
- **02:47 UTC**: `orders-api` begins logging `could not extend file "base/16384/2619"`.
- **03:12 UTC**: P1 alert fires for `orders-api` order_create failure rate (58%).
- **03:15 UTC**: Investigation and disk probe confirm Postgres disk is 100% full due to log growth.

## Root Cause
`disk_full`: The PostgreSQL data disk filled up completely (100% used) because verbose query logging (`log_min_duration_statement=0`) filled up `/var/lib/postgresql/log` to 96GB. This prevented PostgreSQL from extending database files, causing write failures across services (`orders-api`, `inventory-api`).

## Evidence
1. **Logs**: `orders-api` logs show `could not extend file "base/16384/2619"`. `inventory-api` logs show `database I/O error`.
2. **Probe**: `run_probe disk postgres` returned `postgres /var/lib/postgresql: 100% used (200G/200G); /var/lib/postgresql/log = 96G, growing 1.1G/min`.

## Proposed Remediation
Free disk space on the postgres server (specifically by clearing or truncating the oversized log files in `/var/lib/postgresql/log` and reverting/adjusting the log configuration if necessary). This action is safe and directly addresses the disk exhaustion.
