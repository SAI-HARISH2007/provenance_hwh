# Incident Report: payments-api Charge Failures

## Summary
At 2026-08-30T03:12:00.000Z, a P1 alert fired indicating `payments-api` had a 100% charge failure rate. Investigation revealed that a recent deploy (`payments-2.15.0`) at 03:03 UTC updated `PAYGATE_URL` to append `/v2/`, which resulted in 404 errors on all outbound requests to the PayGate API.

## Timeline
- **2026-08-30T03:03:00.000Z**: `payments-api` deployed version `payments-2.15.0` (migrate to PayGate v2 endpoints, changing `PAYGATE_URL` to `https://api.paygate.example/v2/`).
- **2026-08-30T03:12:00.000Z**: P1 alert fired (`charge_failed rate 100% for 4m`).

## Root Cause
A bad configuration / deploy (`bad_config_deploy`) in `payments-api` (`payments-2.15.0`) introduced an incorrect base URL (`https://api.paygate.example/v2/`), causing all API requests to hit non-existent endpoints (404 Not Found).

## Evidence
- `recent_changes`: Deploy at 03:03:00 UTC updated `PAYGATE_URL` to `https://api.paygate.example/v2/`.
- `get_metrics`: `payments-api` error rate jumped from ~0.4% to ~100% right after the 03:03 deploy.
- `query_logs`: Continuous HTTP 404 errors on PayGate requests from `payments-api`.
- `get_config`: Confirmed `PAYGATE_URL` is set to `https://api.paygate.example/v2/`.

## Proposed Remediation
Roll back the `payments-api` deploy (`rollback_deploy`) to the previous stable version (`payments-2.15.0` -> `payments-2.14.x` or prior configuration). This is safe because it reverts the endpoint URL change back to the working version.
