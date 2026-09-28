# Incident Report: Orders-API Inventory Dependency Errors

## Summary
At 2026-08-30T03:12:00.000Z, an alert fired for `orders-api` due to inventory dependency errors (47% error rate). Investigation revealed that `inventory-api` was recently migrated to a new Kubernetes namespace (`fulfilment`) and its old DNS name (`inventory-api.default.svc`) was retired. `orders-api` is still configured to reach the old DNS name, resulting in connection timeouts/NXDOMAIN errors.

## Timeline
- **2026-08-30T02:46:00Z**: `orders-api` deploy `orders-3.8.2` shipped (timeout/retry adjustments).
- **2026-08-30T02:48:00Z**: `inventory-api` migrated to namespace `fulfilment` by `ops-bot`, retiring the old DNS name (`inventory-api.default.svc`).
- **2026-08-30T02:49:34Z**: `orders-api` logs begin showing persistent connection failures to `inventory-api.default.svc:8080`.
- **2026-08-30T03:12:00Z**: Alert fires (`inventory dependency errors 47%`).

## Root Cause
**DNS resolution failure** (or dependency misconfiguration resulting from infrastructure migration). Specifically, `inventory-api` moved namespaces, but `orders-api` configuration still points to the retired DNS name in the default namespace.

## Evidence
- **Recent Changes**: `inventory-api` migrated to namespace `fulfilment`, old DNS name retired.
- **Logs**: `orders-api` logging `dial tcp inventory-api.default.svc:8080: i/o timeout`.
- **DNS Probe**: `inventory-api.default.svc` resolves to `NXDOMAIN`, whereas `inventory-api.fulfilment.svc` resolves successfully (`10.0.91.14`).

## Proposed Remediation
Update `orders-api` configuration to point to the new DNS name (`inventory-api.fulfilment.svc`). This is safe and directly addresses the endpoint mismatch caused by the infrastructure migration.

## Follow-ups
- Ensure upstream callers are automatically notified or their configurations updated during cross-namespace service migrations.
