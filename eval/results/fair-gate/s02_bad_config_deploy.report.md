# Incident Report: Payments-API Outage Due to Bad Config / Deploy

## Summary
At 2026-08-30T03:12:00Z, a P1 page fired for `payments-api` indicating a 100% failure rate on charges. Investigation revealed this was caused by the `payments-2.15.0` deployment at 03:03:00Z, which reconfigured `PAYGATE_URL` to `https://api.paygate.example/v2/` (with a trailing slash), resulting in 404 errors on downstream requests.

## Timeline
- **03:03:00Z**: `payments-api` deployed version `payments-2.15.0` migrating to PayGate v2 endpoints (`PAYGATE_URL` set to `https://api.paygate.example/v2/`).
- **03:03:00Z - onwards**: `payments-api` error rate spikes from ~0.4% to 100%.
- **03:12:00Z**: P1 alert fires (`charge_failed rate 100% for 4m`).
- **03:12:30Z**: Investigation initiated; metrics, logs, recent changes, and config examined.

## Root Cause
A bad configuration update/deploy (`bad_config_deploy`) in `payments-api` (`payments-2.15.0`) introduced an invalid/malformed `PAYGATE_URL` with a trailing slash, breaking all outbound payment requests.

## Evidence
- `recent_changes`: `payments-api: payments-2.15.0: migrate to PayGate v2 endpoints` with `PAYGATE_URL: https://api.paygate.example -> https://api.paygate.example/v2/`.
- `get_metrics`: `payments-api.error_rate_pct` jumped from 0.4% to >100% exactly at the deploy timestamp (03:03).
- `get_config`: `PAYGATE_URL` is configured as `"https://api.paygate.example/v2/"`.
- `query_logs`: `payments-api` logs show repeated `paygate request failed: status=404`.

## Proposed Remediation
Roll back the `payments-api` deployment (`rollback_deploy`) to the previous stable version (`payments-2.14.x` or previous working config/version) or update the config to remove the trailing slash. Rolling back the deployment is safe and instantly restores the previous working state.

## Follow-ups
1. Add validation for URL configurations (e.g. trailing slash checks) in the CI/CD pipeline or service startup checks.
2. Update integration tests to cover PayGate v2 endpoint routing.