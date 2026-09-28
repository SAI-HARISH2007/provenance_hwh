# Incident Report: inventory-api OOM Crash Loop

## Summary
At 2026-08-30T03:12:00.000Z, `inventory-api` began firing alerts due to frequent container restarts (exit code 137, OOMKilled) and elevated error rates (22%). Investigation revealed that version `inventory-1.10.0`, deployed at 01:37:00.000Z with an unbounded in-process SKU cache, caused memory usage to continuously grow until exhausting the container limit (2048Mi).

## Timeline
- **01:37:00.000Z**: `inventory-1.10.0` deployed ("adds in-process hot-item cache").
- **02:42:42.000Z**: First observed OOM exit code 137 log entries appear as memory climbs.
- **03:12:00.000Z**: P2 alert fires for `inventory-api` pod restarts and 22% error rate.
- **03:12:00.000Z+**: Investigation confirms memory climbs from ~50% to 98.5%+ leading to continuous OOM kills.

## Root Cause
`memory_leak_oom`: The new in-process cache added in `inventory-1.10.0` lacks an eviction policy or max size constraint (or leaks unconstrained objects in memory), causing unbounded heap growth until the container hits its memory limit and is terminated by the kernel (exit code 137).

## Evidence
- **Alert / Status**: `inventory-api` is degraded; 6 pod restarts in 10 minutes.
- **Recent Changes**: `inventory-1.10.0` added an in-process SKU cache for hot items.
- **Logs**: `container exited (code 137); restarting` repeated continuously.
- **Metrics**: `mem_pct` climbed steadily from 50% to 98.5%.
- **Probe**: `http://inventory-api/health` confirmed `last exit OOMKilled 137, rss 2048Mi at kill`.

## Proposed Remediation
- **Action**: `rollback_deploy` on `inventory-api` to the previous stable version (`inventory-1.0.9` or pre-cache release).
- **Safety**: Rolling back reverts the code introduction of the unconstrained in-process cache, safely returning memory consumption to baseline levels.

## Follow-ups
1. Require max capacity / LRU eviction policy and memory bounds on any in-process caching implementations.
2. Add memory utilization alerts before OOM container limits are reached.
