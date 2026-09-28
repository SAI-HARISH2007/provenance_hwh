# Incident Report: Orders API Outage Due to Disk Full

## Summary
At 2026-08-30T03:12:00Z, `orders-api` experienced a P1 incident with an order creation failure rate of ~58%. Investigation revealed that the underlying PostgreSQL disk was 100% full due to extreme log growth caused by a recent configuration change enabling verbose query logging.

## Timeline
- **2026-08-30T01:02:00Z**: Config change enabled `log_min_duration_statement=0` on Postgres for slow-query investigation.
- **2026-08-30T02:47:16Z**: First database insertion failures begin (`could not extend file`).
- **2026-08-30T02:52:00Z**: Inventory-api deployed (unrelated).
- **2026-08-30T03:12:00Z**: P1 alert fires for orders-api failure rate.

## Root Cause
`disk_full`: The `log_min_duration_statement=0` configuration change logged every single query executed against PostgreSQL, filling `/var/lib/postgresql/log` to 96GB and exhausting the 200GB disk (`100% used`). This prevented Postgres from extending data files for new orders.

## Evidence
- `get_alert`: `orders-api` error rate high, multiple services degraded.
- `recent_changes`: Postgres config change setting `log_min_duration_statement=0`.
- `query_logs` on `orders-api`: `ERROR orders-api: insert failed: could not extend file "base/16384/2619"`
- `run_probe` (disk): `postgres /var/lib/postgresql: 100% used (200G/200G); /var/lib/postgresql/log = 96G, growing 1.1G/min`

## Proposed Remediation
Free disk space by purging or truncating old Postgres log files, and revert `log_min_duration_statement`.

## Follow-ups
1. Revert `log_min_duration_statement` to default or higher threshold.
2. Set up log rotation and disk space monitoring/alerting.
