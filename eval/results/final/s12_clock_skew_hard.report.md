# Incident Report: Payments-API Clock Skew Causing 401 Auth Failures

## Summary
At 2026-08-30T03:12:00.000Z, `api-gateway` fired a P1 alert for a 9.5% 401 rate on `/v1/checkout`, while `auth-api` was reported healthy. Investigation revealed that `payments-api` (running on host `payments-3`, which was recently rebooted following a kernel patch) experienced severe clock drift of -412.3 seconds due to `chronyd` failing to start on reboot. Because JWT validation relies on time-sensitive `nbf` (not before) and `exp` (expiration) claims, tokens issued by `auth-api` were rejected as "not yet valid" or expired by `payments-api`, resulting in 401 unauthorized responses.

## Timeline
- **2026-08-30T02:02:00Z**: `payments-api` host (`payments-3`) rebooted after a kernel patch. `chronyd` failed to start automatically upon reboot.
- **2026-08-30T02:39:00Z**: `auth-api` deployed version `auth-1.6.0` (switching JWT signing to ES256).
- **2026-08-30T03:12:00Z**: `api-gateway` alerts on high 401 rate on `/v1/checkout`.
- **2026-08-30T03:15:00Z**: Investigation via `run_probe` reveals `payments-api` has a clock offset of -412.3s.

## Root Cause
**clock_skew**: The host node running `payments-api` had its clock skewed by over 6 minutes (-412.3s) because `chronyd` was not running after the host reboot at 02:02Z. This caused token validation to fail due to time claim mismatches (`nbf`/`exp`).

## Evidence
1. Alert: `{"service": "api-gateway", "severity": "P1", "message": "401 rate 9.5% on /v1/checkout; auth-api healthy"}`
2. Probe result (`run_probe clock payments-api`): `payments-api (node payments-3) ntp offset -412.3s — chronyd not running`
3. Probe result (`run_probe clock auth-api`): `auth-api ntp offset 0.002s` (healthy)

## Proposed Remediation
`sync_clock` on `payments-api` (start `chronyd` / synchronize time with NTP). This is safe as it corrects the node time to match cluster time without requiring service restarts or deploys.

## Follow-ups
1. Investigate why `chronyd` failed to start on `payments-3` after the kernel patch reboot.
2. Add monitoring/alerting for host clock offset across all pods/nodes.
