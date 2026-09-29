# Incident Report: Payments-API Outage Due to Bad Config / Incorrect PayGate URL

## Summary
At 2026-08-30T03:12:00Z, `payments-api` experienced a 100% failure rate on charges (`charge_failed`), causing `api-gateway` to become degraded. Investigation revealed that a recent deploy (`payments-2.15.0`) at 03:03:00Z updated the `PAYGATE_URL` configuration to `https://api.paygate.example/v2/`, which appended `/v2/` to endpoint paths (resulting in requests to `/v2/v2/...`), leading to 404 errors from the third-party gateway.

## Timeline
- **2026-08-30T03:03:00Z**: `payments-api` deployed version `payments-2.15.0` with config change: `PAYGATE_URL: https://api.paygate.example -> https://api.paygate.example/v2/`
- **2026-08-30T03:12:00Z**: `payments-api` alert fires (`charge_failed rate 100% for 4m`).
- **2026-08-30T03:15:00Z**: Investigation confirms 404 responses from PayGate due to double-appended `/v2/v2/` paths.

## Root Cause
`bad_config_deploy`: The configuration update in `payments-2.15.0` incorrectly set `PAYGATE_URL` to include the `/v2/` path suffix, while the application code also appends `/v2/` or specific endpoint paths, resulting in invalid URLs (404 Not Found).

## Evidence
- `recent_changes`: `payments-api: payments-2.15.0: migrate to PayGate v2 endpoints (PAYGATE_URL: https://api.paygate.example -> https://api.paygate.example/v2/)`
- `query_logs`: `payments-api` logs showing continuous `status=404` for PayGate requests.
- `get_config`: Confirmed `PAYGATE_URL` is set to `https://api.paygate.example/v2/`.
- `run_probe`: Verified vendor is up (`https://api.paygate.example/v2/status` -> 200).

## Proposed Remediation
Update `payments-api` config (`update_config`) to revert `PAYGATE_URL` back to `https://api.paygate.example` (or the correct base URL without the path suffix), allowing the application to correctly form `/v2/...` request paths.
