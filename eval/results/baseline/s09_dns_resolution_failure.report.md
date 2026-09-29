# Incident Report: Orders-API Inventory Dependency Errors

## Summary
At 2026-08-30T03:12:00.000Z, an alert fired for `orders-api` showing 47% inventory dependency errors. Investigation revealed that a recent infrastructure change moved `inventory-api` to a new Kubernetes namespace (`fulfilment`) and retired the old DNS name (`inventory-api.default.svc`), while `orders-api` was still configured to call the old endpoint.

## Timeline
- **2026-08-30T02:46:00.000Z**: `orders-api` updated to version `orders-3.8.2` (inventory client timeout & retries).
- **2026-08-30T02:48:00.000Z**: `inventory-api` migrated to namespace `fulfilment`; old DNS name retired.
- **2026-08-30T02:49:25.000Z**: Initial TCP connection timeouts to `inventory-api.default.svc:8080` appear in `orders-api` logs.
- **2026-08-30T03:12:00.000Z**: P1 alert fired for `orders-api` inventory dependency errors.

## Root Cause
DNS resolution/connection failure due to `inventory-api`'s migration to the `fulfilment` namespace without updating `orders-api`'s upstream target configuration.

## Evidence
- `[infra] inventory-api: migrate service to new namespace 'fulfilment' (old DNS name retired)`
- `ERROR orders-api: inventory client: request failed dial tcp inventory-api.default.svc:8080: i/o timeout`

## Remediation
Update the `orders-api` configuration to point to the new `inventory-api` DNS endpoint in the `fulfilment` namespace (`inventory-api.fulfilment.svc`).

## Follow-ups
- Ensure service migrations update all dependent service configurations atomically or via robust service discovery (e.g., externalName or cluster-internal DNS aliases).
- Implement automated integration tests for cross-service dependencies during infrastructure migrations.