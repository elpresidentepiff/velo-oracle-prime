# V14 Single-Source Truth Closeout — 2026-05-23

**Status:** CLOSED  
**Classification:** `V14_SINGLE_SOURCE_TRUTH_RECONCILIATION_CLOSED`  
**Date:** 2026-05-23  
**Authority:** El Presidente

---

## What Was Closed

The contradiction between `policy_registry_manifest_v1.json`, `CURRENT_RUNTIME_TRUTH.md`, and actual runtime code has been fully resolved. This document is the authoritative record of that closure.

---

## Commit Record

| Commit | Action | Files |
|---|---|---|
| `4520cdc` | SQPE V18 classification packet | `SQPE_V18_CLASSIFICATION_PACKET.md` |
| `da666fe` | CLAUDE.md stale reference remediation | `CLAUDE_MD_STALE_REFERENCE_REMEDIATION.md`, `CLAUDE.md` |
| `1ea9fc0` | Arena V2 market provenance audit | `ARENA_V2_MARKET_PROVENANCE_AUDIT.md` |
| `3814069` | International gate updated | `VELO_INTERNATIONAL_NEXT_GATE_PLAN_V1.md` |
| `7e05d9d` | Council action queue created | `V14_COUNCIL_ACTION_QUEUE.md` |
| `ff34490` | Live scoring truth audit | `LIVE_SCORING_TRUTH_AUDIT_2026_05_23.md`, `CURRENT_RUNTIME_TRUTH.md` |
| `ce51f0c` | Registry reconciliation | `policy_registry_manifest_v1.json`, `V14_COUNCIL_ACTION_QUEUE.md` |
| `74a0e90` | Council resolution packet | `V14_COUNCIL_RESOLUTION_PACKET_2026_05_23.md` |

---

## Established Live Scoring Truth

**Profile:** `SQPE_IMPROVEMENT_MDS_V1` (active since 2026-05-08, commit `b7e4e0c`)

### Live Core (VP-weighted)

| Signal | Weight | Status |
|---|---|---|
| `sqpe_v17_prob` | 0.45 | LIVE_WEIGHTED |
| `improvement_score` | 0.12 | LIVE_WEIGHTED |
| `market_deception_score` | 0.10 | LIVE_WEIGHTED |

**Effective VP formula:**
```
VP = (0.45 × sqpe_v17 + 0.12 × improvement_score + 0.10 × MDS) / 0.67
```

### Display / Advisory (calculated, stored, not VP-weighted)

| Signal | Status | Notes |
|---|---|---|
| `place_prob` | BADGE_ONLY | Excluded from VP in SQPE_IMPROVEMENT_MDS_V1; displayed as badge |
| `release_window_score` | STORED_ONLY | Weight 0.00; calculated, stored, not weighted |
| `comment_intel_score` | STORED_ONLY | Weight 0.00; calculated, stored, not weighted |
| `longshot_score` | FROZEN | FREEZE_CANDIDATE (ROI=-0.065); excluded from VP; SP≥10 gate still used for tier X |

### Shadow Only

| Signal | Status | Notes |
|---|---|---|
| Playbook G | SHADOW_ONLY | Multiplier computed, NOT applied to VP (VELO_G_SHADOW_MODE=shadow default) |
| NO_VP_COMPOSITE challenger | SHADOW_GATE | Forward evidence gate; n=284/300 runners |

### Unclassified Lab

| Model | Status |
|---|---|
| SQPE V18 | NOT_WIRED / LAB_EXPERIMENT_COMPLETED_NO_LIFT / ARCHIVE_ELIGIBLE |

---

## Documents Corrected

| Document | Error | Correction |
|---|---|---|
| `CURRENT_RUNTIME_TRUTH.md` Section 3 | Described pre-surgery LEGACY_FULL_ENSEMBLE state — improvement_score listed as disabled, place_prob as live-weighted | Section 3 updated to SQPE_IMPROVEMENT_MDS_V1 truth |
| `policy_registry_manifest_v1.json` SCORING_POLICY_LIVE | place_prob listed as 0.08 live; comment_intel_score listed as 0.08 live; release_day_prob wrong field name (0.10); longshot_score listed as gated live | Corrected to live_weighted / badge_only / frozen_not_weighted / stored_only sections |

**Root cause of both errors:** The 2026-05-08 Ensemble Surgery (commit `b7e4e0c`) changed the active profile from LEGACY_FULL_ENSEMBLE to SQPE_IMPROVEMENT_MDS_V1 but neither document was updated to reflect the new profile's disabled set.

---

## Dirty Worktree Files — Intentionally Untouched

The following modified/untracked files were present during this session and were deliberately excluded from all commits:

**Modified (tracked):**
`data/eod_loss_ledger_shadow_daily.jsonl`, `data/industry_selections_20260519.json`, `data/mission_control/2026-05-22_mission_control.json`, `data/mission_control/latest.json`, `data/playbook_g_outcome_events_shadow_daily.jsonl`, `data/reports/*.json/*.md`, `data/sentient_state_shadow_daily.json`, `data/sentient_state_shadow_full_train_v2.json`, `data/shadow_learning_loop_audit_v1.json`, `data/sigma_results/sigma_results_2026_05_22.json`, `data/telegram_delivery_truth_2026_05_17.json`, `scripts/ops/build_industry_comparison.py`, `scripts/ops/ingest_racecard_pdfs.py`, `scripts/ops/ingest_results_to_horse_runs.py`, `scripts/ops/velo_morning_cockpit.py`

**Untracked (not staged):**
Runtime artifacts, sigma results, runner snapshots, council packets, ops worker dry runs, competitor reports — all ops/data artifacts, none governance-relevant.

---

## Remaining Open Governance Items

| Item | Status | Requires |
|---|---|---|
| SQPE V18 archive decision | COUNCIL_REQUIRED | Operator sign-off to move pkl to archive |
| Arena V3 morning odds arena | BLOCKED | Operator sign-off + source legality + Arena V3 build |
| Feature registry Council review | REVIEW_PENDING | Council formal sign-off |
| International gate | GATE_ACTIVE | El Presidente explicit sign-off |
| First implementation slice | AWAITING_APPROVAL | Council approval |

---

## Final Classification

```
V14_SINGLE_SOURCE_TRUTH_RECONCILIATION_CLOSED
LIVE_SCORING_TRUTH_ESTABLISHED
POLICY_REGISTRY_RECONCILED_TO_RUNTIME
IMPROVEMENT_SCORE_LIVE_WEIGHTED_CONFIRMED (0.12)
MDS_LIVE_WEIGHTED_CONFIRMED (0.10)
DISPLAY_ONLY_SIGNALS_SEPARATED (place_prob / release_window_score / comment_intel_score / longshot_score)
SHADOW_ONLY_SIGNALS_SEPARATED (Playbook G / CPU challenger)
SQPE_V18_REMAINS_NOT_WIRED
ARENA_V2_CLASSIFIED_AS_CLOSING_MARKET_CONFIRMATION
INTERNATIONAL_STILL_GATED
NO_SCORING_CHANGE
NO_MODEL_PROMOTION
NO_ROUTER_STAKING_CHANGES
NO_TELEGRAM_RUNTIME_CHANGES
NO_PLAYBOOK_G_CHANGES
NO_LIVE_STATE_MUTATION
NO_MIGRATION
NO_WORKER_ACTIVATION
```
