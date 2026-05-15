# VELO Safety Sentinel V1

## Purpose
Safety Sentinel is the veto layer for VELO Agent OS. It checks whether a command is safe before the system mutates anything important.

## Outputs
- `SAFE`
- `WARN`
- `BLOCK`

Artifacts:
- `data/safety_sentinel/latest.json`
- `data/safety_sentinel/YYYY-MM-DD_preflight.json`

## Current Hard Blocks
- target is `shadow_full_train_v1`
- learning requested with missing target
- `data/sentient_state.json` appears modified
- `consumed_live > 0`
- Sigma truth unavailable for learning
- official predictions already exist and scoring would overwrite them
- scoring/model/router/staking/Telegram files changed without approval
- `.env` or secret-like files changed
- `verify=False` appears in changed code
- new executable scripts are staged without explicit approval

## Current Warns
- repo dirty
- governance docs drifting
- RP coverage below threshold
- CASHRUN missing
- convergence report missing
- Sigma waiting / partial

## Cloud Backup Rule
The canonical live backup row is:
- `pattern_name = SENTIENT_STATE_BACKUP`

Sentinel must not rely solely on:
- `pattern_type = SENTIENT_STATE_BACKUP`

## Learning Rule
No results means no truth.
No truth means no learning.
No learning means hard stop.

## Current Approved Learning Target
- `shadow_full_train_v2`
