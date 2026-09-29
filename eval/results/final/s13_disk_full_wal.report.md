# Incident Report: Orders Write Errors (SQLSTATE 53100)

## Summary
On 2026-08-30 at 03:12 UTC, a P1 alert fired for `orders-api` showing 44% write errors with SQLSTATE `53100` (`disk_full`). Investigation revealed that the PostgreSQL data volume (`/var/lib/postgresql`) is at 100% capacity because `pg_wal` has grown to 138GB with 8,612 WAL segments awaiting archive. WAL archiving is failing (likely due to S3 credential rotation or archive command config), preventing PostgreSQL from recycling WAL segments.

## Timeline
- **2026-08-29 03:52 UTC**: Postgres config updated (`archive_mode=on`, `archive_command=wal-g wal-push %p`).
- **2026-08-29 22:02 UTC**: S3 credentials rotated for `wal-archive` bucket.
- **2026-08-30 02:47 UTC**: `orders-api` deployed (version 3.9.0, batch inserts).
- **2026-08-30 02:49 UTC**: `orders-api` begins logging `SQLSTATE 53100 disk_full` errors.
- **2026-08-30 03:12 UTC**: P1 alert fires.

## Root Cause
`disk_full` (`disk_full` / `disk_full` root cause label). Specifically, PostgreSQL disk space is exhausted due to unarchived WAL segments accumulating rapidly (`pg_wal` taking 138GB, 100% disk usage), causing all database writes to fail with SQLSTATE 53100.

## Evidence
- `get_alert`: `orders-api` write errors 44% (SQLSTATE 53100).
- `run_probe db postgres`: `postgres: 44/100 connections; writes failing ERROR 53100 disk_full; 8,612 WAL segments awaiting archive`.
- `run_probe disk postgres`: `/var/lib/postgresql: 100% used (200G/200G); /var/lib/postgresql/pg_wal = 138G, growing 0.9G/min (archive failing, segments not recycled)`.
- `query_logs`: Continuous repeating logs of `orders-api: batch insert failed: SQLSTATE 53100 disk_full`.

## Proposed Remediation
Free disk space on postgres (`free_disk_space`), specifically by cleaning up/managing the accumulated WAL segments or fixing the WAL archiving pipeline so PostgreSQL can recycle segments. This is safe as it clears non-essential/already processed log backlog or restores archiving capability to resume normal WAL recycling without restarting the database.
