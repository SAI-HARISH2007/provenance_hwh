# Incident Report: Orders-API Inventory Dependency Errors

## Summary
At 03:12 UTC, `orders-api` began failing 47% of requests due to inventory dependency errors. Investigation revealed that `inventory-api` was recently migrated to a new Kubernetes namespace (`fulfilment`) and its old DNS name (`inventory-api.default.svc`) was retired, while `orders-api` is still attempting to connect to the retired DNS name.

## Timeline
- **2026-08-30T02:46:00Z**: `orders-api` deployed `orders-3.8.2` (inventory client timeout changes).
- **2026-08-30T02:48:00Z**: `inventory-api` migrated to namespace `fulfilment` by `ops-bot`, retiring the old DNS name (`inventory-api.default.svc`).
- **2026-08-30T03:12:00Z**: Alert fires for `orders-api` inventory dependency errors (47%).

## Root Cause
`dns_resolution_failure`: `inventory-api`'s DNS name changed during a namespace migration, but `orders-api` configuration/client is still pointing to the retired DNS name (`inventory-api.default.svc`), resulting in DNS resolution failure (`NXDOMAIN`) and TCP connection timeouts.

## Proposed Remediation
Update `orders-api` configuration/environment variables to point to the new inventory service DNS name in the `fulfilment` namespace (`inventory-api.fulfilment.svc`).

## Follow-ups
- Update service discovery / dependency documentation across teams.
- Implement integration tests that validate cross-service DNS resolution before namespace migrations.