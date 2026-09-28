# Incident Report: payments-api Charge Failures

## Summary
At 2026-08-30T03:12:00Z, an alert fired indicating a 100% failure rate for charges on the `payments-api` service. Investigation revealed that a recent deployment (`payments-2.15.0`) introduced a bad configuration pointing to non-existent `/v2/` endpoints on the PayGate upstream service, leading to continuous HTTP 404 errors.

## Timeline
- **03:03:00Z**: `payments-api` deployed version `payments-2.15.0` updating `PAYGATE_URL` to append `/v2/`.
- **03:12:00Z**: Alert fires as `payments-api` experiences 100% charge failures.

## Root Cause
A bad configuration deploy (`bad_config_deploy`) updated `PAYGATE_URL` to an invalid path (`https://api.paygate.example/v2/`), causing all downstream payment gateway requests to return 404 Not Found.

## Evidence
- Change log shows `PAYGATE_URL` modified to `https://api.paygate.example/v2/` at 03:03:00Z.
- Metrics show `payments-api.error_rate_pct` spiking to ~100% right after the deployment.
- Logs continuously report `ERROR payments-api: paygate request failed: status=404`.

## Remediation
- Roll back `payments-api` to the previous stable deployment (`payments-2.14.x` or equivalent prior version) or fix the `PAYGATE_URL` configuration.

## Follow-ups
- Verify upstream API contract versioning before updating base URLs in future deployments.
- Add integration tests verifying upstream connectivity during the deployment pipeline.