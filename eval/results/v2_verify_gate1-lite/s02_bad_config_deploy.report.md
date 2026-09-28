# Incident Report: payments-api Charge Failure

## Summary
At 2026-08-30T03:12:00.000Z, `payments-api` began experiencing 100% charge failures (`charge_failed rate 100% for 4m`), causing `api-gateway` to become degraded and the `payments-api` service to go down. The root cause was a recent bad configuration/deploy (`payments-2.15.0`) which misconfigured the PayGate v2 endpoint URL.

## Timeline
- **2026-08-30T03:03:00.000Z**: `payments-api` deployed version `payments-2.15.0` ("migrate to PayGate v2 endpoints") updating `PAYGATE_URL` to `https://api.paygate.example/v2/`.
- **2026-08-30T03:12:00.000Z**: `payments-api` alert fires (`charge_failed rate 100% for 4m`).
- **Investigation**: Logs for `payments-api` show continuous HTTP 404 errors when making requests to PayGate. A probe to `api.paygate.example` confirmed the vendor is healthy and exposes endpoints at `/v2/status`, revealing that appending path segments to the base URL `https://api.paygate.example/v2/` results in invalid 404 paths (e.g. `/v2//charges`).

## Root Cause
`bad_config_deploy`: The deploy of `payments-2.15.0` incorrectly configured `PAYGATE_URL` with a trailing `/v2/`, breaking all outgoing API calls to PayGate v2.

## Evidence
- Recent changes show `payments-api` deployed at 03:03 with `PAYGATE_URL: https://api.paygate.example/v2/`.
- `query_logs` for `payments-api` returned multiple `status=404` errors on PayGate requests.
- `run_probe` on `api.paygate.example` successfully reached `https://api.paygate.example/v2/status` (200 OK), confirming the API base URL should not include `/v2/`.

## Proposed Remediation
Roll back the deployment of `payments-api` to the previous stable version (or correct the `PAYGATE_URL` configuration to `https://api.paygate.example`). Rolling back is safe as it immediately reverts the incorrect URL configuration and restores previous communication with PayGate.
