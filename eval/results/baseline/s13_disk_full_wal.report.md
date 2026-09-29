# Incident Report: Orders-API Write Failures

## Summary
At 2026-08-30T03:12:00.000Z, `orders-api` began experiencing a high rate of write errors (SQLSTATE 53100). Investigation revealed that the backing PostgreSQL database has reached 100% disk utilization, preventing any further write operations.

## Timeline
- **2026-08-29T03:52:00.000Z**: WAL archiving enabled on PostgreSQL (`archive_mode=on`, `wal-g`).
- **2026-08-29T22:02:00.000Z**: S3 credentials rotated for the WAL archive bucket.
- **2026-08-30T02:47:00.000Z**: `orders-3.9.0` deployed with batch order inserts.
- **2026-08-30T03:12:00.000Z**: Alert fires for `orders-api` write errors (44%).

## Root Cause
The PostgreSQL data/WAL disk is completely full (`disk_pct: 100`), resulting in storage exhaustion errors (`SQLSTATE 53100 disk_full`). This is likely compounded by WAL archiving issues or rapid table/WAL growth following recent batch operations.

## Evidence
- PostgreSQL disk metric shows `disk_pct: now 100`.
- `orders-api` logs repeatedly output: `ERROR orders-api: batch insert failed: SQLSTATE 53100 disk_full`.

## Remediation
1. Immediately free disk space on the PostgreSQL instance (e.g., clean up stale WAL files if archiving is blocked due to the credential rotation or investigate large temporary files/bloat).
2. Expand the PostgreSQL disk volume if necessary.

## Follow-ups
- Verify WAL-G archiving status and S3 connectivity following the recent credential rotation.
- Implement disk space monitoring and alerting prior to reaching 100% capacity.