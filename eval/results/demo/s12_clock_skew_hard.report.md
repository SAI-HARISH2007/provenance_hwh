# Incident Report: API Gateway 401 Rate Spike on Checkout

## Summary
At 03:12 UTC, a P1 alert fired for a 9.5% 401 Unauthorized rate on `/v1/checkout` routed through `api-gateway`, while `auth-api` was reported healthy. Investigation revealed that a recent node reboot of `payments-api` left chronyd stopped, causing a -412.3-second clock skew on `payments-api` (node `payments-3`). Because token validation (JWT expiration / `nbf` / `iat` checks) depends on accurate time, tokens received by `payments-api` failed verification due to the severe clock skew, returning 401 errors.

## Timeline
- **02:02:00 UTC**: `payments-api` node (`payments-3`) rebooted after kernel patch by `ops-bot`. Chronyd failed to start automatically upon reboot.
- **02:39:00 UTC**: `auth-api` deployed version `auth-1.6.0` (switch JWT signing to ES256, dual-verify enabled).
- **03:12:00 UTC**: Alert fires: 401 rate 9.5% on `/v1/checkout`.

## Root Cause
- **Root Cause Label**: `clock_skew`
- **Service**: `payments-api`
- **Explanation**: Following the kernel patch reboot at 02:02 UTC, chronyd was not running on node `payments-3` hosting `payments-api`, resulting in a -412.3-second clock offset. Requests involving `payments-api` failed JWT time validation (`nbf`/`exp`), causing 401 responses.

## Evidence
1. `run_probe` with `kind: clock` on `payments-api` returned: `payments-api (node payments-3) ntp offset -412.3s — chronyd not running`.
2. `get_metrics` for `api-gateway` `error_rate_pct` showed a sharp jump from ~0.3% to ~9.5% at minute 14.
3. Clocks on `auth-api` and `api-gateway` were accurate (offsets < 0.003s).

## Proposed Remediation
- **Action**: `sync_clock` on `payments-api`.
- **Safety**: Synchronizing the clock via NTP / starting chronyd restores correct time validation without restarting stateful databases or rolling back unrelated deployments.

## Follow-ups
- Ensure chronyd service configuration is set to start automatically on boot for all infrastructure nodes following kernel patches.
