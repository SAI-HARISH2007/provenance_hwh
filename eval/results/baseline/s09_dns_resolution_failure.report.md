# Incident Report: Orders-API Inventory Dependency Errors

## Summary
At 2026-08-30T03:12:00.000Z, `orders-api` experienced a P1 alert due to high error rates (47.28%) communicating with its inventory dependency. This was caused by a recent infrastructure migration where `inventory-api` moved to a new namespace (`fulfilment`), retiring its old DNS endpoint while `orders-api` was configured with the outdated connection string.

## Timeline
- **02:46:00.000Z**: `orders-api` deployed version `orders-3.8.2` (inventory client timeout/retries change).
- **02:48:00.000Z**: `inventory-api` migrated to namespace `fulfilment` and old DNS name retired.
- **02:49:25.000Z**: `orders-api` begins logging TCP connection timeouts to `inventory-api.default.svc:8080`.
- **03:12:00.000Z**: P1 alert fires for `orders-api` inventory dependency errors.

## Root Cause
The `inventory-api` service was migrated to a new Kubernetes namespace (`fulfilment`), retiring the old DNS name (`inventory-api.default.svc`). `orders-api` is attempting to reach the retired DNS address, resulting in TCP i/o timeouts.

## Evidence
- Infrastructure log: `2026-08-30T02:48:00.000Z [infra] inventory-api: migrate service to new namespace 'fulfilment' (old DNS name retired)`
- Application log: `ERROR orders-api: inventory client: request failed dial tcp inventory-api.default.svc:8080: i/o timeout`

## Remediation
Update the `orders-api` configuration/environment variables to point to the new inventory service DNS name in the `fulfilment` namespace (e.g., `inventory-api.fulfilment.svc:8080`).

## Follow-ups
1. Ensure service dependency endpoints are updated dynamically or validated via integration tests prior to namespace migrations.
2. Implement alerting for unresolved DNS or persistent downstream connection failures during infrastructure migrations.