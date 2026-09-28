# Incident Report: payments-api Secret Rotation Failure

## Summary
At 2026-08-30T03:12:00.000Z, `payments-api` experienced a 100% charge failure rate, causing `api-gateway` to become degraded and triggering a P1 page. The root cause is a secret rotation (`PAYGATE_API_KEY v7 -> v8`) that occurred at 03:04 UTC where the old key was revoked at the vendor. Because `payments-api` caches secrets at process start time, it continued using the revoked key version `v7`, resulting in 401 Unauthorized responses from Paygate.

## Timeline
- **2026-08-30T03:01:00.000Z**: `payments-api` deployed version `payments-2.16.0` (retry jitter).
- **2026-08-30T03:04:00.000Z**: Vault scheduled 90-day rotation: `PAYGATE_API_KEY` rotated from `v7` to `v8`, and `v7` was revoked at the vendor.
- **2026-08-30T03:12:00.000Z**: `payments-api` alert fires due to 100% charge failures.

## Root Cause
`secret_rotation`: `payments-api` holds the API key in memory from process start time and did not pick up the new `v8` key after Vault rotation, resulting in authentication failures against Paygate.

## Evidence
- `get_alert`: `payments-api` service status is `down`, `charge_failed rate 100%`.
- `recent_changes`: Vault 90-day rotation at 03:04:00 UTC moved `PAYGATE_API_KEY` from `v7` to `v8` and revoked `v7`.
- `query_logs`: `payments-api` logs show continuous `401` errors with `body={"error":"invalid_api_key","key_version":"v7"}`.
- `run_probe`: Probe to `api.paygate.example` succeeded (200 OK) with the note: "key v7 revoked 8 min ago, v8 active".
- `get_config`: `payments-api` config confirmed `PAYGATE_API_KEY_VERSION: v7 (loaded at process start 3d ago)`.

## Proposed Remediation
Restart `payments-api` (`restart_service`) to force it to reload the new secret (`v8`) from Vault upon startup. This is safe and standard practice for non-dynamic secret configuration.
