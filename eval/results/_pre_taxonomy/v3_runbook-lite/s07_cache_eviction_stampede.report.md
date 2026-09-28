# Incident Report: orders-api Latency Spike due to Cache Eviction Stampede

## Summary
On 2026-08-30 at 03:12 UTC, `orders-api` experienced a p95 latency spike to 3.9s (threshold 800ms), causing `api-gateway` to report degraded status. The root cause was a recent deploy of `orders-api` (version `orders-3.8.1`) which added product bundle caching (~1.5GB of new keys) exceeding the Redis cache memory limit (`maxmemory` = 2gb), triggering massive cache eviction (approx. 48,000 keys/min) and dropping the cache hit rate from ~100% to ~31%.

## Timeline
- **02:27 UTC**: `orders-api` version `orders-3.8.1` deployed with cache product bundles feature (adding ~1.5GB of keys).
- **02:30 UTC**: Redis memory usage rapidly climbs, hitting 102.7%, and cache eviction rate spikes to ~48,000 keys/min. Cache hit rate drops from ~100% to ~31%.
- **03:12 UTC**: `orders-api` p95 latency breaches 800ms threshold (reaching 3.9s), triggering the P2 page.

## Root Cause
**Cache eviction stampede** (`cache_eviction_stampede`). The new feature in `orders-3.8.1` added approximately 1.5GB of cached data, which exceeded the 2GB Redis `maxmemory` limit when combined with existing cache usage. This resulted in continuous thrashing and eviction of active keys under the `allkeys-lru` policy, causing high latency in `orders-api` as it repeatedly falls back to slower data sources.

## Evidence
1. **`recent_changes`**: `orders-api: orders-3.8.1: cache product bundles (adds ~1.5GB of new keys)`
2. **`redis.used_memory_pct`**: Climbed from ~60% to 102.7% following the deploy and remained pegged.
3. **`redis.evicted_keys_per_min`**: Jumped from 0 to ~48,000 evictions/min starting immediately after the deploy.
4. **`redis.hit_rate_pct`**: Dropped from ~95-100% down to ~31%.
5. **`get_config` (redis)**: Confirmed `maxmemory` is set to `2gb`.
6. **`run_probe`**: Confirmed `orders-api` health endpoint returns 503 due to severe request latency.

## Proposed Remediation
Increase Redis cache memory (`increase_cache_memory`) to accommodate the new product bundle cache and stop the eviction stampede.

## Follow-ups
- Review caching sizing guidelines for new features before deployment.
- Consider setting up cache memory alerting before limits are reached.