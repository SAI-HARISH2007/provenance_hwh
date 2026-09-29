# Incident Report: orders-api Latency Spike

## Summary
At 2026-08-30T03:12:00.000Z, the `orders-api` service experienced high p95 latency (3.9s) and error rate increases. The root cause was a recent code deployment introducing ~1.5GB of new cache keys, overflowing Redis memory and triggering a cache eviction stampede.

## Timeline
- **2026-08-30T02:27:00Z**: `orders-api` deployed version `orders-3.8.1` introducing product bundle caching.
- **2026-08-30T02:50:00Z**: Redis memory reaches 102.7% capacity, high rate of key evictions begins.
- **2026-08-30T03:12:00Z**: Alert fires as p95 latency climbs to 3.9s due to massive DB fallback traffic.

## Root Cause
A bad deployment (`orders-3.8.1`) added ~1.5GB of new cache keys to Redis without sufficient capacity planning, causing cache thrashing, evictions, and downstream database saturation.

## Evidence
- `redis: used_memory_pct: now 102.703`
- `redis: evicted_keys_per_min: now 47670.7`
- `redis: hit_rate_pct: now 31.335 (down from 91.766)`
- Deploy log: `orders-api: orders-3.8.1: cache product bundles (adds ~1.5GB of new keys)`

## Remediation
- Rollback `orders-api` to the previous stable version (`orders-3.8.0`).

## Follow-ups
1. Review sizing and TTL strategy for new cache entries before re-deploying product bundle caching.
2. Scale up Redis memory or implement cache key eviction monitoring.