# Incident Report: Orders API ValidationError Spike

## Summary
At 2026-08-30T03:12:00.000Z, `orders-api` fired an alert for a 27% error rate on order creation (`ValidationError`). Investigation revealed that the newly rolled out `new_pricing_engine` feature flag caused cart calculations to result in negative totals when processing carts with `percentage_stacked` coupons.

## Timeline
- **2026-08-30T02:53:00.000Z**: `new_pricing_engine` feature flag expanded from 20% to 100% rollout.
- **2026-08-30T02:54:32.000Z**: First `ValidationError` (`negative total for cart with coupon_type=percentage_stacked`) logged by `orders-api`.
- **2026-08-30T03:12:00.000Z**: Alert fires for `orders-api` order creation errors (27% error rate).

## Root Cause
Feature flag misconfiguration / bug in new feature (`feature_flag_misconfig`): The `new_pricing_engine` feature flag handles percentage stacked coupons incorrectly, producing negative cart totals which fail validation.

## Evidence
- Alert: `orders-api` status degraded, `order_create 27% errors (ValidationError)`.
- Recent changes: `new_pricing_engine 20% -> 100%` at 02:53:00.000Z.
- Logs: Continuous `ValidationError: negative total for cart with coupon_type=percentage_stacked` explicitly referencing `pricing_engine=new` starting immediately after the flag expansion.

## Proposed Remediation
Disable the `new_pricing_engine` feature flag (`disable_feature_flag`) to immediately stop processing orders with the buggy pricing engine and restore 100% successful order creation for stacked percentage coupon carts. This action is safe and instantaneous.
