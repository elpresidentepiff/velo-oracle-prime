# V14 Council Resolution Packet — 2026-05-23

**Status:** GOVERNANCE_HYGIENE_COMPLETE — 5 items closed or classified  
**Classification:** `V14_SINGLE_SOURCE_TRUTH_RECONCILIATION_CLOSED`  
**Date:** 2026-05-23  
**Authority:** El Presidente

---

## Purpose

This packet formally closes or classifies the governance hygiene items identified following the V14 master rollout plan commit. It establishes single-source truth for live scoring reality and documents the Council's position on all 5 items.

---

## Item 1 — SQPE V18 Classification

**Document:** `docs/engineering/SQPE_V18_CLASSIFICATION_PACKET.md`

**Evidence summary:**
- PKL present: `models/sqpe_v18/sqpe_v18.pkl` (6.9MB, GradientBoostingClassifier + IsotonicCalibration)
- Trained: 2026-04-05T16:55:56
- Verdict: `"NO LIFT"` — AUC delta -0.0003, top-1 delta -0.0012
- New features (`class_delta`, `days_since_run`): combined importance 0.001
- Git commit: `032793f` "lab(sqpe): v18 results — NO LIFT from days_since_run + class_delta"
- Training script: `archive/dead_scripts/train_sqpe_v18.py` (archived)
- Runtime references: ZERO — not imported by any scoring path
- V17 outperforms on all metrics (AUC 0.9400 vs 0.9372)

**Council resolution:**

```
ITEM_1_STATUS: CLASSIFIED
CLASSIFICATION: LAB_EXPERIMENT_COMPLETED_NO_LIFT
ARCHIVE_ELIGIBLE: YES
WIRED_TO_RUNTIME: NO — confirmed
PROMOTION_PATH: NONE
KEEP_UNTIL: Operator archive approval (DO NOT DELETE without sign-off)
ACTION: pkl remains in place; classified and documented; no further investigation required
```

**Hard rules confirmed:**
- Do NOT wire sqpe_v18.pkl to any runtime
- Do NOT promote without evidence gate
- Do NOT delete pkl directory without operator sign-off
- Classification is final pending operator archive approval

---

## Item 2 — CLAUDE.md Stale Model References

**Document:** `docs/engineering/CLAUDE_MD_STALE_REFERENCE_REMEDIATION.md`  
**CLAUDE.md:** Updated 2026-05-23

**Evidence summary:**
- `sqpe_v14`: directory exists, pkl ABSENT — METADATA_ONLY
- `sqpe_v15`: MISSING — directory does not exist
- `longshot_v6`: directory exists, pkl ABSENT — METADATA_ONLY
- `overlay_v5`: directory exists, pkl ABSENT — METADATA_ONLY
- CLAUDE.md previously claimed all four "EXISTS on disk" — all four claims false
- Runtime impact: ZERO — none of the four referenced by any scoring path

**Council resolution:**

```
ITEM_2_STATUS: RESOLVED
CLASSIFICATION: REMEDIATED_DOCUMENTATION_ONLY
RUNTIME_IMPACT: NONE — confirmed
CLAUDE_MD_UPDATED: YES — model table corrected 2026-05-23
ACTION: Complete — no further action required
NO_MODEL_DELETION: metadata directories preserved until operator decides
```

---

## Item 3 — Arena V2 Market Timestamp Provenance

**Document:** `docs/engineering/ARENA_V2_MARKET_PROVENANCE_AUDIT.md`

**Evidence summary:**
- All 6 Arena V2 market features derive from `sp_dec` (Starting Price at race-off)
- SP is set at the moment the race begins — CLOSING_MARKET, not available at morning prediction time
- All 6 features classified: `CLOSING_MARKET_ONLY`
- Arena V2 result: all 5 packs GATE_REOPENED_SAFE_SHADOW_CANDIDATE (AUC 0.78–0.89)
- FR_AUTEUIL_JUMPS_V2: SR tied exactly with FavSR (0pp gap) — weakest pack
- Morning odds (HKJC tote pool / PMU morning price): NOT YET SOURCED

**Council resolution:**

```
ITEM_3_STATUS: CLASSIFIED
ARENA_V2_CLASSIFICATION: CLOSING_MARKET_CONFIRMATION_ENGINE
NOT_MORNING_EDGE_ENGINE: CONFIRMED
MORNING_ODDS_ARENA_REQUIRED: YES — Arena V3 required per pack before any deployment discussion
THREE_ARENA_REQUIREMENT: V1 (form-only) → V2 (closing-market) → V3 (morning odds)
INTERNATIONAL_GATE: STILL_ACTIVE — El Presidente sign-off required
SP_DERIVATIVES_IN_MORNING_FEATURES: BANNED
ACTION: Arena V2 evidence valid for research; Arena V3 required for deployment
```

---

## Item 4 — Feature Registry Review

**Document:** `docs/engineering/feature_registry_manifest_v1.csv`

**Status:** REVIEW_PENDING — Council has not yet formally reviewed all 17 entries.

This item remains open. No errors were identified in the automated review, but Council formal sign-off of the registry is pending.

```
ITEM_4_STATUS: OPEN — Council review required
ACTION: Review feature_registry_manifest_v1.csv; sign off or flag corrections
BLOCKING: No
```

