## Incident Report: Orders-API Inventory Dependency Errors

### Summary
Orders-api is experiencing a P1 alert with a 47% error rate due to connectivity issues with the inventory-api. The root cause is a DNS resolution failure, as orders-api is attempting to connect to the old, retired DNS name for inventory-api following an infrastructure migration.

### Timeline
*   **2026-08-30T02:46:00Z**: `orders-api` deploy to version `3.8.2` (inventory client timeout increase) by 'lee'. (Note: `orders-api` is currently running `3.8.1`, suggesting this deploy either failed or was rolled back).
*   **2026-08-30T02:48:00Z**: `inventory-api` migrated to a new namespace 'fulfilment', and its old DNS name was retired by 'ops-bot'.
*   **2026-08-30T02:49:25Z**: First `ERROR orders-api: inventory client: request failed dial tcp inventory-api.default.svc:8080: i/o timeout` log observed in `orders-api`.
*   **2026-08-30T03:12:00Z**: Alert fired for `orders-api` due to `inventory dependency errors 47%`.

### Root Cause
**dns_resolution_failure**: The `orders-api` service is attempting to connect to `inventory-api` using its old DNS name (`inventory-api.default.svc:8080`), which was retired at `02:48:00Z` when `inventory-api` was migrated to the `fulfilment` namespace. This results in `i/o timeout` errors as the old DNS entry no longer resolves to the active `inventory-api` instance. The `inventory-api` itself is healthy, indicating the problem lies with the client's (orders-api) ability to locate it.

### Evidence
*   The alert message explicitly states 'inventory dependency errors 47%'.
*   A recent change log indicates `inventory-api` was migrated to a new namespace and its 'old DNS name retired' at `02:48:00Z`.
*   `orders-api` logs are filled with `ERROR orders-api: inventory client: request failed dial tcp inventory-api.default.svc:8080: i/o timeout` starting shortly after the `inventory-api` migration.
*   `orders-api` metrics show a sharp increase in `error_rate_pct` from `0.392%` to `47.286%` and `latency_p95_ms` from `123ms` to `4766ms`.
*   `inventory-api` metrics show it is `healthy` with normal error rates and latency, confirming the issue is not with the inventory service itself.

### Remediation
**update_config** for `orders-api` to point to the correct, new DNS name for `inventory-api` (e.g., `inventory-api.fulfilment.svc`). This will likely require a new deployment of `orders-api` with the updated configuration.

### Follow-ups
1.  Investigate why the `orders-api` deploy to `3.8.2` at `02:46:00Z` did not persist, as the service is currently running `3.8.1`.
2.  Establish a clear communication and coordination protocol for infrastructure changes that affect service dependencies, especially DNS name changes.
3.  Consider implementing a more dynamic service discovery mechanism (e.g., a service mesh) to reduce reliance on hardcoded DNS names in client configurations.