# V14 Council Action Queue

**Status:** ACTIVE — items require Council decision  
**Classification:** `COUNCIL_ACTION_REQUIRED` / `POST_MASTER_ROLLOUT`  
**Date authored:** 2026-05-23  
**Authority:** El Presidente

---

## Purpose

This queue captures all open items requiring Council decision following the V14 governance closure and master rollout plan commit. Items are ordered by urgency. No item may be actioned without Council vote except where labelled `DOCS_ONLY`.

---

## Priority Queue

### Priority 1 — SQPE V18 Formal Classification

**Status:** COUNCIL_CLASSIFICATION_REQUIRED  
**Document:** `docs/engineering/SQPE_V18_CLASSIFICATION_PACKET.md`  
**Why urgent:** A loadable model PKL (`models/sqpe_v18/sqpe_v18.pkl`) exists on disk without formal governance status. Current holding classification `UNCLASSIFIED_LOADABLE_MODEL` is a placeholder only.  
**Evidence summary:** AUC delta -0.0003, top-1 delta -0.0012. Verdict: "NO LIFT". New features (`class_delta`, `days_since_run`) combined importance 0.001. Not wired to any runtime. Archived training script. Git commit: `032793f`.  
**Recommended Council decision:** Formally close as `LAB_EXPERIMENT_COMPLETED_NO_LIFT`. Reclassify as `ARCHIVE_ELIGIBLE`. Move pkl to `archive/models_evaluated/` after vote.  
**Blocking:** Nothing is blocked by this item today. Governance hygiene only.

---

### Priority 2 — CLAUDE.md Stale Model Reference Remediation

**Status:** DOCS_UPDATE_STAGED — Council awareness required  
**Document:** `docs/engineering/CLAUDE_MD_STALE_REFERENCE_REMEDIATION.md`  
**Why urgent:** CLAUDE.md claimed four model pkls "EXISTS on disk" when three directories contain only metadata and one directory does not exist. CLAUDE.md has been updated to reflect verified state.  
**Stale refs remediated:**
- `SQPE v14` → `METADATA_ONLY` (pkl absent)  
- `SQPE v15` → `MISSING` (directory does not exist)  
- `Longshot v6` → `METADATA_ONLY` (pkl absent)  
- `Overlay v5` → `METADATA_ONLY` (pkl absent)  
- Added correct entries: `SQPE v17` (LIVE), `SQPE v18` (UNCLASSIFIED LAB)  
**Runtime impact:** NONE confirmed.  
**Council action required:** Review and ratify the CLAUDE.md correction. No runtime changes needed.

---

### Priority 3 — Arena V2 Market Timestamp Provenance Close

**Status:** AUDIT_COMPLETE — deployment decision required  
**Document:** `docs/engineering/ARENA_V2_MARKET_PROVENANCE_AUDIT.md`  
**Why urgent:** Arena V2 all 5 packs returned GATE_REOPENED. Before any deployment discussion, the Council must formally acknowledge the market timestamp constraint and confirm classification.  
**Key finding:** All 6 market features derive from `sp_dec` (Starting Price at race-off). All are `CLOSING_MARKET_ONLY`. Not morning-safe. Arena V2 = `CLOSING_MARKET_CONFIRMATION_ENGINE / NOT_MORNING_EDGE_ENGINE`.  
**Council must decide:**
1. Accept `CLOSING_MARKET_CONFIRMATION_ENGINE` as the formal Arena V2 classification
2. Authorise sourcing investigation for HKJC tote pool (morning) + PMU morning prices
3. Confirm three-arena requirement (V1, V2, V3) before any pack deployment discussion  
**Blocking:** International gate plan updated with three-arena requirement. No deployment until Arena V3 built and passed.

---

### Priority 4 — Feature Registry Review

**Status:** REVIEW_PENDING  
**Document:** `docs/engineering/feature_registry_manifest_v1.csv`  
**Why pending:** The feature registry was produced as part of the V14 governance closure (commit `6e65261`). Council should review all 17 feature family entries to confirm classifications are accurate.  
**Key entries to review:**
- `MARKET_SIGNAL_INTL` — added for Arena V2, classified `CLOSING_MARKET_ONLY`
- `RPDC_PROFILE` — field mapping fix 2026-05-08, verify provenance classification is current
- Any feature family not yet present in the registry  
**Council action:** Review and sign off registry as canonical, or flag corrections.

---

### Priority 5 — Policy Registry Review

**Status:** RESOLVED_2026-05-23 — reconciliation complete  
**Document:** `docs/engineering/policy_registry_manifest_v1.json` (updated 2026-05-23)  
**Audit:** `docs/engineering/LIVE_SCORING_TRUTH_AUDIT_2026_05_23.md`  
**Resolution:** Runtime code (`velo_prime_ensemble.py`) was the authoritative source. Both `CURRENT_RUNTIME_TRUTH.md` Section 3 and `policy_registry_manifest_v1.json` SCORING_POLICY_LIVE had errors — they described the pre-surgery LEGACY_FULL_ENSEMBLE state, not SQPE_IMPROVEMENT_MDS_V1.

