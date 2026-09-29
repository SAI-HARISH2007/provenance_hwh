# Incident Report

## Summary
An alert was triggered for `api-gateway` due to a spike in 401 errors on `/v1/checkout`. The `payments-api` service is showing a degraded status with an error rate exceeding 83%.

## Timeline
- **02:02:00Z**: `payments-api` host rebooted after kernel patch.
- **02:39:00Z**: `auth-api` deployed version `auth-1.6.0`, switching JWT signing to ES256 with dual-verify enabled.
- **03:12:00Z**: P1 alert fired for `api-gateway` reporting elevated 401 rates on `/v1/checkout`.

## Root Cause
Potential mismatch or validation failure involving token verification or service secrets following the recent JWT signing algorithm update or node reboot on `payments-api`.

## Evidence
- `payments-api` error rate jumped from 0.385% to 83.917%.
- `auth-api` recently transitioned JWT signing from RS256 to ES256.

## Remediation & Follow-ups
- Monitor token verification logs on `payments-api`.
- Verify secret/key propagation across all nodes.