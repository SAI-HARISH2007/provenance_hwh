# Incident Report: inventory-api Memory Leak and Out-Of-Memory Restarts

## Summary
At 2026-08-30T03:12:00.000Z, the `inventory-api` service experienced severe instability with a 22% error rate and 6 pod restarts within 10 minutes due to memory exhaustion. The root cause was traced to the recently deployed in-process hot-item cache (`inventory-1.10.0`), which lacks size bounding and eviction policies, causing an uncontrolled memory leak and extreme GC pressure.

## Timeline
- **2026-08-30T01:37:00Z**: `inventory-1.10.0` deployed, introducing the in-process SKU cache.
- **2026-08-30T02:49:52Z**: First `gc pressure: heap ... rss growing` warnings appear in logs.
- **2026-08-30T03:12:00Z**: Alert triggered for `inventory-api` pod restarts (6 in 10m) and elevated error rate (22%).

## Root Cause
Unbounded in-process caching introduced in version `inventory-1.10.0` without TTL or maximum capacity enforcement, leading to OOM-killer pod terminations under memory pressure.

## Evidence
- Recent deployment log: `[deploy] inventory-api: inventory-1.10.0: in-process SKU cache for hot items`
- Metric spikes: `inventory-api` memory utilization reached 98.5% with 6 pod restarts.
- Log warnings showing rampant heap growth prior to restarts: `WARN inventory-api: gc pressure: heap 99945MB rss growing`

## Remediation
- Roll back `inventory-api` to the previous stable version (`inventory-1.9.x` or remove the unbonded in-process cache implementation).

## Follow-ups
1. Implement strict LRU eviction and maximum size/item limits for any in-memory caches.
2. Add integration and load tests covering memory stability before releasing caching updates.