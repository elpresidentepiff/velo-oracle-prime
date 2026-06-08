# RP Archive Outcome Bridge V1

## Purpose

The RP archive can only prove value when archive horses are connected to VÉLØ predictions and confirmed outcomes. Outcome Bridge V1 joins:

`RP archive -> identity bridge -> VÉLØ runner snapshot/verdict -> Sigma/result truth`

## Inputs

- `data/racing_post_account_parsed/horse_identity_bridge.json`
- RP horse dossiers
- RP race dossiers
- VÉLØ runner snapshots
- official VÉLØ verdict artifacts
- Sigma result artifacts
- RPDC memory where present

## Classifications

- `OUTCOME_CONFIRMED`: prediction identity and outcome truth are both present.
- `PREDICTION_ONLY_NO_RESULT`: VÉLØ/runner snapshot exists, but result truth is missing.
- `RESULT_ONLY_NO_PREDICTION`: result truth exists without linked VÉLØ prediction.
- `RP_ONLY_NO_VELO`: RP archive exists but no local VÉLØ/prediction identity exists.
- `IDENTITY_AMBIGUOUS`: identity bridge says the row is ambiguous.
- `OUTCOME_MISSING`: identity exists but outcome cannot be verified.

## Confidence Rules

Archive context value tests may only use rows with:

- `classification = OUTCOME_CONFIRMED`
- `identity_confidence >= 0.86`
- `outcome_confidence > 0`

Anything else is reported, not learned from.

## No Scoring Impact

This bridge is read-only. It does not change VÉLØ scoring, formulas, model inputs, router, staking, Telegram, Playbook G, live state, or learning state.

RPR remains `RPR_ARCHIVE_ONLY_EXCLUDED_FROM_VELO`.

## No Signal Promotion Rule

No RP archive signal can be promoted until outcome-linked evidence exists with sufficient sample size and a separate leakage audit.

Current expected state may be zero outcomes. That is valid and must be reported honestly.
