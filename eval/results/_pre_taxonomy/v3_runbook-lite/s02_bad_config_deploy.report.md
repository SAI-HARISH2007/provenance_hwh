# Incident Report: payments-api Charge Failures

## Summary
At 2026-08-30T03:12:00Z, `payments-api` experienced a 100% failure rate on charges (`charge_failed`), resulting in a P1 alert and bringing the service down. Investigation revealed that a recent deploy (`payments-2.15.0`) at 03:03 UTC changed the `PAYGATE_URL` configuration to use `/v2/` endpoints, which is causing requests to fail with `404 Not Found`.

## Timeline
- **2026-08-30T03:03:00Z**: `payments-api` deployed version `payments-2.15.0` (migrated `PAYGATE_URL` to `https://api.paygate.example/v2/`).
- **2026-08-30T03:12:00Z**: Alert fires: `charge_failed rate 100% for 4m`.
- **2026-08-30T03:15:00Z**: Investigation checks logs, config, and probes the vendor API.

## Root Cause
**bad_config_deploy**: The deploy of `payments-2.15.0` misconfigured `PAYGATE_URL` to `https://api.paygate.example/v2/`, causing all payment requests to result in HTTP 404 errors from the payment gateway.

## Evidence
- `recent_changes`: `payments-api: payments-2.15.0: migrate to PayGate v2 endpoints (by dana) detail: PAYGATE_URL: https://api.paygate.example -> https://api.paygate.example/v2/`
- `query_logs`: `payments-api` logs show repeated `paygate request failed: status=404` errors.
- `run_probe`: Probing `https://api.paygate.example/v2/` returned `200` (vendor is healthy, but specific API requests from the app are failing due to the bad base URL path/routing).

## Proposed Remediation
Roll back the `payments-api` deploy to the previous stable version (or revert the `PAYGATE_URL` configuration). Given the deployment change, rolling back the deploy is the standard and safe action.

## Follow-ups
1. Verify PayGate v2 API documentation and path requirements before re-attempting migration.
2. Add integration tests verifying PayGate connectivity during CI/CD.