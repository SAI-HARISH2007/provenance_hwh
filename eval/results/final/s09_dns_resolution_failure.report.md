# Incident Report: Orders-API Inventory Dependency Errors

## Summary
At 2026-08-30T03:12:00.000Z, a P1 alert fired for `orders-api` indicating that 47% of requests were experiencing inventory dependency errors. Investigation revealed that `inventory-api` had been migrated to a new Kubernetes namespace (`fulfilment`) and its old DNS name retired, while `orders-api` was still configured to call the old DNS endpoint (`inventory-api.default.svc:8080`).

## Timeline
- **02:46:00.000Z**: `orders-api` deployed version `orders-3.8.2` (timeout/retry adjustments).
- **02:48:00.000Z**: `inventory-api` migrated to namespace `fulfilment` by ops-bot; old DNS name retired.
- **02:49:34.000Z onwards**: `orders-api` logs show repeated `i/o timeout` / dial errors trying to reach `inventory-api.default.svc:8080`.
- **03:12:00.000Z**: P1 alert fired due to inventory dependency errors.

## Root Cause
**dns_resolution_failure** (or misconfigured caller endpoint). The inventory dependency moved to a new namespace/hostname (`inventory-api.fulfilment.svc`), but `orders-api` configuration still points to the retired `inventory-api.default.svc`.

## Evidence
- `recent_changes`: `inventory-api: migrate service to new namespace 'fulfilment' (old DNS name retired)`
- `query_logs` (orders-api): `dial tcp inventory-api.default.svc:8080: i/o timeout`
- `run_probe dns`: `inventory-api.default.svc -> NXDOMAIN`, whereas `inventory-api.fulfilment.svc -> 10.0.91.14`

## Proposed Remediation
Update the `orders-api` configuration to point to the new inventory service endpoint (`inventory-api.fulfilment.svc:8080`) using `update_config`. This safely corrects the caller's dependency address without requiring a service rollback or restart.

## Follow-ups
- Ensure all dependent services are tracked during namespace migrations to prevent stale endpoint configs.
