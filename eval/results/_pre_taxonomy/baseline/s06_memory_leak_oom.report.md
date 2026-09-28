# Incident Report: inventory-api Memory Exhaustion and Restarts

## Summary
At 2026-08-30T03:12:00Z, an alert fired for `inventory-api` due to frequent pod restarts (6 restarts in 10 minutes) and an error rate spike of ~22%. The root cause was traced back to a recent deployment introducing an unbounded in-process SKU cache causing severe memory leaks and OOM kills.

## Timeline
- **01:37** - `inventory-1.10.0` deployed with an in-process SKU cache for hot items.
- **02:49 - 03:04** - Frequent GC pressure warnings logged as heap usage approaches limits.
- **03:12** - Alert fires for `inventory-api` pod restarts and 22% error rate.

## Root Cause
A memory leak caused by the newly introduced in-process cache in `inventory-1.10.0`, resulting in OOM-induced pod restarts and degraded service.

## Evidence
- Recent deployment: `inventory-api: inventory-1.10.0: in-process SKU cache for hot items`
- Metric spikes: `inventory-api` memory at 95.1% and 6 pod restarts.
- Log warnings: Repeated `WARN inventory-api: gc pressure: heap ... rss growing` messages.

## Remediation
- Roll back `inventory-api` to the previous stable version (`inventory-1.9.x`).

## Follow-ups
1. Audit in-process caching logic to ensure proper TTL/eviction and size limits.
2. Add memory utilization alerts before pods hit OOM thresholds.