# Incident Report: Orders-API Inventory Dependency Errors

## Summary
At 2026-08-30T03:12:00.000Z, a P1 alert fired for `orders-api` indicating that 47% of requests were failing due to inventory dependency errors. The root cause was an infrastructure migration of `inventory-api` to a new namespace (`fulfilment`) without updating the dependent `orders-api` client configuration, leading to DNS resolution and connection timeout failures against the retired DNS name (`inventory-api.default.svc`).

## Timeline
- **02:46:00.000Z**: `orders-api` deployed version `orders-3.8.2` (inventory client timeout update).
- **02:48:00.000Z**: `inventory-api` migrated to the new namespace `fulfilment` and old DNS name retired.
- **02:49:25.000Z**: First `i/o timeout` errors logged by `orders-api` connecting to `inventory-api.default.svc:8080`.
- **03:12:00.000Z**: Alert fires as error rates and P95 latency spike significantly.

## Root Cause
The `inventory-api` service was moved to the `fulfilment` namespace, retiring its old DNS endpoint (`inventory-api.default.svc`). Because `orders-api` attempts to reach it using the old hostname, outgoing connection attempts result in TCP timeouts (`i/o timeout`).

## Evidence
- Infrastructure change log: `inventory-api: migrate service to new namespace 'fulfilment' (old DNS name retired)`
- `orders-api` error logs: `ERROR orders-api: inventory client: request failed dial tcp inventory-api.default.svc:8080: i/o timeout`
- Metric spikes: `orders-api.error_rate_pct` jumping to ~47% and `latency_p95_ms` rising to over 5000ms.

## Remediation
Update the `orders-api` configuration to point to the new DNS endpoint in the `fulfilment` namespace (e.g., `inventory-api.fulfilment.svc`).

## Follow-ups
1. Ensure service migrations enforce dependency discovery checks or automatic updating of environment variables/service discovery pointers.
2. Implement robust circuit breaking and fail-fast mechanisms for downstream HTTP clients.