# Incident Report: Orders-API Validation Errors Following Feature Flag Rollout

## Summary
At 2026-08-30T03:12:00.000Z, `orders-api` began experiencing a 27% error rate (`ValidationError`) on `order_create` requests. Investigation revealed that these errors are caused by the `new_pricing_engine` feature flag being rolled out from 20% to 100% at 02:53 UTC, which produces a `ValidationError` ("negative total for cart with coupon_type=percentage_stacked") for specific cart combinations.

## Timeline
- **02:53:00 UTC**: Feature flag `new_pricing_engine` rolled out to 100% by sam.
- **03:00:14 UTC**: First error logs appear showing `ValidationError: negative total for cart with coupon_type=percentage_stacked`.
- **03:12:00 UTC**: P2 alert fires for `orders-api` (`order_create 27% errors (ValidationError)`).

## Root Cause
`feature_flag_misconfig`: The `new_pricing_engine` feature flag contains a bug when calculating totals for carts with `coupon_type=percentage_stacked`, resulting in negative totals and subsequent validation failures when enabled at 100%.

## Evidence
1. **Recent Changes**: Flag change `new_pricing_engine 20% -> 100%` at 02:53 UTC precisely preceded the errors.
2. **Logs**: `query_logs` for `orders-api` shows explicit `ValidationError: negative total for cart with coupon_type=percentage_stacked` messages linked to `pricing_engine=new`.
3. **Alert**: `get_alert` shows `orders-api` status degraded with 27% validation errors.

## Proposed Remediation
Disable the faulty feature flag (`new_pricing_engine`) to immediately stop validation errors for stacked percentage coupons while the pricing logic bug is fixed.
- **Action**: `disable_feature_flag`
- **Target**: `orders-api` (flag: `new_pricing_engine`)

## Follow-ups
1. Fix the calculation logic in the `new_pricing_engine` for stacked percentage coupons so totals do not become negative.
2. Add comprehensive unit tests covering stacked coupons under the new pricing engine before re-enabling.