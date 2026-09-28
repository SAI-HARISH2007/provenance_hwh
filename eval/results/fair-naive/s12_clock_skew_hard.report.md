# Incident Report: Payments API Auth Failures due to Clock Skew

## Summary
At 2026-08-30T03:12:00Z, an alert fired for `api-gateway` due to elevated 401 errors on `/v1/checkout`. Investigation revealed that `payments-api` was experiencing a massive error rate spike (~90%) due to JWT verification failures (`InvalidIssuedAt`) on ES256 tokens issued by `auth-api`.

## Timeline
- **02:02 UTC**: Infrastructure event: `payments-api` host node (`payments-3`) rebooted after kernel patch. `chronyd` failed to start or sync.
- **02:39 UTC**: `auth-api` deployed version `auth-1.6.0`, switching JWT signing to ES256.
- **02:54 UTC**: First `InvalidIssuedAt` log warnings observed as `payments-api` evaluated tokens issued by `auth-api` with timestamps shifted by its unsynced clock.
- **03:12 UTC**: P1 alert fired.

## Root Cause
`clock_skew`: The node hosting `payments-api` (`payments-3`) rebooted at 02:02 UTC and its NTP service (`chronyd`) failed to run, leaving the system clock 412.3 seconds behind actual time. When `auth-api` started issuing ES256 tokens with `iat` timestamps matching real-time, `payments-api` rejected them as originating in the future (`InvalidIssuedAt`).

## Evidence
- `payments-api` logs: Repeated `jwt verification failed: InvalidIssuedAt` entries.
- `run_probe (kind: clock, target: payments-api)`: `payments-api (node payments-3) ntp offset -412.3s — chronyd not running`.
- `run_probe (kind: clock, target: auth-api)`: `auth-api ntp offset 0.002s`.

## Proposed Remediation
`sync_clock`: Resync the system clock on `payments-3` (restart `chronyd` and sync via NTP). This is safe and directly addresses the clock offset causing the JWT validation failures.

## Follow-ups
- Ensure `chronyd` is enabled and reliably starts on boot for all Kubernetes nodes / EC2 instances.
