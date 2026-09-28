# Incident Report: orders-api Latency Spike

## Summary
At 03:12 UTC, `orders-api` experienced a P2 alert for high p95 latency (3.9s against an 800ms threshold). Investigation revealed that a recent deployment (`orders-3.8.1`) added approximately 1.5GB of new keys to Redis, exhausting available memory, triggering heavy key eviction, and drastically reducing the cache hit rate. This resulted in frequent database fallbacks, high CPU load on Postgres, and degraded end-to-end request latencies.

## Timeline
- **2026-08-30T02:27:00Z**: `orders-api` deployed version `orders-3.8.1` introducing product bundle caching (~1.5GB of new keys).
- **2026-08-30T03:04:00Z**: Redis memory reaches 102.7% utilization, causing high eviction rates (~47k evictions/min) and plummeting hit rates.
- **2026-08-30T03:12:00Z**: `orders-api` triggers high p95 latency alert (3.9s), prompting on-call response.

## Root Cause
Cache eviction stampede in Redis caused by memory exhaustion from the `orders-3.8.1` deployment.

## Evidence
- Recent change log showing the addition of ~1.5GB of new cache keys in `orders-3.8.1`.
- Redis metrics: `used_memory_pct` at 102.7%, `evicted_keys_per_min` at 47,670, and `hit_rate_pct` dropped to 31.3%.
- Postgres CPU spiked to 98.4% due to increased cache-miss fallback queries.

## Remediation
1. Increase Redis cache memory allocation to accommodate the new product bundle keys and stop the eviction loop.
2. Alternatively, rollback or optimize the key payload size in `orders-api` if memory cannot be scaled immediately.

## Follow-ups
- Review caching sizing guidelines for new features prior to deployment.
- Implement Redis memory usage alerts before exhaustion occurs.