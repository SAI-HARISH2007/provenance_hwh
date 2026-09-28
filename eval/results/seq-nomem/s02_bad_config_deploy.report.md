# Incident Report: Payments API Failure due to Bad PayGate v2 Migration Deploy

## Summary
At 2026-08-30T03:12:00Z, a P1 alert fired indicating a 100% failure rate on `payments-api` (`charge_failed`). Investigation revealed that a recent deploy (`payments-2.15.0`) updated the `PAYGATE_URL` configuration to use unreleased or incorrect v2 endpoints (`https://api.paygate.example/v2/`), resulting in HTTP 404 errors on all payment charges.

## Timeline
- **2026-08-30T03:03:00Z**: `payments-api` deployed version `payments-2.15.0` ("migrate to PayGate v2 endpoints", updating `PAYGATE_URL` to `https://api.paygate.example/v2/`).
- **2026-08-30T03:12:00Z**: P1 alert fired: `payments-api` charge_failed rate at 100% for 4 minutes.
- **Investigation**: Inspected logs, config, and recent changes; verified vendor is up via probe.

## Root Cause
`bad_config_deploy`: The deploy of `payments-api` (v2.15.0) misconfigured `PAYGATE_URL` to point to non-existent `/v2/` endpoints, causing all payment requests to fail with HTTP 404.

## Evidence
- `recent_changes`: `2026-08-30T03:03:00.000Z [deploy] payments-api: payments-2.15.0: migrate to PayGate v2 endpoints (PAYGATE_URL: https://api.paygate.example -> https://api.paygate.example/v2/)`
- `query_logs` on `payments-api`: Recurring `ERROR payments-api: paygate request failed: status=404` errors.
- `get_config` on `payments-api`: Confirms `PAYGATE_URL` is set to `https://api.paygate.example/v2/`.

## Proposed Remediation
Roll back the `payments-api` deployment (`rollback_deploy` on `payments-api`) to restore the previous working version (`payments-2.14.x` or prior) and correct `PAYGATE_URL`.
