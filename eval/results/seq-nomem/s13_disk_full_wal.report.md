# Incident Report: Postgres Disk Full due to WAL Archival Failure

## Summary
On August 30, 2026, at 03:12 UTC, `orders-api` began failing to write orders (returning SQLSTATE 53100 `disk_full` errors). Investigation revealed that the PostgreSQL data volume was at 100% capacity due to WAL files filling up (`pg_wal` reached 138GB) because WAL archiving was failing (likely due to S3 credential rotation on August 29).

## Timeline
- **2026-08-29 03:52 UTC**: WAL archiving config enabled (`archive_mode=on`, `archive_command=wal-g wal-push %p`).
- **2026-08-29 22:02 UTC**: S3 credentials rotated for wal-archive bucket.
- **2026-08-30 02:47 UTC**: `orders-api: orders-3.9.0` deployed.
- **2026-08-30 02:49 UTC**: First `SQLSTATE 53100 disk_full` errors logged in `orders-api`.
- **2026-08-30 03:12 UTC**: P1 alert fired for `orders-api` write errors.

## Root Cause
PostgreSQL disk space was entirely exhausted (`disk_full`) because `pg_wal` grew to 138GB. Because WAL archiving (`wal-g wal-push`) has been failing since S3 credentials were rotated on Aug 29, PostgreSQL could not recycle old WAL segments, eventually filling the disk and halting writes with SQLSTATE 53100.

## Evidence
- `get_alert`: `orders write errors 44% (SQLSTATE 53100) for 6m`
- `query_logs`: `orders-api` logging `batch insert failed: SQLSTATE 53100 disk_full`
- `run_probe disk postgres`: `/var/lib/postgresql: 100% used (200G/200G); /var/lib/postgresql/pg_wal = 138G, growing 0.9G/min (archive failing, segments not recycled)`

## Proposed Remediation
1. Fix or update the S3 credentials / WAL archiver environment so `wal-g` can push WAL segments successfully.
2. Free up disk space / clear processed WAL segments once archiving is restored (or safely truncate/clean WAL if archiving cannot be immediately resumed, though restoring archival auth is primary).
3. Action proposed: `free_disk_space` (and fixing the wal-archive credentials out-of-band).

## Follow-ups
- Add alerting for WAL archival failures before `pg_wal` fills the root/data volume.
- Automate S3 credential rotation sync for PostgreSQL WAL archiving.