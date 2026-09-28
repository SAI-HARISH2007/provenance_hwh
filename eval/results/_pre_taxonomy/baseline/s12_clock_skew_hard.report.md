# Incident Report: API Gateway 401 Errors

## Summary
An alert fired indicating an elevated 401 error rate on `/v1/checkout` requests flowing through the `api-gateway`.

## Timeline
- **02:39Z**: `auth-api` deployed version `auth-1.6.0`, switching JWT signing to ES256 with dual-verify enabled.
- **03:12Z**: P1 alert fires for `api-gateway` showing a 9.5% 401 error rate on `/v1/checkout`.

## Root Cause
Token verification mismatch or clients sending un-updated token types during the cryptographic signing algorithm migration in `auth-api`.

## Evidence
- Alert message: `401 rate 9.5% on /v1/checkout; auth-api healthy`
- Recent deployment change: `switch JWT signing to ES256 (dual-verify enabled)`

## Remediation
No immediate action (`no_action`) is required as dual-verify is enabled for a 7-day transition period and `auth-api` remains healthy.

## Follow-ups
- Monitor client token upgrade progress over the 7-day dual-verify window.