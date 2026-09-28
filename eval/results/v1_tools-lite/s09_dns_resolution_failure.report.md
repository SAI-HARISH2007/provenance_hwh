# Incident Report: Orders-API Inventory Dependency Errors

## Summary
At 2026-08-30T03:12:00.000Z, a P1 alert fired for `orders-api` indicating 47% inventory dependency errors. Investigation revealed that `inventory-api` was recently migrated to a new namespace (`fulfilment`) and its old DNS name (`inventory-api.default.svc`) was retired, while `orders-api` was still configured to dial the old DNS endpoint.

## Timeline
- **02:46:00.000Z**: `orders-api` deployed version `orders-3.8.2` (timeout/retries adjustment).
- **02:48:00.000Z**: `inventory-api` migrated to namespace `fulfilment` and old DNS name retired by `ops-bot`.
- **02:49:34.000Z**: `orders-api` starts logging connection timeouts trying to reach `inventory-api.default.svc:8080`.
- **03:12:00.000Z**: Alert fires for `orders-api` inventory dependency errors (47%).
- **03:12:00+Z**: Greenlight investigates, identifies DNS failure, verifies via DNS probes.

## Root Cause
`dns_resolution_failure`: `inventory-api`'s DNS name changed during a namespace migration (`inventory-api.default.svc` -> `inventory-api.fulfilment.svc`), but `orders-api`'s configuration/environment still points to the retired DNS name, causing TCP dial timeouts.

## Evidence
- `recent_changes`: `inventory-api: migrate service to new namespace 'fulfilment' (old DNS name retired)`
- `query_logs` on `orders-api`: `dial tcp inventory-api.default.svc:8080: i/o timeout`
- `run_probe` (dns): `inventory-api.default.svc` -> `NXDOMAIN`
- `run_probe` (dns): `inventory-api.fulfilment.svc` -> `10.0.91.14`

## Proposed Remediation
Update `orders-api` configuration/environment variables to point to the new inventory service endpoint (`inventory-api.fulfilment.svc`). This is safe because it corrects the upstream dependency address to match the new infrastructure topology.

## Follow-ups
- Ensure service migration procedures include updating dependent service references or using stable cross-namespace service discovery / external names.
- Add integration tests verifying service-to-service connectivity after infrastructure migrations.