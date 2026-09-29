# Incident Report: Orders-API Latency Spike Due to Cache Eviction Stampede

## Summary
At 2026-08-30T03:12:00Z, a P2 alert fired for `orders-api` due to elevated p95 latency (3.9s against an 800ms threshold). Investigation revealed that a recent deployment (`orders-3.8.1` at 02:27 UTC) introduced caching for product bundles, adding ~1.5GB of new keys to Redis. This pushed Redis memory usage to 102.7%, triggering massive key evictions (~48,000 keys/min) and dropping the cache hit rate from ~95% down to ~31%, causing a cache eviction stampede and severe latency degradation in `orders-api`.

## Timeline
- **2026-08-30T02:27:00Z**: `orders-api` deployed version `orders-3.8.1` (cache product bundles, adding ~1.5GB of new keys).
- **2026-08-30T02:42:00Z**: Redis memory reaches capacity (102.7%), evictions spike to ~48k/min, and hit rate drops from ~100% to ~31%.
- **2026-08-30T02:43:00Z**: `orders-api` p95 latency jumps from ~120ms to ~3.9s.
- **2026-08-30T03:12:00Z**: P2 alert fires for `orders-api`.

## Root Cause
**cache_eviction_stampede**: The newly deployed feature in `orders-3.8.1` exceeded the available Redis memory limit, causing continuous key eviction and drastically reducing cache hit rates. This forced heavy fallback queries/computations, driving up `orders-api` p95 latency.

## Evidence
- `recent_changes`: `orders-3.8.1` deployed at 02:27 with note "cache product bundles (adds ~1.5GB of new keys)".
- `redis.used_memory_pct`: Rose from ~60% to 102.7%.
- `redis.evicted_keys_per_min`: Jumped from 0 to ~48,000 keys/min.
- `redis.hit_rate_pct`: Dropped from ~95-100% to ~31%.
- `orders-api.latency_p95_ms`: Jumped from ~120ms to ~4,056ms.

## Proposed Remediation
Increase Redis cache memory (`increase_cache_memory`) to accommodate the new product bundle keys and eliminate the eviction stampede. This is safe, targeted, and directly addresses the resource constraint introduced by the new deployment.

## Follow-ups
- Review caching memory budgeting for future feature rollouts.
- Implement cache sizing checks in CI/CD or staging environments.
