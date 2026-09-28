# Incident Report: orders-api Latency Spike and Redis Exhaustion

## Summary
At 2026-08-30T03:12:00.000Z, an alert fired for high p95 latency (3.9s) on `orders-api`. Investigation revealed that a recent deploy (`orders-3.8.1`) added approximately 1.5GB of new cache keys for product bundles, exceeding Redis capacity. This triggered continuous cache evictions, plummeted the cache hit rate to ~31%, and caused a massive surge in database fallbacks, overloading PostgreSQL and degrading both `orders-api` and `api-gateway`.

## Timeline
- **2026-08-30T02:27:00Z**: `orders-api` deployed version `orders-3.8.1` introducing product bundle caching (~1.5GB of keys).
- **2026-08-30T03:12:00Z**: `orders-api` p95 latency alert fires (3.9s).

## Root Cause
Cache eviction stampede and memory exhaustion in Redis caused by the `orders-3.8.1` deployment exceeding memory limits, resulting in severe database fallback overhead.

## Evidence
- Deploy log indicating the addition of ~1.5GB of new keys: `orders-api: orders-3.8.1: cache product bundles (adds ~1.5GB of new keys)`
- Redis memory usage at 102.7% with 47,670+ evicted keys/min.
- Drop in Redis hit rate to 31.3%.
- PostgreSQL CPU usage spiking to 98.4% due to cache-miss fallback queries.

## Remediation
1. Roll back `orders-api` to the previous stable version (`orders-3.8.0`).

## Follow-ups
- Review Redis memory sizing and eviction policies.
- Implement proper load-testing and memory profiling for features introducing large batches of cache keys.