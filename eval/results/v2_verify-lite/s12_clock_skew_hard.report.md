# Incident Report: Payments API Clock Skew After Host Reboot

## Summary
At 2026-08-30T03:12:00.000Z, `api-gateway` alerted on 401 rate of 9.5% on `/v1/checkout`. Investigation revealed that `payments-api` error rate spiked to ~84-92% due to JWT verification failures (`InvalidIssuedAt`). The root cause was clock skew on host `payments-3` following a node reboot at 02:02 UTC, where `chronyd` was not running, leaving the clock skewed by -412.3 seconds relative to `auth-api` and token issuers.

## Timeline
- **02:02:00.000Z**: `payments-api` host `payments-3` rebooted after a kernel patch. `chronyd` failed to start or sync.
- **02:39:00.000Z**: `auth-api` deployed `auth-1.6.0` switching JWT signing to ES256 (dual-verify enabled).
- **02:54:00.000Z - 03:12:00.000Z**: `payments-api` logs flood with `jwt verification failed: InvalidIssuedAt` because the node's local time is ~412 seconds behind actual time, making incoming tokens appear to be issued in the future.
- **03:12:00.000Z**: P1 alert fired on `api-gateway` for 401 errors on `/v1/checkout`.

## Root Cause
`clock_skew`: Following a host reboot on `payments-3`, time synchronization (`chronyd`) was not running, causing a -412.3s clock skew. This caused JWT `iat` (issued at) validations to fail with `InvalidIssuedAt`.

## Evidence
- **Recent Changes**: Node rebooted at 02:02:00.000Z for `payments-api` (node `payments-3`).
- **Logs**: `payments-api` logs showed repeated warnings: `jwt verification failed: InvalidIssuedAt sub=... alg=ES256`.
- **Clock Probe**: `run_probe` on `payments-api` returned `ntp offset -412.3s — chronyd not running`. `auth-api` probe showed `0.002s`.

## Proposed Remediation
`sync_clock` on `payments-3` (start `chronyd` / synchronize time). This is safe because syncing time restores correct NTP synchronization without restarting application containers or mutating business data.

## Follow-ups
1. Ensure `chronyd` is enabled and configured to start automatically on boot for all node groups.
2. Add monitoring/alerting for node NTP offset and chrony service status.
