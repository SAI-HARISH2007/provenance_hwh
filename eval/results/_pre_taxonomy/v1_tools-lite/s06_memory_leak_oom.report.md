# Incident Report: inventory-api Memory Exhaustion & OOM Kills

## Summary
At 2026-08-30T03:12:00.000Z, `inventory-api` began paging due to container restarts and high error rates (22%). Investigation revealed that `inventory-api` containers were repeatedly exiting with code 137 (OOM killed) due to unconstrained memory growth following the deployment of version `inventory-1.10.0`.

## Timeline
- **2026-08-30T01:37:00.000Z**: `inventory-1.10.0` deployed ("in-process SKU cache for hot items").
- **2026-08-30T02:42:42.000Z**: First OOM kill (code 137) observed in `inventory-api` logs as memory utilization reached 98.5%.
- **2026-08-30T03:12:00.000Z**: Alert fires for `inventory-api` pod restarts and error rate.

## Root Cause
**Memory Leak / OOM (`memory_leak_oom`)**: The newly introduced in-process SKU cache in `inventory-1.10.0` lacks an item eviction policy or maximum capacity limit, causing unbounded memory consumption over time until the container hits its memory limit and is OOM-killed (exit code 137).

## Evidence
- `recent_changes`: Deploy `inventory-1.10.0` added "in-process SKU cache for hot items".
- `query_logs` on `inventory-api`: Multiple log entries showing `container exited (code 137); restarting`.
- `get_metrics` (`mem_pct`): Steady climb in memory usage from ~50% up to 98.5% following the deploy.

## Proposed Remediation
**Rollback deploy (`rollback_deploy`)** of `inventory-api` to version `inventory-3.8.1` (or the previous stable version `inventory-1.9.x` / prior deployment).
*Why it is safe*: Reverting the faulty binary immediately removes the unconstrained in-process cache, restoring stable memory utilization.

## Follow-ups
1. Implement max size / LRU eviction policy for the in-process SKU cache before re-introducing it.
2. Add container memory alerts / metrics dashboards.