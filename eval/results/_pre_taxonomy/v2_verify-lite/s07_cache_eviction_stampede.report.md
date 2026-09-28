# Incident Report: orders-api Latency Spike and Redis Exhaustion

## Summary
At 2026-08-30T03:12:00Z, a P2 page fired for high p95 latency in `orders-api` (reaching 4.1s against an 800ms threshold). The root cause was a recent deploy (`orders-3.8.1`) that introduced product bundle caching, adding ~1.5GB of new keys to Redis. Because Redis was configured with a 2GB limit and `allkeys-lru` eviction, the new cache volume overwhelmed memory, causing continuous heavy key eviction (~48k evicted keys/min) and dropping the cache hit rate from ~100% to ~31%. This cache eviction stampede caused downstream database query amplification and latency spikes across `orders-api`.

## Timeline
- **02:27 UTC**: `orders-api` deployed version `orders-3.8.1` (cache product bundles, adding ~1.5GB of new keys).
- **02:27 - 03:00 UTC**: Redis memory usage rapidly climbs from ~60% to 100%+, hitting the 2GB cap. Evictions spike to ~48,000 keys/min and hit rate drops from ~100% to ~31%.
- **03:04 UTC**: `orders-api` p95 latency jumps from ~120ms to ~3,900ms.
- **03:12 UTC**: P2 alert fires for `orders-api` p95 latency.
- **03:12 UTC+**: Incident investigation confirms cache eviction stampede caused by `orders-3.8.1`.

## Root Cause
**Cache Eviction Stampede** triggered by a bad configuration / feature addition in `orders-3.8.1` (`cache_eviction_stampede`). The application cache footprint exceeded Redis capacity (`maxmemory 2gb`), leading to thrashing, low hit rates, and database load.

## Evidence
1. **Recent Changes**: `orders-api: orders-3.8.1: cache product bundles (adds ~1.5GB of new keys)` deployed at 02:27:00.000Z.
2. **Redis Memory**: `redis.used_memory_pct` went from ~60% to 102.7% immediately following the deploy.
3. **Redis Evictions**: `redis.evicted_keys_per_min` went from 0 to ~48,000/min.
4. **Redis Hit Rate**: `redis.hit_rate_pct` collapsed from ~100% to ~31%.
5. **Orders API Latency**: `orders-api.latency_p95_ms` spiked from 120ms to ~4,056ms right after the deploy.

## Proposed Remediation
Roll back the `orders-api` deployment to version `orders-3.8.1`'s predecessor (`orders-3.8.0`) to remove the excessive bundle caching keys and restore normal Redis hit rates and latency.

## Follow-ups
1. Review sizing requirements for product bundle caching before re-introducing.
2. Adjust Redis memory limits or cache TTLs if large object caching is required.
3. Add memory and hit rate alerts for Redis cache tiers.