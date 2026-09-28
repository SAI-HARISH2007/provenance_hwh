# Incident Report: Orders-API Inventory Dependency Errors

## Summary
At 2026-08-30T03:12:00Z, a P1 alert fired for `orders-api` due to inventory dependency errors affecting 47% of requests. Investigation revealed that `inventory-api` was migrated to a new namespace (`fulfilment`) at 02:48:00Z, retiring its old DNS name (`inventory-api.default.svc`). Meanwhile, `orders-api` is attempting to connect to the retired DNS name `inventory-api.default.svc:8080`, causing connection timeouts and failures.

## Timeline
- **02:46:00Z**: `orders-api` deployed version `orders-3.8.2` (inventory client timeout changes).
- **02:48:00Z**: `inventory-api` migrated to namespace `fulfilment` and old DNS name retired (`ops-bot`).
- **02:49:34Z+**: `orders-api` logs flood with `dial tcp inventory-api.default.svc:8080: i/o timeout`.
- **03:12:00Z**: P1 alert fired (`orders-api` inventory dependency errors 47%).

## Root Cause
`dns_resolution_failure` (or stale DNS/endpoint configuration in `orders-api` pointing to a retired service DNS name after an infra namespace migration).

## Evidence
- `recent_changes`: `inventory-api` migrated to namespace `fulfilment` (old DNS name retired).
- `query_logs`: `orders-api` logs show repeated errors: `dial tcp inventory-api.default.svc:8080: i/o timeout`.
- `run_probe dns`: `inventory-api.default.svc` resolves to `NXDOMAIN`.

## Proposed Remediation
Roll back the recent `orders-api` deploy (`orders-3.8.2`) or update the `orders-api` configuration / deploy a fix pointing to the new `inventory-api.fulfilment.svc` endpoint. Choosing `rollback_deploy` on `orders-api` (or rolling back the problematic config/deploy) to restore correct resolution/behavior as per available safe actions.
