# Incident Report: Orders API Disk Full (WAL Accumulation)

## Summary
At 2026-08-30T03:12:00Z, an alert fired for `orders-api` due to a 44% write error rate (SQLSTATE 53100 `disk_full`). Investigation revealed that the PostgreSQL disk is 100% full due to 138GB of unarchived WAL segments piling up in `/var/lib/postgresql/pg_wal`. This was triggered following credential rotation for the WAL archive S3 bucket and high write volume from a new batch insert deployment (`orders-3.9.0`).

## Timeline
- **2026-08-29T03:52:00Z**: Config set `archive_mode=on`, `archive_command=wal-g wal-push %p`.
- **2026-08-29T22:02:00Z**: S3 credentials rotated for wal-archive bucket (`ops-bot`), causing subsequent archiving failures.
- **2026-08-30T02:47:00Z**: `orders-api: orders-3.9.0` deployed (batch order inserts).
- **2026-08-30T02:49:00Z**: `orders-api` error rate spikes from <0.4% to ~44% with `SQLSTATE 53100 disk_full`.
- **2026-08-30T03:12:00Z**: Alert fires.

## Root Cause
`disk_full` on PostgreSQL caused by WAL segment accumulation (`pg_wal` taking up 138GB out of 200GB disk). WAL archiving failed due to broken S3 credentials or archive configuration, preventing PostgreSQL from recycling old WAL files.

## Evidence
- `query_logs`: `orders-api` logs repeatedly show `ERROR orders-api: batch insert failed: SQLSTATE 53100 disk_full`.
- `get_metrics`: `error_rate_pct` jumped sharply around 02:49 from ~0.4% to 44.29%.
- `run_probe` (db): `writes failing ERROR 53100 disk_full; 8,612 WAL segments awaiting archive`.
- `run_probe` (disk): `/var/lib/postgresql: 100% used (200G/200G); /var/lib/postgresql/pg_wal = 138G, growing 0.9G/min`.

## Proposed Remediation
`free_disk_space` (specifically resolving the S3 credential/archive issue and safely clearing or allowing WAL archival to resume / pruning unneeded WAL segments) to restore free space on the PostgreSQL disk and allow writes to succeed.
