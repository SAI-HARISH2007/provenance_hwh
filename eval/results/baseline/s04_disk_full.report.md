# Incident Report: Orders API Failures Due to Disk Exhaustion

## Summary
At 2026-08-30T03:12:00.000Z, an alert fired for `orders-api` due to an order creation failure rate of 58%. Investigation revealed that the underlying PostgreSQL database storage had reached 100% capacity (`disk_pct: 100`), preventing database writes and extending files during insert operations.

## Timeline
- **2026-08-30T01:02:00.000Z**: Config change enabling `log_min_duration_statement=0` on postgres.
- **2026-08-30T02:47:53.000Z**: First database extension error (`could not extend file`) logged in `orders-api`.
- **2026-08-30T03:12:00.000Z**: P1 alert fired for `orders-api` order creation failure rate.

## Root Cause
The PostgreSQL database ran out of disk space (`disk_pct` at 100%), which caused all subsequent database `INSERT` operations to fail with file extension errors.

## Evidence
- PostgreSQL metric `disk_pct` spiked to `100`.
- Application logs continuously show: `ERROR orders-api: insert failed: could not extend file "base/16384/2619"`.

## Remediation
1. Free up disk space on the PostgreSQL storage volume (e.g., clear excessive logs, temporary files, or old table data).
2. Verify database write operations resume normally.

## Follow-ups
- Implement disk space alerting well before 100% exhaustion.
- Review database log retention and growth policies, especially following verbose logging configurations.