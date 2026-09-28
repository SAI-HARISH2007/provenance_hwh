# Incident Report: Orders-API High Latency Due to Cache Eviction Stampede

## Summary
On 2026-08-30 at 03:12 UTC, `orders-api` suffered high latency (p95 latency reaching ~4.1s against an 800ms threshold). The root cause was a recent deploy (`orders-3.8.1`) that introduced product bundle caching adding ~1.5GB of new keys, which overwhelmed the Redis cache configured with a 2GB `maxmemory` limit, leading to continuous key eviction and cache thrashing.

## Timeline
- **2026-08-30T02:27:00.000Z**: `orders-api` deployed version `orders-3.8.1` ("cache product bundles (adds ~1.5GB of new keys)").
- **02:42:00.000Z (approx)**: Redis hit rate dropped from ~100% to ~31% and evicted keys spiked from 0 to ~47,000 keys/min.
- **02:43:00.000Z (approx)**: `orders-api` p95 latency jumped from ~120ms to ~3,900ms+.
- **2026-08-30T03:12:00.000Z**: P2 alert fires for `orders-api` p95 latency.

## Root Cause
**Cache Eviction Stampede (`cache_eviction_stampede`)**: The Redis memory limit (`maxmemory: 2gb`) was insufficient for the new workload introduced by `orders-3.8.1`, which added ~1.5GB of new cached data. This caused massive continuous LRU evictions (`allkeys-lru`), tanking the hit rate and forcing `orders-api` to repeatedly hit backing stores or compute/deserialize bundle data under high contention.

## Evidence
1. **Recent Changes**: `orders-3.8.1` deploy explicitly stated it adds ~1.5GB of new keys.
2. **Redis Metrics**:
   - `hit_rate_pct`: Dropped from 90-100% down to ~31.3%.
   - `evicted_keys_per_min`: Jumped from 0 to ~47,670 evictions/min.
3. **Redis Config**: `maxmemory` is set to `2gb`.
4. **Orders-API Metrics**: `latency_p95_ms` jumped from ~120ms to ~4,056ms right alongside the Redis eviction spike.

## Proposed Remediation
Increase Redis cache memory (`increase_cache_memory`) to accommodate the new product bundle cache footprint and stop the eviction stampede. This is safe as it requires no code rollback, immediately relieves cache pressure, and restores high cache hit rates.

## Follow-ups
- Review caching strategy and memory sizing guidelines for new feature deployments.
- Add alerts for Redis eviction rates and low cache hit ratios.