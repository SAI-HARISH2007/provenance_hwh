### Incident Report: API Gateway 401 Errors on /v1/checkout

#### Summary
At 03:12 UTC, an alert fired for a high 401 error rate (~9.5%) on `/v1/checkout` via the `api-gateway`. Investigation shows that the recent `auth-api` deployment switching token signing to ES256 resulted in `payments-api` rejecting tokens with `InvalidIssuedAt` errors due to token/clock validation issues.

#### Timeline
- **02:02 UTC**: Infrastructure reboot on `payments-api` node.
- **02:39 UTC**: `auth-api` deployed (v1.6.0) switching JWT signing to ES256 (dual-verify enabled).
- **02:54 UTC**: First `InvalidIssuedAt` log entries appear in `payments-api`.
- **03:05 UTC**: `payments-api` error rate jumps to ~90%, driving `api-gateway` 401 error rate to ~9.5%.
- **03:12 UTC**: P1 alert fired.

#### Root Cause
The switch to ES256 in `auth-api` introduced token validation errors (`InvalidIssuedAt`) on `payments-api`, causing requests to fail authentication checks during checkout.

#### Evidence
- Config change: `auth-api` switched JWT signing to ES256.
- Logs: `payments-api` spamming `WARN payments-api: jwt verification failed: InvalidIssuedAt sub=... alg=ES256`.
- Metrics: `payments-api.error_rate_pct` spiked to ~90% starting at 03:04 UTC.

#### Remediation
Update `auth-api` or downstream verification configuration (`JWT_CLOCK_SKEW_S`) to accommodate token issuance time differences or temporarily rollback the signing algorithm config.

#### Follow-ups
1. Audit clock synchronization across nodes, specifically the node rebooted at 02:02 UTC (`payments-3`).
2. Improve pre-deployment testing for JWT signing algorithm migrations.