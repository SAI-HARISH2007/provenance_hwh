# Incident Report: inventory-api Memory Leak / OOMKilled

## Summary
At 2026-08-30T03:12:00.000Z, a page fired for `inventory-api` experiencing pod restarts and a 22% error rate. Investigation revealed that the recently deployed `inventory-1.10.0` (which introduced an in-process SKU cache for hot items) has a memory leak leading to OOMKilled (exit code 137) container terminations.

## Timeline
- **2026-08-30T01:37:00.000Z**: `inventory-1.10.0` deployed ("in-process SKU cache for hot items").
- **2026-08-30T02:42:42.000Z onwards**: Containers begin exiting with code 137 (OOMKilled) repeatedly.
- **2026-08-30T03:12:00.000Z**: Alert fires as restart rate and error rate spike.

## Root Cause
**memory_leak_oom**: The in-process SKU cache added in `inventory-1.10.0` does not bound its memory growth or eviction properly (or leaks references), causing heap usage (`mem_pct`) to climb steadily until hitting container limits and triggering OOMKilled restarts (exit code 137).

## Evidence
- `get_alert`: `inventory-api` reports pod restarts (6 in 10m) and 22% errors.
- `recent_changes`: `inventory-1.10.0` deployed at 01:37 UTC.
- `query_logs`: Repeated `container exited (code 137); restarting`.
- `get_metrics`: `inventory-api.mem_pct` climbs from ~50% steadily after deploy up to 98.5%.
- `run_probe`: HTTP GET on `/healthz` confirmed 502 with `last exit OOMKilled 137, rss 2048Mi at kill`.

## Proposed Remediation
- **rollback_deploy** on `inventory-api` to previous stable version (reverting `inventory-1.10.0`). This is safe as it rolls back the faulty in-process cache implementation.
