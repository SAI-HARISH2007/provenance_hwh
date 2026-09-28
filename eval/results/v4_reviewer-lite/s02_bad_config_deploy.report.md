# Incident Report: payments-api Charge Failures

## Summary
At 2026-08-30T03:12:00.000Z, `payments-api` began failing 100% of charges (`charge_failed rate 100%`). Investigation revealed that a recent deploy (`payments-2.15.0`) at 03:03 UTC updated `PAYGATE_URL` to `https://api.paygate.example/v2/`, resulting in 404 Not Found errors when calling PayGate endpoints.

## Timeline
- **2026-08-30T03:03:00.000Z**: `payments-api` deployed version `payments-2.15.0`, migrating to PayGate v2 endpoints by changing `PAYGATE_URL` to `https://api.paygate.example/v2/`.
- **2026-08-30T03:12:00.000Z**: Paging alert fires due to 100% charge failure rate over 4 minutes.
- **Investigation**: Logs showed constant `404` responses from PayGate. Probing `https://api.paygate.example/v2/status` succeeded, but updating the base URL configuration to include `/v2/` broke the relative endpoint paths used by the API client.

## Root Cause
A bad configuration deploy (`bad_config_deploy`) where `PAYGATE_URL` was incorrectly configured with a trailing `/v2/` path, causing all downstream requests to hit non-existent URLs (404).

## Proposed Remediation
Update the configuration of `payments-api` to correct `PAYGATE_URL` back to `https://api.paygate.example` (or the correct base URL without the extra path component, letting the client append `/v2/...` correctly).

## Follow-ups
- Add integration tests verifying PayGate connectivity during deploys.
- Ensure URL configuration changes validate endpoint existence during startup or via staging smoke tests.