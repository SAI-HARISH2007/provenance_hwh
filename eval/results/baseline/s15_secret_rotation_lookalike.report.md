# Incident Report: payments-api 100% Charge Failure

## Summary
At 2026-08-30T03:12:00.000Z, the `payments-api` service experienced a 100% failure rate on payment charges (`charge_failed rate 100% for 4m`). The root cause is a recent secret rotation in Vault which bumped `PAYGATE_API_KEY` from version `v7` to `v8` and revoked the old key at the vendor. Because `payments-api` reads and caches this secret strictly at process start, it continued using the revoked `v7` key, resulting in 401 Unauthorized errors from the vendor.

## Timeline
- **2026-08-30T03:01:00.000Z**: `payments-api` deploy `payments-2.16.0` adds retry jitter.
- **2026-08-30T03:04:00.000Z**: Vault scheduled 90-day secret rotation updates `PAYGATE_API_KEY` from `v7` to `v8` and revokes `v7` at the vendor.
- **2026-08-30T03:12:00.000Z**: Alert fires indicating 100% charge failures on `payments-api`.

## Root Cause
The Vault secret rotation updated `PAYGATE_API_KEY` to version `v8` and revoked `v7`. `payments-api` loads its API key environment variable / secret strictly upon process initialization and does not automatically reload it, causing all downstream vendor calls to fail with 401 invalid API key.

## Evidence
- Vault audit log: `scheduled 90-day rotation: PAYGATE_API_KEY v7 -> v8 (old key revoked at vendor)`
- Config note: `payments-api reads it at process start`, currently on `v7 (loaded at process start 3d ago)`
- Logs: `ERROR payments-api: paygate request failed: status=401 body={"error":"invalid_api_key","key_version":"v7"}`

## Remediation
1. Restart the `payments-api` service to force a reload of the environment/secrets from Vault (now reading `v8`).

## Follow-ups
- Implement dynamic secret reloading or runtime credential refresh in `payments-api` so manual service restarts are not required upon Vault secret rotations.
- Improve monitoring for credential mismatch / authentication errors prior to 100% outage thresholds.