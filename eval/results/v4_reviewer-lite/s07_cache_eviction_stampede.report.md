# Incident Report: orders-api Latency Spike

## Summary
At 2026-08-30T03:12:00.000Z, `orders-api` experienced a P95 latency spike of 3.9s (threshold 800ms), causing `api-gateway` to become degraded. Investigation revealed that a recent deploy to `orders-api` introduced ~1.5GB of new cached product bundles, which exceeded the 2GB Redis memory limit, causing a massive cache eviction stampede (`evicted_keys_per_min` ~48k evictions/min, `used_memory_pct` reaching 102.7%).

## Timeline
- **2026-08-30T02:27:00.000Z**: `orders-api` deployed version `orders-3.8.1` ("cache product bundles (adds ~1.5GB of new keys)").
- **02:27 - 03:12**: Redis memory usage rapidly climbed from ~60% to 102.7%, and key evictions spiked to ~48,000 keys/min.
- **2026-08-30T03:12:00.000Z**: `orders-api` p95 latency reached 3.9s, triggering the P2 alert.

## Root Cause
**cache_eviction_stampede**: The new feature in `orders-3.8.1` added approximately 1.5GB of new cache keys to Redis. With a 2GB `maxmemory` limit, the cache immediately hit capacity, causing aggressive key eviction (`allkeys-lru`), high cache miss rates, and downstream latency increases on `orders-api`.

## Evidence
- `recent_changes`: `orders-3.8.1` deploy explicitly states "(adds ~1.5GB of new keys)".
- `redis.used_memory_pct`: Rose from ~60% to 102.7% following the deploy.
- `redis.evicted_keys_per_min`: Jumped from 0 to ~48,000 evictions per minute immediately following the deploy.
- `get_config` on `redis`: Confirmed `maxmemory` is set to `2gb`.

## Proposed Remediation
**Increase cache memory** (`increase_cache_memory` on `redis`).
Increasing Redis memory allocation (e.g., to 4GB) will accommodate the new product bundle cache keys, stop the eviction stampede, and restore low-latency cache performance safely without needing to rollback the new feature.
