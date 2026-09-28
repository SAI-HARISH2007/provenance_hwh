# Incident Report: Payments-API Outage

## Summary
At 2026-08-30T03:12:00.000Z, `payments-api` experienced a 100% error rate on charge requests, causing a P1 page. Investigation revealed this was caused by a bad configuration deploy at 03:03 (`payments-2.15.0`) which misconfigured `PAYGATE_URL` to point to a non-existent `/v2/` base path suffix, resulting in HTTP 404 errors from the payment gateway.

## Timeline
- **2026-08-30T03:03:00.000Z**: `payments-api` deployed version `payments-2.15.0`, changing `PAYGATE_URL` from `https://api.paygate.example` to `https://api.paygate.example/v2/`.
- **2026-08-30T03:03:30.000Z**: Error rate spikes from ~0.4% to 100%.
- **2026-08-30T03:12:00.000Z**: P1 alert fires (`charge_failed rate 100% for 4m`).
- **2026-08-30T03:15:00.000Z**: Investigation identifies bad URL config in recent deploy.

## Root Cause
`bad_config_deploy`: The `payments-2.15.0` deployment incorrectly appended `/v2/` to the base `PAYGATE_URL` config, causing all API requests to hit invalid endpoints (resulting in 404s).

## Evidence
- `recent_changes`: Shows `payments-2.15.0` migrated `PAYGATE_URL: https://api.paygate.example -> https://api.paygate.example/v2/` at 03:03.
- `get_metrics`: `payments-api.error_rate_pct` jumped from ~0.4% to ~100% right after the deploy.
- `query_logs`: Shows persistent `status=404` errors on PayGate requests.
- `run_probe`: Confirmed target `https://api.paygate.example/v2/status` returns 200, confirming the host is up but the specific URL construction / path usage in the deploy caused the routing failure.

## Proposed Remediation
`rollback_deploy` for `payments-api` to revert to version `payments-2.15.0` (or update config to remove the `/v2/` suffix from the base URL). Rolling back the deployment is safe and immediately restores the correct configuration.
