# Incident Report: Payments-API Authentication Failures (Clock Skew)

## Summary
At 2026-08-30T03:12:00Z, `api-gateway` fired an alert for a high 401 error rate (~9.5%) on `/v1/checkout`. Investigation revealed that `payments-api` was failing to verify newly issued JWTs because its system clock drifted following a host reboot.

## Timeline
- **02:02Z**: `payments-api` host (`payments-3`) rebooted after kernel patch.
- **02:39Z**: `auth-api` deployed auth-1.6.0 switching JWT signing algorithm to ES256.
- **02:54Z**: First `jwt verification failed: InvalidIssuedAt` logs appear in `payments-api`.
- **03:12Z**: P1 Alert fired as 401 error rate spiked to ~9.5% on `/v1/checkout`.

## Root Cause
The node reboot of `payments-3` (hosting `payments-api`) introduced a clock skew, causing tokens issued with ES256 to fail `InvalidIssuedAt` validation checks against `payments-api`'s drifted local system time.

## Evidence
- Recent infrastructure change: `payments-api` node rebooted at 02:02Z.
- Log errors: `payments-api: jwt verification failed: InvalidIssuedAt sub=user_30099 alg=ES256`.
- Metric spike: `payments-api.error_rate_pct` jumped from ~0.4% to ~90% starting at 02:54Z.

## Remediation
1. Sync the system clock on the `payments-api` host (`payments-3`).
2. Verify that JWT verification succeeds and error rates return to normal.

## Follow-ups
- Ensure NTP/Chrony service is correctly configured and enabled on all hosts to prevent drift after reboots.
- Add monitoring for clock skew across all microservices.