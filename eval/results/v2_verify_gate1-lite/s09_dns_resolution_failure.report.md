# Incident Report: Orders-API Inventory Dependency Errors

## Summary
At 2026-08-30T03:12:00.000Z, a P1 page fired for `orders-api` reporting 47% inventory dependency errors. Investigation revealed that `inventory-api` was migrated to a new Kubernetes namespace (`fulfilment`) at 02:48 UTC and its old DNS name (`inventory-api.default.svc`) was retired, while `orders-api` is still attempting to connect to the retired DNS name.

## Timeline
- **02:46:00 UTC**: `orders-api` deployed version `orders-3.8.2` (updating timeout and retries).
- **02:48:00 UTC**: `inventory-api` migrated to namespace `fulfilment` by `ops-bot`, retiring the old DNS name (`inventory-api.default.svc`).
- **02:49:34 UTC+**: `orders-api` begins logging dial timeouts attempting to reach `inventory-api.default.svc:8080`.
- **03:12:00 UTC**: P1 alert fires for `orders-api` inventory dependency errors (47%).

## Root Cause
**dns_resolution_failure**: The downstream dependency `inventory-api` changed its Kubernetes namespace and DNS name to `inventory-api.fulfilment.svc`, causing all calls from `orders-api` using the old DNS hostname (`inventory-api.default.svc`) to fail with DNS resolution / dial timeouts.

## Proposed Remediation
Roll back the recent `orders-api` deploy / configuration change or update the service endpoint environment variable to point to `inventory-api.fulfilment.svc`.
