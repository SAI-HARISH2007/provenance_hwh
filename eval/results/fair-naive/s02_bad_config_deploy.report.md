# Incident Report: Payments-API PayGate v2 Deployment Failure

## Summary
At 2026-08-30T03:12:00Z, the `payments-api` service began alerting with a 100% failure rate on charges (`charge_failed rate 100% for 4m`). Investigation revealed that a deployment (`payments-2.15.0`) shipped at 03:03:00Z to migrate to PayGate v2 endpoints (`PAYGATE_URL: https://api.paygate.example/v2/`) introduced 404 errors on all outgoing requests to PayGate.

## Timeline
- **2026-08-30T03:03:00Z**: `payments-api` version `payments-2.15.0` deployed, updating `PAYGATE_URL` to `https://api.paygate.example/v2/`.
- **2026-08-30T03:03:00Z - 03:11:52Z**: In-flight requests or retries occasionally succeeded or logged, but error rate sharply climbed to nearly 100%.
- **2026-08-30T03:12:00Z**: `payments-api` P1 alert fires (`charge_failed rate 100% for 4m`).
- **03:15:00Z**: Investigation and probe confirm PayGate vendor is healthy, but the configured v2 endpoint URL results in 404 Not Found errors.

## Root Cause
A bad configuration/deploy (`bad_config_deploy`) in `payments-2.15.0` updated the PayGate base URL to an incorrect or non-existent v2 path (`https://api.paygate.example/v2/`), causing all API requests to fail with HTTP 404.

## Evidence
- `get_alert`: `payments-api` P1 `charge_failed rate 100% for 4m`.
- `recent_changes`: `payments-api: payments-2.15.0: migrate to PayGate v2 endpoints (PAYGATE_URL: https://api.paygate.example -> https://api.paygate.example/v2/)` at `2026-08-30T03:03:00Z`.
- `get_metrics`: `payments-api.error_rate_pct` jumped from ~0.4% to ~100% immediately following the deploy.
- `query_logs`: Repeated `ERROR payments-api: paygate request failed: status=404`.
- `run_probe`: Confirmed vendor endpoint status returns 200, proving the base URL path configured in the deployment is wrong.

## Proposed Remediation
Roll back the `payments-api` deployment (`rollback_deploy`) to the previous stable version (`payments-2.14.x` or prior) to restore correct communication with the payment gateway. This is safe because it reverts to the previously working configuration and endpoints.

## Follow-ups
- Verify correct PayGate v2 API documentation and path with the vendor before attempting another migration.
- Add staging integration tests for third-party endpoint migrations.