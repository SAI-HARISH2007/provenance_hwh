# Incident Report: inventory-api OOMKilled Loop

## Summary
At 2026-08-30T03:12:00.000Z, an alert fired for `inventory-api` due to pod restarts and error rates. Investigation revealed that the recently deployed `inventory-1.10.0` version introduced an unbounded in-process SKU cache that leaks memory, leading to repeated OOMKilled events (exit code 137) and service degradation.

## Timeline
- **2026-08-30T01:37:00.000Z**: `inventory-1.10.0` deployed ("adds in-process hot-item cache").
- **2026-08-30T02:12:00.000Z**: Redis failover to replica during maintenance.
- **2026-08-30T02:42:00.000Z onwards**: `inventory-api` container repeatedly exits with OOMKilled (code 137), `mem_pct` reaches ~98.5%.
- **2026-08-30T03:12:00.000Z**: Alert fires (`pod restarts 6 in 10m; 22% errors`).

## Root Cause
`memory_leak_oom`: The in-process cache added in `inventory-1.10.0` lacks an eviction policy / size limit, accumulating SKU entries in memory until the container exceeds its memory limit and is terminated by the kernel (OOMKilled, exit code 137).

## Proposed Remediation
Roll back the deployment of `inventory-api` to the previous stable version (`inventory-1.9.x` or prior stable release / rolling back `inventory-1.10.0`).
