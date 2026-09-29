# Incident Report: Payments API Outage

## Summary
At 03:12 UTC, the `payments-api` service triggered a P1 alert indicating a 100% charge failure rate. Investigation revealed that a recent deployment (`payments-2.15.0`) incorrectly updated the `PAYGATE_URL` configuration to point to a non-existent endpoint path (`/v2/`), resulting in 404 errors on all outgoing payment requests.

## Timeline
- **03:03 UTC**: Deployment `payments-2.15.0` applied to `payments-api`, changing `PAYGATE_URL` to include `/v2/`.
- **03:12 UTC**: `payments-api` charge failure rate hits 100%; P1 alert fires.
- **03:12 UTC**: Incident response initiated.

## Root Cause
A bad configuration/endpoint change in deploy `payments-2.15.0` targeted an invalid PayGate URL (`https://api.paygate.example/v2/`).

## Evidence
- Deployment log: `PAYGATE_URL: https://api.paygate.example -> https://api.paygate.example/v2/`
- Application logs showing persistent 404 errors: `ERROR payments-api: paygate request failed: status=404`
- Alert: `charge_failed rate 100% for 4m`

## Remediation
1. Rollback the `payments-api` service deployment to the previous stable version (or revert the `PAYGATE_URL` config change).

## Follow-ups
- Verify PayGate v2 API path requirements and ensure integration tests validate upstream URL correctness pre-deploy.
- Add smoke tests checking upstream reachability during deployment pipelines.