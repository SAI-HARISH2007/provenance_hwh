# Incident Report: API Gateway 401 Rate Spike

## Summary
At 2026-08-30T03:12:00.000Z, an alert fired for an elevated 401 error rate (~9.5%) on `/v1/checkout` requests through the `api-gateway`. Investigation points to a recent change in `auth-api` switching the JWT signing algorithm to ES256.

## Timeline
- **02:02:00Z**: `payments-api` host rebooted after kernel patch.
- **02:39:00Z**: `auth-api` deployed version `auth-1.6.0` switching JWT signing to ES256.
- **03:12:00Z**: P1 alert fired for high 401 rates on `/v1/checkout`.

## Root Cause
Switching JWT token signing to ES256 in `auth-api` (`auth-1.6.0`) introduced token validation discrepancies/failures across downstream consumers or dependencies during checkout flows, resulting in 401 Unauthorized responses.

## Evidence
- `auth-api` deploy change at 02:39:00Z: switch JWT signing to ES256.
- `api-gateway` logs showing frequent 401 errors on POST `/v1/checkout` targeting upstream services.

## Remediation
- **Action**: Rollback `auth-api` deploy or temporarily disable ES256 JWT signing until verification logic is fully validated across all services.
- **Target**: `auth-api`

## Follow-ups
1. Verify JWT verification compatibility across all consuming services before reenabling ES256.
2. Add automated integration tests for token validation during algorithm rotations.