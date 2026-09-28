# Incident Report: payments-api Secret Rotation Outage

## Summary
At 2026-08-30T03:12:00Z, the `payments-api` service experienced a 100% failure rate on charges (`charge_failed rate 100% for 4m`), causing the service status to go down. Investigation revealed that a scheduled Vault secret rotation (PAYGATE_API_KEY v7 -> v8) revoked the old API key v7 at the vendor, while `payments-api` was still holding key v7 in memory (loaded at process start 3 days ago).

## Timeline
- **2026-08-30T03:01:00Z**: `payments-api` deployed version `payments-2.16.0` (retry jitter).
- **2026-08-30T03:04:00Z**: Vault scheduled 90-day rotation: PAYGATE_API_KEY rotated from v7 to v8. Old key v7 revoked at vendor. Note in config/probe indicates consumers must reload the secret.
- **2026-08-30T03:12:00Z**: Alert fires: `payments-api` charge_failed rate 100% for 4m.

## Root Cause
Secret rotation (`secret_rotation`): Vault rotated `PAYGATE_API_KEY` from v7 to v8 and revoked v7 at the vendor. Because `payments-api` reads the secret at process start and has not been restarted since the rotation, it continues sending requests with the defunct v7 key, resulting in authentication/authorization failures on all charges.

## Evidence
- `recent_changes`: `vault: scheduled 90-day rotation: PAYGATE_API_KEY v7 -> v8 (old key revoked at vendor) (by ops-bot)` at 03:04:00Z, noting: `consumers must reload the secret; payments-api reads it at process start`.
- `get_config`: `payments-api` config shows `"PAYGATE_API_KEY_VERSION": "v7 (loaded at process start 3d ago)"`.
- `run_probe`: Probe to `https://api.paygate.example/status` confirms vendor is healthy but notes: `key v7 revoked 8 min ago, v8 active`.

## Proposed Remediation
Restart the `payments-api` service (`restart_service`) to reload the latest environment variables / secrets from Vault (v8). This is safe because `payments-api` is a stateless API tier running multiple replicas.
