# Incident Report: payments-api Secret Rotation Failure

## Summary
At 2026-08-30T03:12:00Z, `payments-api` experienced a 100% failure rate for charge requests. Investigation revealed that vault performed a scheduled 90-day secret rotation for `PAYGATE_API_KEY` from version `v7` to `v8` at 03:04 UTC, revoking the old `v7` key at the vendor. Because `payments-api` caches secrets at process start and has not been restarted since the rotation, it continued sending requests with the revoked `v7` API key, resulting in 401 unauthorized errors from Paygate.

## Timeline
- **2026-08-30T03:01:00Z**: `payments-api` deployed version `payments-2.16.0` (add retry jitter).
- **2026-08-30T03:04:00Z**: Vault scheduled 90-day rotation: `PAYGATE_API_KEY` v7 -> v8 (old key revoked at vendor).
- **2026-08-30T03:12:00Z**: `payments-api` alert fires: `charge_failed rate 100% for 4m`.

## Root Cause
`secret_rotation`: Vault rotated the API key at the vendor and revoked the old key (`v7`), but `payments-api` holds the old key in memory loaded at process start and requires a restart to pick up the new secret (`v8`).

## Evidence
- `recent_changes`: Vault rotation log showing `PAYGATE_API_KEY v7 -> v8 (old key revoked at vendor)`.
- `get_config`: `payments-api` configuration showing `PAYGATE_API_KEY_VERSION: v7 (loaded at process start 3d ago)`.
- `query_logs`: `payments-api` error logs showing continuous `status=401 body={"error":"invalid_api_key","key_version":"v7"}`.
- `run_probe`: Probe to `https://api.paygate.example` confirming vendor is healthy and that key v7 was revoked, with v8 active.

## Proposed Remediation
Restart `payments-api` (`restart_service`) to force the application to load the newly rotated API key (`v8`) from Vault. This is safe and standard for secret rotation where processes load environment variables or secrets at startup.