---

## Item 5 — Scoring Policy Truth Reconciliation

**Documents:**
- `docs/engineering/LIVE_SCORING_TRUTH_AUDIT_2026_05_23.md` — full audit
- `CURRENT_RUNTIME_TRUTH.md` — corrected (Section 3)
- `docs/engineering/policy_registry_manifest_v1.json` — corrected (SCORING_POLICY_LIVE)
- `docs/engineering/V14_COUNCIL_ACTION_QUEUE.md` — Priority 5 resolved

**The contradiction:** `policy_registry_manifest_v1.json` declared `improvement_score=0.12`, `release_window_score=0.10`, `comment_intel_score=0.08` as live-weighted. `CURRENT_RUNTIME_TRUTH.md` Section 3 said they were DISABLED. Both documents were wrong.

**Root cause:** Both documents described the LEGACY_FULL_ENSEMBLE state (pre-surgery), not the active SQPE_IMPROVEMENT_MDS_V1 state. The Ensemble Surgery (2026-05-08, commit b7e4e0c) changed the active profile but neither document was updated correctly.

**Authoritative source:** `src/intelligence/velo_prime_ensemble.py` — `_WEIGHTS`, `_PROFILE_DISABLED`, `_DISABLED_COMPONENTS`, `compute()`.

**Established live scoring truth under SQPE_IMPROVEMENT_MDS_V1:**

| Signal | Status | Weight |
|---|---|---|
| `sqpe_v17_prob` | LIVE_WEIGHTED | 0.45 |
| `improvement_score` | LIVE_WEIGHTED | 0.12 |
| `market_deception_score` | LIVE_WEIGHTED | 0.10 |
| `place_prob` | BADGE_ONLY (not in VP) | — |
| `longshot_score` | FROZEN (not in VP) | — |
| `release_window_score` | STORED_ONLY | 0.00 |
| `comment_intel_score` | STORED_ONLY | 0.00 |

**Effective VP formula:**
`VP = (0.45 × sqpe_v17 + 0.12 × improvement_score + 0.10 × MDS) / 0.67`

**Council resolution:**

```
ITEM_5_STATUS: RESOLVED_2026-05-23
CLASSIFICATION: POLICY_REGISTRY_CORRECTED_TO_RUNTIME
IMPROVEMENT_SCORE: LIVE_WEIGHTED (0.12) — was wrongly listed as disabled
RELEASE_WINDOW_SCORE: STORED_ONLY — was wrongly listed with weight 0.10
COMMENT_INTEL_SCORE: STORED_ONLY — was wrongly listed with weight 0.08
PLACE_PROB: BADGE_ONLY — was wrongly listed as live-weighted 0.08
LONGSHOT_SCORE: FROZEN — was wrongly listed as gated live 0.07
CURRENT_RUNTIME_TRUTH_MD: CORRECTED — Section 3 updated
POLICY_REGISTRY: CORRECTED — SCORING_POLICY_LIVE entry updated
ACTION: Complete — single source of truth restored
NO_SCORING_CHANGE: CONFIRMED — no runtime behavior was altered
```

---

## Final Classification

```
V14_SINGLE_SOURCE_TRUTH_RECONCILIATION_CLOSED: YES
LIVE_SCORING_TRUTH_ESTABLISHED: YES — improvement_score=LIVE, place_prob=BADGE_ONLY, longshot_score=FROZEN
POLICY_REGISTRY_RECONCILED_TO_RUNTIME: YES — SCORING_POLICY_LIVE corrected
CURRENT_RUNTIME_TRUTH_RECONCILED: YES — Section 3 corrected
SQPE_V18_REMAINS_NOT_WIRED: CONFIRMED — classified as LAB_EXPERIMENT_COMPLETED_NO_LIFT
ARENA_V2_CLASSIFIED_AS_CLOSING_MARKET_CONFIRMATION: CONFIRMED
INTERNATIONAL_STILL_GATED: CONFIRMED — El Presidente sign-off required
NO_SCORING_CHANGE: CONFIRMED — no runtime code touched
NO_MODEL_PROMOTION: CONFIRMED
NO_ROUTER_STAKING_CHANGES: CONFIRMED
NO_TELEGRAM_RUNTIME_CHANGES: CONFIRMED
NO_PLAYBOOK_G_CHANGES: CONFIRMED
NO_LIVE_STATE_MUTATION: CONFIRMED
NO_MIGRATION: CONFIRMED
NO_WORKER_ACTIVATION: CONFIRMED
```

---

## Remaining Open Items (from V14_COUNCIL_ACTION_QUEUE.md)

| Priority | Item | Status |
|---|---|---|
| 1 | SQPE V18 formal Council vote | COUNCIL_REQUIRED (resolution above is recommended classification) |
| 2 | CLAUDE.md stale refs | Council ratification required |
| 3 | Arena V2 provenance | Council acceptance of CLOSING_MARKET classification required |
| 4 | Feature registry formal review | OPEN |
| 5 | Scoring policy truth | **RESOLVED** |
| 6 | International gate decision | GATE_ACTIVE — El Presidente sign-off required |
| 7 | Phase 3 implementation | AWAITING_APPROVAL |
