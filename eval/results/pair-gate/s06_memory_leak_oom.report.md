# Incident Report

**Summary**: Inventory API experienced rapid pod restarts (6 in 10 min) and a 22 % error rate, degrading the service.

**Timeline**:
- **01:37** – Deploy `inventory-1.10.0` introduced an in‑process hot‑item SKU cache.
- **02:45‑03:10** – Memory usage (`mem_pct`) climbed from ~50 % to >98 %.
- **02:45‑03:12** – Pod restarts metric rose from 0 to 6, matching the memory spike.
- **03:12** – Alert fired (pod restarts, errors).

**Root Cause**: `memory_leak_oom` in `inventory-api`. The newly added cache consumes unbounded memory, causing the container to be OOM‑killed (exit 137) and restarted.

**Evidence**:
- Recent change adding cache (see `recent_changes`).
- Memory usage chart shows spike to 98 % (`get_metrics mem_pct`).
- Restart count correlates with memory spike (`get_metrics restarts`).
- HTTP health probe reports `502` with OOMKilled exit code 137 (`run_probe`).

**Proposed Remediation** (safe): Roll back `inventory-api` to the previous stable version (e.g., `inventory-1.9.x`) that does not contain the unbounded cache. This removes the memory pressure without altering resource limits or affecting dependent services.

**Why Safe**: Rolling back a stateless API is a standard, low‑risk mitigation. It restores known‑good memory behavior, stops OOM kills, and does not impact data stores.

**Follow‑ups**:
- Conduct load testing of the cache implementation to determine safe size limits.
- Add configuration to cap cache memory or implement eviction.
- Monitor memory usage after rollback to confirm stability.

---
