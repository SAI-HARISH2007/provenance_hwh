# Incident Report

**Summary**
- Inventory API degraded with frequent pod restarts and elevated error rate.

**Timeline**
- 01:37 Z – Deploy `inventory-1.10.0` added an in‑process SKU cache.
- 02:42‑02:46 Z – Logs show OOM kills (exit code 137).
- 02:42‑03:12 Z – Memory usage spiked to ~98 %.
- 03:12 Z – Alert fired; health probe returned 502.

**Root Cause**
- The new in‑process cache caused a memory leak, exhausting pod memory and triggering OOM kills (**memory_leak_oom**).

**Evidence**
- Alert details (degraded service, restarts, errors).
- Deploy record of cache addition.
- Error logs with OOM exit codes.
- Memory usage metric reaching 98 %.
- Health probe failure (502) confirming OOM‑related restarts.

**Proposed Remediation** (safe)
- **Rollback the `inventory-api` deployment to the previous stable version** (`inventory-1.9.x`).
- This removes the faulty cache, stopping memory pressure and OOM kills.
- No data loss; change only added a cache layer.

**Follow‑ups**
- Validate cache implementation in staging.
- Add memory usage alerts and guardrails.
- Consider externalizing hot‑item cache.