**Confirmed live truth under SQPE_IMPROVEMENT_MDS_V1:**
- `improvement_score`: **LIVE_WEIGHTED (0.12)** — was wrongly listed as disabled in CURRENT_RUNTIME_TRUTH.md
- `place_prob`: **BADGE_ONLY** (excluded from VP) — was wrongly listed as 0.08 live-weighted
- `longshot_score`: **FROZEN** (excluded from VP) — was wrongly listed as 0.07 live-weighted
- `release_window_score`: STORED_ONLY (weight 0.00) — correct
- `comment_intel_score`: STORED_ONLY (weight 0.00) — correct

**Documents corrected:**
- `CURRENT_RUNTIME_TRUTH.md` Section 3 — signal truth table updated
- `policy_registry_manifest_v1.json` SCORING_POLICY_LIVE — weights corrected, badge_only/frozen/stored_only sections added
- `CURRENT_RUNTIME_TRUTH.md` Next Gates — "improvement_score live-weight" removed (it is already live)

**Council action:** Ratify the resolution. No further scoring investigation needed.

---

### Priority 6 — International Next Gate Decision

**Status:** GATE_STILL_ACTIVE — El Presidente sign-off required  
**Document:** `docs/engineering/VELO_INTERNATIONAL_NEXT_GATE_PLAN_V1.md` (updated 2026-05-23)  
**Why pending:** INTERNATIONAL_RATING_PROVENANCE_GATE locked at `589b428`. Arena V2 provides evidence but gate remains ACTIVE until El Presidente explicit sign-off.  
**Council must decide:**
1. Accept Arena V2 evidence as sufficient for gate-reopened status
2. Authorise morning odds sourcing investigation (HKJC tote pool + PMU)
3. Confirm priority pack order (HK_SHA_TIN first — largest gap +17.3pp)
4. Timeline for Arena V3 build after morning odds sourced  
**Migration, workers, training, and promotion remain fully blocked until sign-off.**

---

### Priority 7 — First Safe Implementation Slice Approval

**Status:** DESIGN_READY — awaiting Council approval to proceed  
**Document:** `docs/engineering/VELO_MASTER_ROLLOUT_INDEX.md` (Section: Immediate Next Safe Implementation Slice)  
**Why pending:** Phase 3 (Agent Harness) is the next safe implementation step. Design is committed. Implementation requires explicit Council approval to begin.  
**Scope of first slice:**
1. `Sentinel.preflight_check()` — verifiable before any live-adjacent task
2. `MissionControl.approve_task()` — task queue + approval gate
3. Wire to `scripts/maintenance/assert_canonical_worktree.py`
4. Add `VELO_SANDBOX=true` env var check to all arena/audit scripts  
**Prerequisite:** Spec-First Protocol (Phase 1) adopted as working culture first.  
**Scope constraint:** Infrastructure only. No scoring changes. No model changes.  
**Council action:** Approve Phase 3 implementation start + confirm Phase 1 (Spec-First) adoption.

---

## Standing Rules for All Queue Items

```
NO item may be actioned without Council vote (except DOCS_ONLY items already executed)
NO scoring changes via any queue item
NO model promotion via any queue item
NO router/staking changes via any queue item
NO Telegram format changes via any queue item
NO migration until Priority 6 sign-off AND Arena V3 pass
NO workers until Priority 6 sign-off AND source legality confirmed
```

---

## Queue Status Summary

| Priority | Item | Status | Blocking? |
|---|---|---|---|
| 1 | SQPE V18 classification | COUNCIL_REQUIRED | No (governance only) |
| 2 | CLAUDE.md stale refs | DOCS_EXECUTED | Council ratification |
| 3 | Arena V2 market provenance | AUDIT_COMPLETE | Yes — international gate |
| 4 | Feature registry review | REVIEW_PENDING | No |
| 5 | Policy registry review | **RESOLVED_2026-05-23** | No — scoring truth established |
| 6 | International gate decision | GATE_ACTIVE | Yes — all international work |
| 7 | Phase 3 implementation | AWAITING_APPROVAL | Yes — agent harness build |

---

```
V14_COUNCIL_ACTION_QUEUE_STATUS: ACTIVE
ITEMS_OPEN: 6 (Priority 5 resolved 2026-05-23)
HIGHEST_PRIORITY: SQPE_V18_CLASSIFICATION (Priority 1)
HIGHEST_BLOCKING: INTERNATIONAL_GATE_DECISION (Priority 6)
PRIORITY_5_RESOLVED: improvement_score=LIVE_WEIGHTED(0.12), place_prob=BADGE_ONLY, longshot_score=FROZEN
```
