# Incident Report: Orders API Failures Due to Full Database Disk

## Summary
At 2026-08-30T03:12:00.000Z, the `orders-api` experienced a P1 alert indicating a 58% failure rate on order creations. The root cause was identified as the PostgreSQL database disk hitting 100% capacity, preventing database file extension and writes.

## Timeline
- **2026-08-30T01:02:00.000Z**: Config change enabled `log_min_duration_statement=0` on Postgres for slow-query investigation.
- **2026-08-30T02:47:53.000Z**: First database write failure logged by `orders-api` (`could not extend file`).
- **2026-08-30T03:12:00.000Z**: Alert fires as `order_create` failure rate reaches 58%.

## Root Cause
The Postgres database disk is completely full (`disk_pct: 100`). This was likely exacerbated or accelerated by verbose logging (`log_min_duration_statement=0`) enabled earlier in the shift, causing database writes/logs to exhaust available storage.

## Evidence
- Metric: `postgres: disk_pct` is at `100`.
- Logs: `ERROR orders-api: insert failed: could not extend file "base/16384/2619"` repeating across order creation attempts.

## Remediation
1. Free up disk space on the `postgres` instance (e.g., by clearing old/excessive logs or unnecessary temporary files).
2. Revert or adjust the `log_min_duration_statement` setting to prevent runaway log generation.

## Follow-ups
- Implement disk space alerting well before 100% capacity is reached.
- Review logging retention and verbosity policies on production databases.