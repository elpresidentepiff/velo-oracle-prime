# VELO Telegram Signal Attribution Panel Live Patch V1

## Scope

- display-only patch in `scripts/run_prime_today.py`
- no model scoring changes
- no router logic changes
- no staking changes
- no execution gate changes

## Patch Summary

- added `render_signal_attribution_panel()`
- wired the full panel into governed A/B cards
- wired a compact panel into the C-WATCH grouped list
- used repo-proven badge conditions only

## Badge Conditions

- `VP30_TIER_A`: velo_prime_prob >= 0.30 and decision_tier == A
- `MDS_HIGH`: market_deception_score > 0.50
- `IMPROVE_HIGH`: improvement_score > 0.40
- `PLACE_PROB_HIGH`: place_prob > 0.80
- `B_LOW_VP_SUPPRESS`: decision_tier == B and velo_prime_prob < 0.30
- `VP_020_030_DRAG`: 0.20 <= velo_prime_prob < 0.30
- `MID_PRICE_ZONE_WATCH`: pre-race odds in 3.0-8.5 zone

## Safety Proof

- pick selection unchanged
- model scoring unchanged
- router unchanged
- staking unchanged
- candidate route unchanged
- syntax check passed

## Tomorrow Readiness

If this patched `scripts/run_prime_today.py` is the version used tomorrow, Telegram will show the signal panel.
This remains a display-only intelligence upgrade, not a prediction or execution change.

## Preview File

- `data/telegram_signal_attribution_live_preview_v1.md`