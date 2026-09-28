# Incident Report: Orders-API High Latency due to Redis Cache Eviction Stampede

## Summary
At 2026-08-30T03:12:00Z, a P2 alert fired for `orders-api` due to p95 latency reaching 3.9s (threshold 800ms). Investigation revealed that a recent feature deployment (`orders-3.8.1` at 02:27 UTC) introduced caching for product bundles, adding ~1.5GB of new keys. This exceeded Redis's 2GB `maxmemory` limit, triggering continuous LRU evictions (~47,000 keys/min), tanking the cache hit rate from ~100% to ~31%, and causing a severe cache eviction stampede that overloaded PostgreSQL and spiked `orders-api` p95 latency.

## Timeline
- **2026-08-30T02:27:00Z**: `orders-3.8.1` deployed (adds product bundle caching, ~1.5GB keys).
- **2026-08-30T03:02:00Z**: Redis memory reaches 102.7% limit; evictions spike to ~47,000 keys/min; cache hit rate drops from ~100% to ~31%.
- **2026-08-30T03:02:16Z**: `orders-api` p95 latency jumps from ~120ms to ~3,900ms.
- **2026-08-30T03:12:00Z**: Alert fires for `orders-api` p95 latency.

## Root Cause
**cache_eviction_stampede**: The new feature added 1.5GB of keys to a 2GB Redis instance, causing constant key churn/eviction under maxmemory policy `allkeys-lru`. This destroyed cache effectiveness and caused a stampede of cache misses hitting the database.

## Evidence
- `recent_changes`: `orders-3.8.1: cache product bundles (adds ~1.5GB of new keys)` deployed at 02:27 UTC.
- `redis.used_memory_pct`: Rose past 100% to 102.7% starting around 03:02 UTC.
- `redis.evicted_keys_per_min`: Jumped from 0 to ~47,000–49,000 evictions per minute at 03:02 UTC.
- `redis.hit_rate_pct`: Dropped from ~100% to ~31% simultaneously.
- `orders-api.latency_p95_ms`: Jumped from ~120ms to ~4,000ms at 03:02 UTC.

## Proposed Remediation
Increase Redis cache memory (`increase_cache_memory`) to accommodate the new product bundle keys and stop the eviction loop. This is completely safe and non-disruptive as it avoids restarting Redis or rolling back functionality.

## Follow-ups
- Right-size Redis `maxmemory` permanently to account for data growth.
- Add memory usage and eviction alerts for Redis.
