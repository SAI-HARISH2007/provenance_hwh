## Incident Report: orders-api order_create failure

### Summary
The `orders-api` is experiencing a P1 alert with a 58% failure rate for order creation. Investigation reveals the root cause is the PostgreSQL database disk reaching 100% utilization, preventing the `orders-api` from writing new data.

### Timeline
*   **2026-08-30T01:02:00Z**: `postgres` configuration change to enable `log_min_duration_statement=0` for slow-query investigation.
*   **2026-08-30T02:47:53Z**: First `ERROR orders-api: insert failed: could not extend file` logs appear, indicating disk space issues.
*   **2026-08-30T02:52:00Z**: `inventory-api` deployed with version `inventory-1.9.3` (add reservation retry).
*   **2026-08-30T03:12:00Z**: Alert fired for `orders-api` order_create failure rate 58%.

### Root cause
**disk_full** on `postgres`. The PostgreSQL database disk reached 100% utilization, preventing `orders-api` from performing necessary database inserts. This is directly evidenced by the `could not extend file` errors in the `orders-api` logs and the `postgres` `disk_pct` metric showing 100%.

### Evidence
*   **`orders-api` logs**: Repeated `ERROR orders-api: insert failed: could not extend file "base/16384/2619"` messages, which is a direct indication of a full disk preventing writes.
*   **`postgres` metrics**: `disk_pct: now 100 (30m ago 41, max 100)`. This shows a rapid increase in disk usage from 41% to 100% within the last 30 minutes, correlating with the start of the errors.
*   **`orders-api` metrics**: `error_rate_pct: now 59.635` confirms the high failure rate reported by the alert.
*   The `inventory-api` also shows a degraded status and high error rate (57.283%), likely a cascading effect as `orders-api` cannot complete order processes requiring inventory updates.

### Remediation
**free_disk_space** on `postgres`. Immediate action is required to free up disk space on the PostgreSQL server. This may involve deleting old logs, temporary files, or scaling up disk capacity.

### Follow-ups
1.  Investigate the cause of rapid disk consumption on `postgres`. This could be related to the `log_min_duration_statement=0` change, large data imports, or unmanaged temporary files.
2.  Revert the `postgres` `log_min_duration_statement=0` configuration if it is found to be a significant contributor to disk usage, or implement proper log rotation and retention policies.
3.  Implement proactive disk space monitoring and alerting for `postgres` to prevent future occurrences.
4.  Assess the impact of the `inventory-api` deploy and its 'reservation retry' logic in the context of the database outage, though it is not the root cause.