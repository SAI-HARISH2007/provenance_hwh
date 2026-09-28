# Incident Report: Payments-API PayGate v2 Migration Failure

## Summary
At 2026-08-30T03:12:00.000Z, `payments-api` began failing 100% of charges (`charge_failed rate 100%`), causing the service to go down and `api-gateway` to become degraded. Investigation revealed this immediately followed the deployment of `payments-2.15.0` at 03:03:00 UTC, which migrated the `PAYGATE_URL` configuration to `https://api.paygate.example/v2/`. The v2 endpoint configuration results in 404 Not Found errors when `payments-api` attempts to process charges.

## Timeline
- **2026-08-30T03:03:00.000Z**: `payments-api` deployed version `payments-2.15.0` (migrate to PayGate v2 endpoints, changing `PAYGATE_URL` to `https://api.paygate.example/v2/`).
- **2026-08-30T03:12:00.000Z**: Alert fires: `payments-api` `charge_failed rate 100% for 4m`.
- **2026-08-30T03:12:00.000Z+**: Investigation confirms 404 errors on PayGate requests due to the invalid v2 endpoint configuration.

## Root Cause
**bad_config_deploy**: The deployment of `payments-2.15.0` introduced an incorrect `PAYGATE_URL` configuration (`https://api.paygate.example/v2/`), causing all payment requests to fail with HTTP 404.

## Evidence
- `recent_changes`: `payments-api: payments-2.15.0: migrate to PayGate v2 endpoints (by dana) detail: PAYGATE_URL: https://api.paygate.example -> https://api.paygate.example/v2/`
- `query_logs`: `payments-api` logs show repeated `paygate request failed: status=404` errors.
- `get_alert`: `payments-api` status is `down` with `charge_failed rate 100%`.

## Proposed Remediation
Roll back the `payments-api` deploy (`rollback_deploy` on `payments-api`), reverting the service to the previous stable version (`payments-2.14.x` or prior) with the correct `PAYGATE_URL` (`https://api.paygate.example`). This is safe as it restores the known-good configuration and endpoints used prior to the bad deployment.
