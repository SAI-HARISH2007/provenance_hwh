# Incident Report: Payments-API 401 Rate Spike due to Clock Skew

## Summary
At 2026-08-30T03:12:00Z, a P1 alert fired for `api-gateway` reporting a 9.5% 401 error rate on `/v1/checkout`, with `payments-api` marked degraded. Investigation revealed that `payments-api` pod instances running on node `payments-3` were experiencing a massive error rate spike (~84–92%) due to JWT verification failures (`InvalidIssuedAt`).

## Timeline
- **02:02:00 UTC**: Node `payments-3` rebooted following a kernel patch (by ops-bot).
- **02:39:00 UTC**: `auth-api` deployed `auth-1.6.0`, switching JWT signing to ES256 with dual-verify enabled.
- **02:54:00 UTC onwards**: `payments-api` logs begin showing persistent `jwt verification failed: InvalidIssuedAt` warnings for ES256 tokens.
- **03:12:00 UTC**: Alert fires on `api-gateway` for `/v1/checkout` 401 errors.

## Root Cause
Following the node reboot at 02:02 UTC, chronyd failed to start or sync on node `payments-3`, causing the system clock on `payments-api` pods to drift by **-412.3 seconds** (over 6 minutes behind real time). When `auth-api` began issuing ES256 tokens, `payments-api` evaluated the `iat` (issued-at) claim against its own skewed local clock, resulting in `InvalidIssuedAt` rejections and HTTP 401 errors.

## Evidence
- **Clock Probe**: `run_probe` on `payments-api` (node `payments-3`) returned an NTP offset of **-412.3s** with `chronyd not running`.
- **Logs**: `query_logs` for `payments-api` showed continuous `jwt verification failed: InvalidIssuedAt sub=... alg=ES256`.
- **Metrics**: `get_metrics` for `payments-api` error rate showed a sharp jump from ~0.4% to ~90% right after the node reboot.
- **Recent Changes**: Node rebooted at 02:02:00 UTC.

## Proposed Remediation
- **Action**: `sync_clock` on `payments-api` (target: `payments-api` / node `payments-3`).
- **Why it is safe**: Syncing the clock via NTP/chronyd or restarting the time sync daemon corrects the local system time without altering application state or restarting stateful databases.
