# Incident Report: Orders-API Latency Spike Due to Cache Eviction Stampede

## Summary
On August 30, 2026 at 03:12 UTC, `orders-api` suffered a severe latency spike, with p95 latency reaching 3.9s (threshold 800ms). The root cause was a cache eviction stampede in Redis caused by version `orders-3.8.1`, which introduced product bundle caching amounting to ~1.5GB of new keys, overwhelming Redis's `maxmemory` limit of 2GB. This dropped the cache hit rate from ~98% to ~31%, causing massive key evictions (~48k/min) and driving up database load and API latency.

## Timeline
- **2026-08-30T02:27:00Z**: `orders-api` deployed version `orders-3.8.1` ("cache product bundles (adds ~1.5GB of new keys)").
- **02:42 UTC**: Redis cache hit rate drops from ~95-100% to ~31%, and evicted keys spike from 0 to ~47k/min.
- **02:42 UTC**: `orders-api` p95 latency jumps from ~120ms to ~3.9s.
- **2026-08-30T03:12:00Z**: P2 alert fires for `orders-api` p95 latency.

## Root Cause
**cache_eviction_stampede**: Redis `maxmemory` was configured to 2GB, but the new deployment added ~1.5GB of bundle keys on top of existing cached data, exceeding capacity. This caused continuous LRU evictions (`maxmemory_policy: allkeys-lru`), destroying the cache hit rate and sending a flood of heavy database queries (`SELECT ... FROM orders JOIN bundles`) to Postgres, driving Postgres CPU to 97% and causing high API response latencies.

## Evidence
1. **Recent Changes**: `orders-3.8.1` explicitly states it adds ~1.5GB of new cache keys.
2. **Redis Metrics**: `hit_rate_pct` plummeted from ~98% down to ~31%; `evicted_keys_per_min` jumped from 0 to ~48,000 evictions/min.
3. **Orders-API Metrics**: `latency_p95_ms` correlated instantly with the start of Redis evictions, jumping from ~120ms to ~3.9s.
4. **Redis Config**: `maxmemory` is set to `2gb`.
5. **Database Probe**: Postgres connection pool and CPU are heavily saturated with heavy join queries retrieving un-cached bundle data.

## Proposed Remediation
- **Action**: `increase_cache_memory`
- **Target**: `redis`
- **Why it is safe**: Increasing Redis cache memory (e.g. from 2GB to 4GB) accommodates the newly added ~1.5GB bundle keys without evicting existing working set data. It requires no service restarts, code rollbacks, or data migrations, and immediately restores the cache hit rate.

## Follow-ups
1. Review cache sizing methodology for feature rollouts that introduce substantial new caching volumes.
2. Optimize bundle payload size or implement TTLs/tiered caching if necessary.