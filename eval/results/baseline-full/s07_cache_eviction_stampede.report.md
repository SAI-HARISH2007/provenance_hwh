# Incident Report: orders-api Latency Spike

## Summary
At 2026-08-30T03:12:00.000Z, an alert fired for high p95 latency on `orders-api` (reaching ~3.9s against an 800ms threshold). The root cause was traced back to a recent deployment (`orders-3.8.1`) which added ~1.5GB of new product bundle cache keys, exceeding Redis memory limits and causing continuous key eviction. This resulted in a cache stampede, drastically reducing Redis hit rates and overwhelming PostgreSQL with heavy join queries.

## Timeline
- **2026-08-30T02:27:00Z**: `orders-api` deployed version `orders-3.8.1` (cache product bundles, adding ~1.5GB of new keys).
- **2026-08-30T02:49:34Z**: Redis reaches `maxmemory`, starting continuous cache eviction (`maxmemory reached; evicting keys`).
- **2026-08-30T02:50:18Z**: PostgreSQL begins logging slow queries (`SELECT ... FROM orders JOIN bundles ...` taking up to 13.6s).
- **2026-08-30T03:04:00Z+**: `orders-api` and `api-gateway` p95 latencies consistently exceed 4 seconds.
- **2026-08-30T03:12:00Z**: P2 alert fires for `orders-api` p95 latency.

## Root Cause
The new caching logic in `orders-3.8.1` flooded the 2GB Redis instance with 1.5GB of new data, pushing memory usage over 100% and triggering aggressive LRU evictions (~48,000 keys/min). Cache hit rates collapsed from ~100% to ~31%, forcing requests to fall back to PostgreSQL with expensive join queries. This exhausted the DB connection pool and maxed out Postgres CPU.

## Evidence
- Deployment log: `orders-3.8.1: cache product bundles (adds ~1.5GB of new keys)`
- Redis metric: `redis.used_memory_pct` reached 102.7% with `redis.evicted_keys_per_min` around 47,000–49,000.
- Redis metric: `redis.hit_rate_pct` dropped from ~98% to ~31%.
- PostgreSQL metric: `postgres.connections_used` jumped from ~38 to over 90.
- Postgres logs: Frequent slow queries `SELECT ... FROM orders JOIN bundles ...` taking several seconds.

## Remediation
1. Roll back `orders-api` to version `orders-3.8.0` to remove the problematic bundle caching logic.
2. Alternatively, scale up Redis memory or adjust caching strategies, but immediate rollback is the fastest way to relieve database connection exhaustion.

## Follow-ups
- Implement pre-release memory profiling for caching changes.
- Add monitoring and alerts for Redis eviction rates and hit rate drops.
- Review database connection pool limits and query timeout configurations.