# Incident Report: payments-api 100% Failure Rate

## Summary
At 2026-08-30T03:12:00Z, an alert fired indicating a 100% failure rate for charges in `payments-api`. The incident was triggered by a recent deployment (`payments-2.15.0`) which introduced a misconfigured `PAYGATE_URL` pointing to an invalid `/v2/` endpoint.

## Timeline
- **2026-08-30T03:03:00.000Z**: `payments-api` deployed version `payments-2.15.0` updating `PAYGATE_URL` to include `/v2/`.
- **2026-08-30T03:12:00.000Z**: `payments-api` alert fires (`charge_failed rate 100% for 4m`).

## Root Cause
A bad configuration/deploy in `payments-api` (`payments-2.15.0`) updated the `PAYGATE_URL` to an incorrect endpoint path (`https://api.paygate.example/v2/`), causing all downstream calls to fail.

## Evidence
- Recent changes log showing `payments-api` deploy at `03:03:00.000Z` migrating to PayGate v2 endpoints.
- P1 Alert: `charge_failed rate 100% for 4m` starting shortly after the deployment.

## Remediation
- Roll back `payments-api` to the previous stable version or correct the `PAYGATE_URL` configuration.

## Follow-ups
- Verify PayGate v2 integration path requirements with the vendor before attempting future endpoint migrations.
- Add integration tests verifying external payment gateway endpoints during deployment pipelines.