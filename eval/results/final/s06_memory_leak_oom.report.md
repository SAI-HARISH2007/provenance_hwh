# Incident Report: inventory-api Memory Leak / OOMKilled

## Summary
At 2026-08-30T03:12:00.000Z, `inventory-api` fired a P2 alert for pod restarts and error rate (22% errors, 6 restarts in 10m). Investigation revealed that a recent deploy (`inventory-1.10.0`, adding an in-process SKU cache) introduced an unbounded memory leak, causing containers to hit the container memory limit and get OOMKilled (exit code 137).

## Timeline
- **01:37 UTC**: `inventory-1.10.0` deployed ("in-process SKU cache for hot items").
- **01:37 - 02:42 UTC**: Memory usage steadily climbs from ~50% to 98% as the unbounded in-process cache accumulates items.
- **02:42 UTC**: First recorded OOMKilled exit (code 137) at 2048Mi memory limit. Container begins restart loop.
- **03:12 UTC**: Alert fires due to repeated container restarts and 502/error responses.

## Root Cause
**memory_leak_oom** in `inventory-api`. The in-process SKU cache introduced in version `1.10.0` does not bound cache size, TTL eviction, or memory consumption, leading to continuous memory growth and container OOM termination.

## Evidence
1. `recent_changes`: `inventory-1.10.0` deployed at 01:37 UTC with "in-process SKU cache for hot items".
2. `get_metrics` (`mem_pct`): Shows steady upward climb starting right after deploy, reaching 98.55%.
3. `query_logs`: Frequent container exits with code 137 (OOMKilled).
4. `run_probe` (`http`): Confirms `inventory-api` health endpoint failing with `pod restarting; last exit OOMKilled 137, rss 2048Mi at kill`.

## Proposed Remediation
Roll back the deployment of `inventory-api` from version `1.10.0` to the previous stable version (`1.9.x` or roll back the bad deploy via pipeline).
- **Safety**: Rolling back reverts the code introduction of the unbounded in-process cache, eliminating the memory leak.

## Follow-ups
1. Fix the in-process cache implementation in `inventory-api` to include LRU eviction and maximum size/memory limits before re-attempting introduction.
2. Add memory utilization alerts warning well before OOM limits.