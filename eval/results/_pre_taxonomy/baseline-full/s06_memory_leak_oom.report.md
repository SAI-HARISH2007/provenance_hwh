# Incident Report: inventory-api Memory Exhaustion and Restarts

## Summary
At 2026-08-30T03:12:00.000Z, `inventory-api` began experiencing continuous OOM restarts (6 restarts in 10 minutes) and a 22% error rate spike, impacting downstream requests at the API Gateway.

## Timeline
- **01:37** - `inventory-1.10.0` deployed, introducing an in-process hot-item SKU cache.
- **02:49** - First warning logs for GC pressure and growing heap appear in `inventory-api`.
- **03:04** - Memory usage exceeds 90%; pods begin crashing due to out-of-memory (OOM) conditions.
- **03:12** - Alert fires as pod restart counter hits 6 and error rate reaches ~22%.

## Root Cause
A memory leak caused by unbounded growth in the newly introduced in-process SKU cache (`inventory-1.10.0`).

## Evidence
- Recent deployment: `inventory-1.10.0: in-process SKU cache for hot items`
- Memory climbing rapidly from ~51% to over 95%.
- Repeated warning logs: `inventory-api: gc pressure: heap ... rss growing`
- Pod restart counter rising from 0 to 6.

## Remediation
1. Rollback `inventory-api` to version `1.9.x` (or previous stable version) to remove the leaking in-process cache.

## Follow-ups
- Fix the cache implementation to enforce max size limits and item TTLs before re-deploying in-process caching.
- Add memory and heap usage alerts before OOM threshold limits are reached.