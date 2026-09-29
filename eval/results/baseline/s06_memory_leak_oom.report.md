# Incident Report: inventory-api Memory Exhaustion and Pod Restarts

## Summary
At 2026-08-30T03:12:00.000Z, the `inventory-api` service was reported degraded with high error rates (21.8%) and repeated container restarts (6 restarts in 10 minutes). The root cause was traced back to the recent deployment introducing an unbounded in-process hot-item cache (`inventory-1.10.0`), resulting in severe memory pressure and OOM kills.

## Timeline
- **2026-08-30T01:37:00.000Z**: `inventory-1.10.0` deployed with in-process SKU cache for hot items.
- **2026-08-30T02:49:52.000Z**: First GC pressure and high heap warnings begin appearing in logs.
- **2026-08-30T03:12:00.000Z**: Alert fires for `inventory-api` pod restarts and 22% error rate.

## Root Cause
Unbounded in-process cache implementation in version `inventory-1.10.0` causing a memory leak / OOM condition.

## Evidence
- Recent change log: `inventory-api: inventory-1.10.0: in-process SKU cache for hot items`
- Metric: `inventory-api` memory usage reached 98.5% (`mem_pct: now 95.097`) with 6 pod restarts.
- Log warnings: Frequent `gc pressure: heap ...MB rss growing` messages preceding container terminations.

## Remediation
- Roll back `inventory-api` from version `inventory-1.10.0` to the previous stable version.

## Follow-ups
1. Review the in-process cache implementation for proper eviction policies (e.g., LRU, size limits, or max items).
2. Add memory utilization alerts for pre-OOM thresholds.