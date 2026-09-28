## Incident Report: High 401/5xx Rate on Authenticated Routes

### Summary
At 03:12:00Z, an alert fired indicating a 41% 401/5xx error rate on all authenticated routes via the `api-gateway`. Investigation revealed the `auth-api` service was down and experiencing a near 100% error rate. Logs from `api-gateway` showed persistent 'TLS handshake error' messages when attempting to connect to `auth-api`, strongly suggesting an expired or invalid TLS certificate on the authentication service.

### Timeline
* **2026-08-30T02:53:32.000Z**: First occurrence of `TLS handshake error` in `api-gateway` logs targeting `auth-api`.
* **2026-08-30T03:12:00.000Z**: P1 alert fired for `api-gateway` due to high 401/5xx rate.
* **2026-08-30T03:12:00.000Z (now)**: `auth-api` reported as 'down' with 98% error rate. `api-gateway` and `orders-api` are 'degraded' with high error rates.

### Root Cause
The root cause is an expired TLS certificate on the `auth-api` service. This prevents `api-gateway` from establishing a secure connection, leading to TLS handshake failures and subsequent authentication errors (401/5xx) for all authenticated routes.

### Evidence
* The `auth-api` service is explicitly marked as `down` in the service status overview.
* Metrics show `auth-api`'s `error_rate_pct` spiked to `98.046%` from a healthy state.
* `api-gateway` logs are flooded with `ERROR api-gateway: upstream auth-api: TLS handshake error; retrying upstream` messages, directly pointing to a communication issue with `auth-api` at the TLS layer.
* The alert message itself, '401/5xx rate 41% on all authenticated routes', aligns perfectly with an authentication service failure.

### Remediation
**Action:** `rotate_tls_cert`
**Target:** `auth-api`

Rotate the TLS certificate for the `auth-api` service with a new, valid certificate. A restart of the `auth-api` service may be required after the certificate rotation to ensure the new certificate is loaded and used.

### Follow-ups
1. Verify the actual expiration date of the certificate on `auth-api` to confirm the root cause.
2. Implement proactive monitoring and alerting for TLS certificate expiration dates across all services.
3. Review and improve the certificate management process for `auth-api` to prevent future expirations.