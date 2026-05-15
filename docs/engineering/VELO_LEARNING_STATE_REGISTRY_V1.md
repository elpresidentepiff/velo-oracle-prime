# VELO Learning State Registry V1

## Purpose
This file is the authoritative operator map for learning targets. It exists to stop accidental writes into the live brain, prevent re-use of contaminated shadow states, and make daily EOD decisions explicit.

## State Classes

### LIVE
- Path: `data/sentient_state.json`
- Role: protected live state
- Policy: read-only for agent workers
- Mutation: forbidden
- Promotion source: none by default

### CONTAMINATED
- Target: `shadow_full_train_v1`
- Role: preserved evidence of duplicate learning contamination
- Policy: never target for build, consume, or replay
- Mutation: forbidden

### APPROVED SHADOW
- Target: `shadow_full_train_v2`
- Role: current clean shadow learning state
- Seed provenance: `shadow_repair_v1`
- Approved use: post-results EOD learning only when Sigma truth is ready
- Current clean race count baseline: `1975`

## Blocked Paths and Modes
- `consumed_live=true`
- any write to `data/sentient_state.json`
- any learning command targeting `shadow_full_train_v1`
- any Playbook G live promotion
- any cloud backup mutation during shadow learning

## Current EOD Target
- Approved daily EOD target: `shadow_full_train_v2`
- Forbidden daily EOD target: `shadow_full_train_v1`

## Consumed Live Policy
- `consumed_live` must remain `0`
- live learning is blocked unless an explicit promotion audit is approved
- any observed `consumed_live > 0` is an immediate `BLOCK`

## Cloud Backup Policy
- Cloud backup row is `pattern_name = SENTIENT_STATE_BACKUP`
- Shadow consume must not mutate the live cloud backup row
- Any unexpected `updated_at` change during shadow consume is a stop condition

## Promotion Gates
Learning or promotion is allowed only if all are true:
- Sigma has usable result truth
- target is `shadow_full_train_v2`
- `consumed_live = 0`
- live state hash unchanged
- cloud backup unchanged
- no official prediction overwrite risk
- no forbidden file modifications

## EOD Stop Conditions
Daily EOD must stop when:
- Sigma returns `0` result races
- Sigma returns `0` matched races / audit rows
- target is missing
- target is contaminated
- live state hash changes unexpectedly
- cloud backup changes unexpectedly
- `consumed_live` would become non-zero

## Operational Summary
- Live brain: protected
- Contaminated shadow: evidence only
- Clean shadow: `shadow_full_train_v2`
- No truth: no learning
- No learning: hard stop
