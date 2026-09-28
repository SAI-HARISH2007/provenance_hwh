# Incident Report: inventory-api Memory Leak / OOMKilled

## Summary
At 2026-08-30T03:12:00.000Z, an alert fired for `inventory-api` due to frequent pod restarts (6 in 10 minutes) and 22% error rate. Investigation revealed that version `inventory-1.10.0`, deployed at 01:37 UTC, introduced an unbounded in-process SKU cache for hot items without eviction limits, leading to memory exhaustion (OOMKilled exit code 137).

## Timeline
- **01:37:00 UTC**: `inventory-1.10.0` deployed ("in-process SKU cache for hot items").
- **02:12:00 UTC**: Redis failover to replica during maintenance.
- **02:42:42 UTC onwards**: `inventory-api` containers repeatedly exit with code 137 (OOMKilled) as memory reaches 98.5%.
- **03:12:00 UTC**: Alert fires (`inventory-api` pod restarts 6 in 10m).

## Root Cause
`memory_leak_oom`: The newly introduced in-process SKU cache in `inventory-1.10.0` lacks bounded sizing or eviction policies, causing memory usage to grow unboundedly until the container hits its memory limit and is killed by the OOM killer (exit code 137).

## Evidence
1. **Recent Changes**: `inventory-1.10.0` shipped an in-process SKU cache at 01:37 UTC.
2. **Metrics**: `inventory-api.mem_pct` climbed steadily from ~50% to 98.5%.
3. **Logs**: `inventory-api` logs show repeated `container exited (code 137); restarting`.
4. **Probe**: `run_probe` confirmed `502 (pod restarting; last exit OOMKilled 137, rss 2048Mi at kill)`.

## Proposed Remediation
Roll back the deployment of `inventory-api` from version `inventory-1.10.0` to the previous stable version. This is completely safe as it reverts the problematic code addition while keeping existing infrastructure and database states intact.
