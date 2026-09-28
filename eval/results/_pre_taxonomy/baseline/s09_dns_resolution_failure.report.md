# Incident Report: Orders-API Inventory Dependency Errors

## Summary
At 2026-08-30T03:12:00.000Z, the `orders-api` service experienced a P1 alert due to a 47.28% error rate caused by failing calls to the inventory dependency. The root cause is a bad configuration/deploy where `orders-api` version `orders-3.8.2` attempts to reach `inventory-api` via its retired DNS name (`inventory-api.default.svc:8080`) following `inventory-api`'s migration to the `fulfilment` namespace.

## Timeline
- **02:46:00.000Z**: `orders-api` deployed version `orders-3.8.2` (inventory client timeout update).
- **02:48:00.000Z**: `inventory-api` migrated to the `fulfilment` namespace, retiring the old DNS name.
- **02:49:25.000Z**: First TCP connection timeout errors logged in `orders-api` connecting to `inventory-api.default.svc:8080`.
- **03:12:00.000Z**: P1 alert fires for `orders-api` inventory dependency errors (47% error rate).

## Root Cause
DNS resolution / network routing failure due to a configuration mismatch introduced during recent deployments. `orders-api` is targeting the old, retired service DNS endpoint of `inventory-api` (`inventory-api.default.svc:8080`) instead of the new namespace `fulfilment`.

## Evidence
- Recent changes log showing `orders-api` deployment at 02:46 and `inventory-api` namespace migration at 02:48.
- Continuous `i/o timeout` logs in `orders-api`: `dial tcp inventory-api.default.svc:8080: i/o timeout`.
- Metrics showing `orders-api` error rate spiking to ~47% and p95 latency jumping to >4700ms.

## Remediation
1. Roll back `orders-api` to version `orders-3.8.1` or hotfix the `orders-api` environment configuration/code to point to the new inventory service DNS name in the `fulfilment` namespace.

## Follow-ups
- Update CI/CD pipelines and deployment verification checks to ensure service dependencies are validated across namespace migrations.
- Implement robust service discovery or use external name aliases to prevent hardcoded namespace-dependent DNS failures during infrastructure migrations.