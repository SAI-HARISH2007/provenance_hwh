# Incident Report: orders-api Write Failures Due to Postgres Disk Full

## Summary
On August 30, 2026, at 03:12 UTC, `orders-api` experienced a P1 alert for write errors (44% error rate with SQLSTATE 53100 `disk_full`). Investigation revealed that the Postgres data directory `/var/lib/postgresql` reached 100% capacity (200G/200G), with `pg_wal` consuming 138GB due to unarchived WAL segments accumulating because archive uploads were failing.

## Timeline
- **2026-08-29 03:52 UTC**: Config change `archive_mode=on`, `archive_command=wal-g wal-push %p` applied.
- **2026-08-29 22:02 UTC**: S3 credentials for wal-archive bucket rotated.
- **2026-08-30 02:47 UTC**: `orders-api` deployed version `orders-3.9.0` (batch order inserts).
- **2026-08-30 03:12 UTC**: P1 alert fires for `orders-api` write errors (SQLSTATE 53100).
- **2026-08-30 03:15 UTC**: Investigation confirms Postgres disk usage is at 100% with 8,612 WAL segments awaiting archive.

## Root Cause
`disk_full` in the `postgres` service. Specifically, WAL archiving began failing (due to credential rotation or connectivity issues with the S3 wal-archive bucket), causing Postgres to retain WAL segments in `pg_wal` rather than recycling them. This filled the disk to 100% and triggered SQLSTATE 53100 on write transactions.

## Evidence
- `run_probe(kind=disk, target=postgres)`: `/var/lib/postgresql` at 100% used (200G/200G); `/var/lib/postgresql/pg_wal` = 138G, growing at 0.9G/min due to failed archiving.
- `run_probe(kind=db, target=postgres)`: Writes failing with `ERROR 53100 disk_full`; 8,612 WAL segments awaiting archive.
- `query_logs`: Repeated `batch insert failed: SQLSTATE 53100 disk_full` errors from `orders-api`.

## Proposed Remediation
Execute `free_disk_space` on `postgres` (or clean/resolve WAL archive backlog and reclaim disk space) to restore database write capacity.
