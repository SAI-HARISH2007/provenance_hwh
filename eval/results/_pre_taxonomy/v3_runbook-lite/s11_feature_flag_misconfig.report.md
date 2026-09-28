# Incident Report: orders-api ValidationError Spike

## Summary
At 2026-08-30T03:12:00.000Z, a page fired for `orders-api` experiencing 27% errors (`ValidationError`) on `order_create`. Investigation traced the root cause to the `new_pricing_engine` feature flag, which was rolled out to 100% at 02:53 UTC. The new pricing engine incorrectly calculates totals for carts with stacked percentage coupons, producing negative cart totals that fail validation.

## Timeline
- **2026-08-30T02:53:00.000Z**: `new_pricing_engine` feature flag scaled from 20% to 100% by Sam via UI.
- **2026-08-30T02:54:32.000Z**: First `ValidationError` (`negative total for cart with coupon_type=percentage_stacked`) logged in `orders-api`.
- **2026-08-30T03:12:00.000Z**: P2 Alert fires due to 27% error rate on `order_create`.

## Root Cause
Feature flag misconfiguration / buggy feature (`feature_flag_misconfig`): The `new_pricing_engine` feature flag introduced a bug when calculating orders with `coupon_type=percentage_stacked`, resulting in negative cart totals and subsequent `ValidationError`.

## Evidence
- `get_alert`: `orders-api` degraded with 27% `ValidationError` on `order_create`.
- `recent_changes`: `new_pricing_engine` flag updated from 20% to 100% at 02:53 UTC.
- `query_logs`: Continuous `ValidationError: negative total for cart with coupon_type=percentage_stacked` errors associated with `pricing_engine=new` beginning immediately after the flag rollout.
- `run_probe`: Verified service process is healthy (`/healthz` 200 OK), confirming the service is running normally and failures are strictly isolated to the new pricing engine feature logic.

## Proposed Remediation
Disable the `new_pricing_engine` feature flag (`disable_feature_flag`) on `orders-api` to immediately halt the validation errors, returning to the stable pricing engine while the bug in `new_pricing_engine` is patched. This action is safe, instant, and directly targets the mechanism.

## Follow-ups
1. Fix the calculation bug in `new_pricing_engine` for `percentage_stacked` coupons.
2. Add automated unit tests covering stacked percentage coupons under the new pricing engine.
