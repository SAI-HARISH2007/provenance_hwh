## Incident Report: orders-api P95 Latency Spike

### Summary
At 2026-08-30T03:12:00Z, an alert fired for orders-api indicating a P95 latency of 3.9s, significantly exceeding the 800ms threshold. Investigation revealed a severe degradation in Redis cache performance and an overloaded Postgres database, directly impacting orders-api.

### Timeline
* **2026-08-30T02:27:00Z**: `orders-api` version `orders-3.8.1` deployed, introducing caching for product bundles (adding ~1.5GB of new keys).
* **~02:30:00Z - 03:12:00Z**: Redis memory usage spiked, leading to aggressive key evictions and a plummeting cache hit rate. Orders-api logs show an increase in cache misses.
* **~02:30:00Z - 03:12:00Z**: Postgres CPU utilization surged from ~22% to ~98% due to increased fallback queries from orders-api.
* **2026-08-30T03:12:00Z**: Alert fired for orders-api P95 latency (3.9s) and increased error rate (9.17%).

### Root Cause
The root cause is a `cache_eviction_stampede` triggered by the `orders-api` deploy (`orders-3.8.1`) at 02:27:00Z. The deploy introduced a new caching mechanism for product bundles, adding approximately 1.5GB of new keys to Redis. This caused Redis to exceed its memory capacity (102.7% used_memory_pct), leading to aggressive key evictions (47k/min) and a drastic drop in cache hit rate (from ~90% to ~31%). The resulting increase in cache misses forced `orders-api` to fall back to the database for a significant portion of requests, overwhelming Postgres (98.41% CPU utilization) and causing the observed latency and error spikes in `orders-api`.

### Evidence
* **Recent Change**: `2026-08-30T02:27:00.000Z [deploy] orders-api: orders-3.8.1: cache product bundles (adds ~1.5GB of new keys) (lee)` directly precedes the incident.
* **Redis Metrics**: `used_memory_pct` jumped from 59.114% to 102.703%, `evicted_keys_per_min` went from 0 to 47670.7, and `hit_rate_pct` plummeted from 91.766% to 31.335%.
* **Postgres Metrics**: `cpu_pct` surged from 22.429% to 98.41%, indicating severe overload.
* **orders-api Metrics**: `latency_p95_ms` increased from 125.22ms to 4056.91ms and `error_rate_pct` from 0.412% to 9.171%.
* **orders-api Logs**: Frequent `DEBUG orders-api: cache miss key=order:XXXXX rid=YYYYY -> db fallback` entries confirm increased database load due to cache misses.

### Remediation
**Action**: `rollback_deploy`
**Target**: `orders-api`

Rolling back the `orders-3.8.1` deploy will revert the problematic caching logic, allowing Redis memory to recover, cache hit rates to normalize, and reducing the load on Postgres.

### Follow-ups
1.  Investigate Redis capacity: Determine if Redis needs to be scaled up (more memory) to accommodate the new cache data, or if the cache size needs to be optimized.
2.  Review caching strategy: Analyze the impact of caching product bundles and ensure proper cache invalidation and sizing for future deployments.
3.  Load testing: Conduct thorough load testing for new caching features to prevent similar incidents.
4.  Monitoring enhancements: Consider adding alerts for Redis memory usage and cache hit rate specifically tied to new deployments.