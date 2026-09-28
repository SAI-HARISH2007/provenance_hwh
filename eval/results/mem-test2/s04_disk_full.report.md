# Incident Report: orders-api order_create failure rate

## Summary
- **Severity:** P1
- **Symptoms:** `orders-api` order_create failure rate at 58%, with `orders-api`, `inventory-api`, and `api-gateway` degraded.
- **Root Cause:** `disk_full` on the `postgres` service due to runaway log growth (`/var/lib/postgresql/log` at 96GB, partition 100% full) caused by enabling `log_min_duration_statement=0` for slow-query investigation.
- **Remediation:** Free disk space / prune postgres logs and reset `log_min_duration_statement`.

## Timeline
- 2026-08-30T01:02:00.000Z: Config change enabled `log_min_duration_statement=0` on `postgres`.
- 2026-08-30T03:12:00.000Z: P1 alert fired: `orders-api` order_create failure rate 58%.
- Investigation: Checked recent changes and disk probe on postgres, confirming `/var/lib/postgresql` is at 100% capacity due to postgres logs growing at 1.1G/min.

## Root Cause
Postgres disk usage reached 100% (`200G/200G`) because of excessive logging (`log_min_duration_statement=0`), preventing writes and causing failures across orders-api and inventory-api.

## Proposed Remediation
Execute `free_disk_space` on `postgres` (and revert `log_min_duration_statement` config).
