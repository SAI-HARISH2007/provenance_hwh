# Incident Report: Orders-API Inventory Dependency Errors

## Summary
At 2026-08-30T03:12:00.000Z, `orders-api` experienced a P1 alert due to a 47% error rate on inventory dependency calls, causing requests to time out and `api-gateway` to return 503 errors.

## Timeline
- **02:46:00**: `orders-api` deployed version `orders-3.8.2` increasing inventory client timeout to 5s and adding retries.
- **02:48:00**: `inventory-api` migrated to the `fulfilment` namespace, retiring the old default namespace DNS name (`inventory-api.default.svc`).
- **02:49:25**: `orders-api` logs begin showing TCP dial timeouts to the retired DNS name.
- **03:12:00**: Alert fires as error rates and p95 latencies spike.

## Root Cause
The `inventory-api` service was moved to a new Kubernetes namespace (`fulfilment`), retiring its old DNS name (`inventory-api.default.svc`). Because `orders-api` attempts to connect to the old DNS address and was recently configured with longer timeouts and retries, requests hang and fail consistently.

## Evidence
- Infrastructure change log: `inventory-api: migrate service to new namespace 'fulfilment' (old DNS name retired)`
- Deploy log: `orders-api: orders-3.8.2: inventory client timeout 2s -> 5s + retries`
- Error logs: `ERROR orders-api: inventory client: request failed dial tcp inventory-api.default.svc:8080: i/o timeout`

## Remediation
Roll back `orders-api` or update its configuration / client endpoint to point to the new `fulfilment` namespace DNS name.

## Follow-ups
1. Ensure service migrations update all dependent client environment variables or use fully qualified cluster-wide DNS/service mesh discovery.
2. Implement faster fail-fast mechanisms or circuit breaking when internal dependencies experience continuous DNS/connection failures.