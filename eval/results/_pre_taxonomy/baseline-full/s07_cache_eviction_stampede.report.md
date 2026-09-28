# Incident Report: orders-api Latency Spike

## Summary
At 2026-08-30T03:12:00Z, `orders-api` experienced a P2 alert for high p95 latency (3.9s vs 800ms threshold). The incident was triggered by a recent deployment (`orders-3.8.1`) that introduced ~1.5GB of new cache keys for product bundles. This exhausted the 2GB Redis memory limit, causing a severe cache eviction stampede, cache hit-rate collapse, and a subsequent database overload as requests fell back to PostgreSQL.

## Timeline
- **2026-08-30T02:27:00Z**: `orders-api` deployed version `orders-3.8.1` (added ~1.5GB of bundle keys).
- **2026-08-30T02:49:34Z**: Redis `maxmemory` reached; continuous key eviction begins (~47k-49k keys/min evicted).
- **2026-08-30T02:50:18Z**: PostgreSQL logs first slow queries (`SELECT ... FROM orders JOIN bundles ...`) taking >10 seconds.
- **2026-08-30T03:12:00Z**: `orders-api` p95 latency alert fires after sustained high latency.

## Root Cause
The deployment of `orders-3.8.1` oversized the caching requirements relative to the Redis instance allocation (`maxmemory: 2gb`). This caused churn, thrashing, and cache misses, routing a high volume of heavy join queries directly to PostgreSQL and exhausting connection and CPU resources.

## Evidence
- **Recent Change**: `orders-api: orders-3.8.1: cache product bundles (adds ~1.5GB of new keys)`
- **Redis Metrics**: `redis.hit_rate_pct` plummeted from ~100% to ~30%; `redis.evicted_keys_per_min` jumped to ~48,000.
- **Postgres Metrics**: CPU usage spiked to ~100%, connections rose from ~38 to ~90.
- **Logs**: Frequent `cache miss ... -> db fallback` entries paired with slow query logs in PostgreSQL.

## Remediation
1. Rollback `orders-api` to the previous stable version (`orders-3.8.0`) to stop the cache memory exhaustion.
2. Alternatively scale Redis memory or optimize bundle payload sizes in a future patch.

## Follow-ups
- Review cache sizing guidelines and test memory footprint before deploying new caching layers.
- Implement circuit breakers or rate-limiting for database fallbacks during cache misses.