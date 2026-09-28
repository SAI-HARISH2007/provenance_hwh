# Incident Report: Orders API Failures Due to Disk Exhaustion

## Summary
At 03:12 UTC, a P1 alert fired for `orders-api` due to an order creation failure rate of ~58%. Investigation revealed that database inserts were failing with "could not extend file" errors. The root cause is a full disk on the postgres server (100% capacity used), driven by massive Postgres log growth following the verbose query logging change deployed earlier.

## Timeline
- **01:02 UTC**: Raj configures Postgres with `log_min_duration_statement=0` to investigate slow queries.
- **02:47 UTC**: First database write failures (`could not extend file`) begin appearing in `orders-api` logs as disk space runs out.
- **02:52 UTC**: Inventory API deploys `inventory-1.9.3` (unrelated, but services are degraded).
- **03:12 UTC**: P1 alert fires for `orders-api` failure rate spike.
- **03:12 UTC**: Probe confirms `/var/lib/postgresql` is at 100% capacity (200G/200G), with `/var/lib/postgresql/log` consuming 96G and growing at 1.1G/min.

## Root Cause
`disk_full`: Enabling `log_min_duration_statement=0` logged every single SQL statement executed by Postgres at maximum verbosity. Over ~2 hours, this generated 96GB of logs, entirely filling the Postgres data/log volume (200GB total) and preventing Postgres from extending data files.

## Evidence
1. **Logs**: `orders-api` logs flooded with `ERROR orders-api: insert failed: could not extend file "base/16384/2619"`.
2. **Probe**: `run_probe` on `postgres` (disk) returned: `/var/lib/postgresql: 100% used (200G/200G); /var/lib/postgresql/log = 96G, growing 1.1G/min`.
3. **Recent Changes**: Change at 01:02 UTC enabled `log_min_duration_statement=0`.
4. **Metrics**: `orders-api` error rate jumped from ~0.4% to ~60% around the time writes failed.

## Proposed Remediation
Free disk space by clearing/truncating the bloated Postgres log files and reverting `log_min_duration_statement` config, allowing database writes to resume.
