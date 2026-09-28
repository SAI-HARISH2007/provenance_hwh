# Incident Report: Orders-API Inventory Dependency Errors

## Summary
The `orders-api` service experienced high error rates when communicating with the `inventory-api` dependency. The root cause is a bad configuration / infra change where `inventory-api` was migrated to a new Kubernetes namespace (`fulfilment`) and its old DNS name (`inventory-api.default.svc`) was retired, while `orders-api` was still configured to dial the old DNS name.

## Timeline
- **2026-08-30T02:46:00Z**: `orders-api` deployed version `orders-3.8.2` (inventory client timeout / retries).
- **2026-08-30T02:48:00Z**: `inventory-api` migrated to namespace `fulfilment` by `ops-bot`; old DNS name retired.
- **2026-08-30T02:49:34Z**: `orders-api` starts throwing I/O timeout errors dialing `inventory-api.default.svc:8080`.
- **2026-08-30T03:12:00Z**: P1 alert fires for `orders-api` (`inventory dependency errors 47%`).

## Root Cause
`bad_config_deploy`: The infrastructure change migrated `inventory-api` to a new namespace without updating `orders-api`'s upstream endpoint configuration/DNS reference, leading to DNS resolution failure (`NXDOMAIN`) and TCP timeouts.

## Proposed Remediation
Update `orders-api` configuration to point to the new DNS name / service endpoint in the `fulfilment` namespace (`inventory-api.fulfilment.svc`).

## Follow-ups
- Establish service discovery linkage checks or automated integration tests for inter-service namespace migrations.
- Ensure infrastructure migrations update dependent service configurations simultaneously.
