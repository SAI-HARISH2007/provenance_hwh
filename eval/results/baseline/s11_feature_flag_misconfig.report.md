# Incident Report: orders-api ValidationError spike

## Summary
At 2026-08-30T03:12:00.000Z, an alert fired for `orders-api` indicating a 27% error rate spike (ValidationError) on `order_create`. The root cause was traced to rolling out the `new_pricing_engine` feature flag to 100%, which introduced a calculation bug resulting in negative totals for carts using stacked percentage coupons.

## Timeline
- **2026-08-30T02:53:00.000Z**: `new_pricing_engine` feature flag rolled out from 20% to 100% by sam.
- **2026-08-30T02:58:55.000Z**: First `ValidationError` due to negative total logged in `orders-api`.
- **2026-08-30T03:12:00.000Z**: Alert fires for `order_create` 27% error rate.

## Root Cause
Feature flag misconfiguration/bug: The `new_pricing_engine` calculation logic produces negative totals for carts with `coupon_type=percentage_stacked`.

## Evidence
- Feature flag change audit: `2026-08-30T02:53:00.000Z [flag] orders-api: new_pricing_engine 20% -> 100% (sam)`
- Error logs showing validation failure: `ERROR orders-api: pricing_engine=new ValidationError: negative total for cart with coupon_type=percentage_stacked order_id=ord_22020 rid=18c99e5d`

## Remediation
- Disable the `new_pricing_engine` feature flag on `orders-api`.

## Follow-ups
- Fix the pricing calculation logic for stacked percentage coupons in the new pricing engine before re-enabling.
- Add unit tests covering percentage stacked coupons with the new pricing engine.