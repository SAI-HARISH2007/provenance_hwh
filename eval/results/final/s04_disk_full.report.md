# Incident Report: Orders API Failures Due to Disk Full on Postgres

## Summary
On 2026-08-30 at 03:12 UTC, `orders-api` experienced a 58% failure rate when creating orders, and `inventory-api` / `api-gateway` were degraded. Investigation revealed that the Postgres data/log volume was 100% full, causing database I/O errors and failures to extend database files (`could not extend file`).

## Timeline
- **01:02 UTC**: Configuration change made: `postgres: enable log_min_duration_statement=0` by raj to investigate slow queries. This caused massive logging of every single database statement.
- **02:45 UTC**: Inventory writes begin failing with `database I/O error`.
- **02:47 UTC**: Orders writes begin failing with `could not extend file "base/16384/2619"`.
- **03:12 UTC**: P1 alert fires for `orders-api` order_create failure rate 58%.

## Root Cause
`disk_full`: Enabling `log_min_duration_statement=0` on Postgres caused verbose logging of all statements. Over roughly two hours, the Postgres log directory grew to 96GB, filling the 200GB disk to 100% and preventing writes or file extensions.

## Evidence
- `run_probe disk postgres`: `/var/lib/postgresql: 100% used (200G/200G); /var/lib/postgresql/log = 96G, growing 1.1G/min`
- `query_logs` for `orders-api`: `insert failed: could not extend file "base/16384/2619"`
- `query_logs` for `inventory-api`: `reservation write failed: database I/O error`
- `recent_changes`: `postgres: enable log_min_duration_statement=0`

## Proposed Remediation
Free disk space by truncating/clearing excessive logs in `/var/lib/postgresql/log` and reverting the verbose logging config (`log_min_duration_statement`).
Action: `free_disk_space` on `postgres`.
