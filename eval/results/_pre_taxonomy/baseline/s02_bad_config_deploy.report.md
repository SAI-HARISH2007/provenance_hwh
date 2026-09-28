# Incident Report: payments-api Charge Failures

## Summary
At 2026-08-30T03:12:00.000Z, the `payments-api` service experienced a 100% failure rate on all charge requests (`charge_failed rate 100% for 4m`). The incident was triggered by a recent deployment introducing an incorrect upstream URL configuration.

## Timeline
- **2026-08-30T03:03:00.000Z**: `payments-api: payments-2.15.0` deployed with updated `PAYGATE_URL` (`https://api.paygate.example/v2/`).
- **2026-08-30T03:12:00.000Z**: P1 Alert fires indicating 100% charge failures.

## Root Cause
A bad configuration deployment (`bad_config_deploy`) in `payments-api` version `payments-2.15.0` appended an invalid `/v2/` path suffix to `PAYGATE_URL`, causing all upstream requests to return `404 Not Found`.

## Evidence
- Recent Change entry: `[deploy] payments-api: payments-2.15.0: migrate to PayGate v2 endpoints (dana) PAYGATE_URL: https://api.paygate.example -> https://api.paygate.example/v2/`
- Error logs showing constant 404 responses from PayGate: `ERROR payments-api: paygate request failed: status=404`

## Remediation
1. Rollback the `payments-api` deployment to the previous stable version (or correct the `PAYGATE_URL` configuration).

## Follow-ups
- Verify PayGate v2 endpoint paths and API integration tests prior to deployment.
- Implement staging verification checks for external API URL configurations.