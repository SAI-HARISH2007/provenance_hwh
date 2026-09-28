# Incident Report: Orders API Write Failures Due to Full Disk

## Summary
At 2026-08-30T03:12:00Z, a P1 alert fired for `orders-api` showing a 44% error rate on write operations. Investigation revealed that PostgreSQL disk storage reached 100% capacity due to unarchived WAL segments (`pg_wal` consuming 138GB), resulting in PostgreSQL error `53100` (`disk_full`).

## Timeline
- **2026-08-29T22:02:00Z**: S3 credentials rotated for wal-archive bucket (infra change by ops-bot).
- **2026-08-30T02:47:00Z**: `orders-api` version `orders-3.9.0` deployed (batch order inserts).
- **2026-08-30T02:49:37Z**: First `SQLSTATE 53100 disk_full` error logged by `orders-api`.
- **2026-08-30T03:12:00Z**: P1 alert fires.

## Root Cause
Postgres disk space is exhausted (`disk_full`). Following the S3 credential rotation on August 29th, WAL archiving (`wal-g wal-push`) has been failing, causing PostgreSQL to retain WAL files instead of recycling them. The high volume of database writes from the new `orders-3.9.0` batch insert deploy accelerated WAL generation until `/var/lib/postgresql` reached 100% capacity (200GB/200G), blocking further writes with error `53100`.

## Evidence
- **Logs**: `orders-api` logs show repeated `ERROR orders-api: batch insert failed: SQLSTATE 53100 disk_full`.
- **Metrics**: `orders-api` error rate jumped from ~0.4% to ~44% exactly when disk filled.
- **Probe (DB)**: `postgres` reports writes failing with `ERROR 53100 disk_full; 8,612 WAL segments awaiting archive`.
- **Probe (Disk)**: `/var/lib/postgresql` is at 100% capacity with `pg_wal` taking 138GB and growing at 0.9G/min.

## Proposed Remediation
1. Free disk space / address the archiving issue (or prune processed WALs / fix S3 credentials).
2. Once disk space is freed and WAL archiving resumes, PostgreSQL will automatically recycle WAL segments and resume normal write operations.
