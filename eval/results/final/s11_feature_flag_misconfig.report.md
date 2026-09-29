# Incident Report: orders-api Validation Errors due to Feature Flag

## Summary
At 2026-08-30T03:12:00.000Z, `orders-api` began throwing `ValidationError` (`negative total for cart with coupon_type=percentage_stacked`) on approximately 27% of order creation requests. The root cause is a feature flag (`new_pricing_engine`) that was scaled up from 20% to 100% at 02:53 UTC, exposing a bug in the new pricing engine where stacked percentage coupons calculate a negative total.

## Timeline
- **2026-08-30T02:53:00.000Z**: Feature flag `new_pricing_engine` for `orders-api` scaled from 20% to 100%.
- **2026-08-30T02:57:26.000Z**: First `ValidationError` (`negative total for cart with coupon_type=percentage_stacked`) logged in `orders-api`.
- **2026-08-30T03:12:00.000Z**: P2 alert fires for `orders-api` (`order_create 27% errors (ValidationError)`).

## Root Cause
Feature flag misconfiguration / buggy feature flag implementation (`feature_flag_misconfig`). The `new_pricing_engine` contains a calculation bug for carts using `coupon_type=percentage_stacked`, resulting in negative cart totals which fail validation. When it was at 20%, errors were infrequent; at 100%, it affected ~27% of requests.

## Evidence
1. **Recent Changes**: `orders-api: new_pricing_engine 20% -> 100%` at 02:53:00.000Z.
2. **Logs**: Repeated `ERROR orders-api: pricing_engine=new ValidationError: negative total for cart with coupon_type=percentage_stacked`.
3. **Metrics**: `error_rate_pct` on `orders-api` jumped from 0.4% to ~27% immediately following the flag change.

## Proposed Remediation
Disable the faulty feature flag (`new_pricing_engine`) via `disable_feature_flag`. This is extremely safe and instant, returning orders-api to the previous stable pricing engine version while developers fix the percentage-stacking calculation bug.

## Follow-ups
1. Fix the `new_pricing_engine` calculation logic for `coupon_type=percentage_stacked`.
2. Add unit/integration tests covering percentage stacked coupons with the new pricing engine.
