# Incident Report: Clock Skew on payments-api

## Summary
At 2026-08-30T03:12:00.000Z, `api-gateway` fired an alert for a high 401 rate (9.5%) on `/v1/checkout`, while `auth-api` reported healthy. Investigation revealed a clock skew on `payments-api` caused by chronyd failing to restart after a scheduled host reboot following a kernel patch.

## Timeline
- **02:02:00 UTC**: `payments-api` host (`payments-3`) rebooted after a kernel patch. Chronyd failed to start automatically upon reboot.
- **02:39:00 UTC**: `auth-api` deployed auth-1.6.0 (switch JWT signing to ES256 with dual-verify).
- **03:12:00 UTC**: Alert fires on `api-gateway` for 401 errors on `/v1/checkout`.

## Root Cause
`clock_skew` on `payments-api`. Following a node reboot (`payments-3`) at 02:02 UTC, `chronyd` did not start up, resulting in a time drift of -412.3 seconds. When `payments-api` issues or verifies JWT/token-secured requests or timestamps with auth tokens, the clock offset causes validation failures (tokens appearing either in the future or expired), resulting in 401 unauthorized responses.

## Evidence
- `run_probe clock payments-api`: `payments-api (node payments-3) ntp offset -412.3s — chronyd not running`
- `run_probe clock api-gateway`: `api-gateway ntp offset 0.003s`
- `run_probe clock auth-api`: `auth-api ntp offset 0.002s`
- Alert message: `401 rate 9.5% on /v1/checkout; auth-api healthy`

## Proposed Remediation
Sync the clock on `payments-api` / restart `chronyd` on node `payments-3`. (Action: `sync_clock` targeting `payments-api`). This is safe as it restores correct NTP time synchronization without restarting application services or losing state.

## Follow-ups
- Ensure chronyd is properly enabled as a systemd service across all infrastructure hosts on boot.
