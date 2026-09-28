## Incident Report: orders-api ValidationError Spike

### Summary
On 2026-08-30 at 03:12:00Z, an alert fired for `orders-api` indicating a 27% error rate on `order_create` operations, specifically `ValidationError`s. Investigation revealed these errors are caused by the `new_pricing_engine` feature, which was fully enabled via a feature flag shortly before the incident.

### Timeline
* **2026-08-30T00:42:00Z**: `orders-api` deployed version `orders-3.8.1` (refactor order serializer).
* **2026-08-30T02:53:00Z**: Feature flag `new_pricing_engine` on `orders-api` was changed from 20% to 100% rollout.
* **2026-08-30T02:58:55Z**: First `ValidationError: negative total for cart with coupon_type=percentage_stacked` logs observed in `orders-api`, explicitly tagged with `pricing_engine=new`.
* **2026-08-30T03:12:00Z**: P2 alert fired for `orders-api` due to 27% error rate on `order_create`.

### Root Cause
The root cause is a bug within the `new_pricing_engine` feature of the `orders-api`. This bug manifests as a `ValidationError` when processing carts with `coupon_type=percentage_stacked`, resulting in a 'negative total'. The issue was triggered when the `new_pricing_engine` feature flag was rolled out from 20% to 100%, fully activating the problematic code path.

### Evidence
* The alert message explicitly states `order_create 27% errors (ValidationError)` on `orders-api`.
* `orders-api` metrics show a significant spike in `error_rate_pct` from 0.41% to 25.97% (max 28.101%) within the last 30 minutes.
* The `RECENT CHANGES` log shows `2026-08-30T02:53:00.000Z [flag] orders-api: new_pricing_engine 20% -> 100% (sam)`, which directly precedes the error spike.
* `orders-api` logs show repeated `ERROR orders-api: pricing_engine=new ValidationError: negative total for cart with coupon_type=percentage_stacked` messages starting at `02:58:55Z`, confirming the specific error and its association with the new pricing engine.
* Other services and infrastructure (Postgres, Redis, other APIs) show healthy metrics, indicating the issue is isolated to `orders-api` and its new feature.

### Remediation
Disable the `new_pricing_engine` feature flag on `orders-api` by reverting its rollout percentage to 0% or 20% (its previous state) to immediately mitigate the errors.

### Follow-ups
1. **Investigate `new_pricing_engine` bug**: The engineering team responsible for the `new_pricing_engine` feature should investigate and fix the `ValidationError` related to 'negative total for cart with coupon_type=percentage_stacked'.
2. **Improve feature flag rollout process**: Review the testing and rollout process for critical feature flags to prevent similar issues from impacting 100% of traffic.
3. **Monitoring for feature flags**: Enhance monitoring to detect specific error types or increased error rates immediately after feature flag changes.