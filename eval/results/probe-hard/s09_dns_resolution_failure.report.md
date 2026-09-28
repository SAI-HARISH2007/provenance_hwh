# Incident Report: Orders API Inventory Dependency Errors

## Summary
At 2026-08-30T03:12:00.000Z, a P1 alert fired for `orders-api` reporting 47% inventory dependency errors. Investigation revealed that the `inventory-api` service was migrated to a new Kubernetes namespace (`fulfilment`) and its old DNS name (`inventory-api.default.svc`) was retired, while `orders-api` was still configured to point to the old DNS address.

## Timeline
- **2026-08-30T02:46:00.000Z**: `orders-api` deployed `orders-3.8.2` (timeout/retries update).
- **2026-08-30T02:48:00.000Z**: `inventory-api` migrated to new namespace `fulfilment` and old DNS name retired by `ops-bot`.
- **2026-08-30T02:49:34.000Z onwards**: `orders-api` logs begin flooding with connection timeouts (`dial tcp inventory-api.default.svc:8080: i/o timeout`).
- **2026-08-30T03:12:00.000Z**: P1 alert fired for `orders-api`.

## Root Cause
**bad_config_deploy** (or out-of-sync service endpoint configuration): The `inventory-api` dependency endpoint address used by `orders-api` points to the retired DNS name `inventory-api.default.svc`, which now resolves to `NXDOMAIN`.

## Evidence
1. `recent_changes`: `inventory-api: migrate service to new namespace 'fulfilment' (old DNS name retired)`
2. `query_logs` on `orders-api`: `inventory client: request failed dial tcp inventory-api.default.svc:8080: i/o timeout`
3. `run_probe` (dns): `resolve inventory-api.default.svc -> NXDOMAIN`
4. `run_probe` (http): `GET http://inventory-api.fulfilment.svc:8080/healthz -> 200 in 21ms`

## Proposed Remediation
Update the `orders-api` configuration to point to the correct DNS name/service in the `fulfilment` namespace (`inventory-api.fulfilment.svc`). This is safe as it aligns the service discovery endpoint with the recent infrastructure migration.

## Follow-ups
- Ensure cross-namespace dependencies are coordinated or updated simultaneously during namespace migrations.
- Add service discovery validation checks in CI/CD or infrastructure migration playbooks.
