# Incident Report: inventory-api Memory Exhaustion and Restarts

## Summary
At 2026-08-30T03:12:00Z, the `inventory-api` service experienced continuous pod restarts due to memory exhaustion (OOM), leading to degraded status across dependent API gateways and an elevation in overall error rates.

## Timeline
- **01:37:00Z**: `inventory-1.10.0` deployed with an in-process SKU cache for hot items.
- **02:49:52Z**: First `inventory-api` GC pressure warning logged as heap consumption grows unboundedly.
- **03:07:00Z**: `inventory-api` memory reaches ~94%, pod restarts begin incrementing.
- **03:12:00Z**: Alert fires as pod restart count hits 6 and error rates spike to ~5% at the `api-gateway`.

## Root Cause
The newly introduced in-process hot-item cache in version `inventory-1.10.0` lacks proper eviction or bounded sizing, causing a severe memory leak that exhausts the container heap and triggers OOM kills.

## Evidence
- Recent deployment changelog showing `inventory-1.10.0` added an in-process SKU cache.
- Metrics show `inventory-api.mem_pct` climbing steadily from ~51% to nearly 99%.
- Logs filled with repeated warnings: `inventory-api: gc pressure: heap ... rss growing`.
- Metric `inventory-api.restarts` incrementing up to 6.

## Remediation
1. Roll back `inventory-api` to the previous stable version (`inventory-1.9.x` or remove the unbonded in-process cache).

## Follow-ups
- Implement strict maximum size limits and TTL eviction policies for any in-process caching mechanisms.
- Add automated memory usage and GC duration alerts prior to OOM thresholds.