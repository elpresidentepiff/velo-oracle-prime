# V14 Council Action Queue

**Status:** ACTIVE — items require Council decision  
**Classification:** `COUNCIL_ACTION_REQUIRED` / `POST_MASTER_ROLLOUT`  
**Date authored:** 2026-05-23  
**Updated:** 2026-05-24 — Priority 0 added (live degradation gates)  
**Authority:** El Presidente

---

## Purpose

This queue captures all open items requiring Council decision following the V14 governance closure and master rollout plan commit. Items are ordered by urgency. No item may be actioned without Council vote except where labelled `DOCS_ONLY`.

---

## Priority Queue

### Priority 0 — RPDC and Supabase Fallback Gates (NEW — 2026-05-24)

**Status:** IMPLEMENTATION_REQUIRED — live degradation confirmed  
**Audit:** `docs/engineering/MAY24_SUPABASE_RPDC_INCIDENT_AUDIT.md`  
**Operator packet:** `docs/engineering/MAY24_OPERATOR_CORRECTION_PACKET.md`  
**Why urgent:** The 2026-05-24 scoring run was classified `OFFICIAL_VALID_FEATURE_DEGRADED`. improvement_score was silently excluded from the VP ensemble on all 29 races. The system sent "strong card" and "A-STRIKE" to Telegram without any degraded-feature banner. RPDC has been broken since 2026-05-08 (16+ days). None of these conditions triggered a Mission Control alert. This is a live scoring integrity gap — not a governance hygiene item.

**Immediate actions required (before next scoring run):**
1. Run `ingest_results_to_horse_runs.py --date 2026-05-23` to repair the chain
2. Run `build_rpdc_daily.py --date 2026-05-24` to verify RPDC returns >0 runners
3. Operator decision: RESCORE_TODAY / HOLD_AS_DEGRADED / COMPARE_ONLY

**Six gates to implement (implementation requires Council approval):**

| Gate | Trigger | Action |
|---|---|---|
| `RPDC_ZERO_BLOCK_OR_WARN` | build_rpdc_daily returns 0 runners | WARN in Telegram pre-flight + Mission Control |
| `FEATURE_DEGRADED_BANNER` | Any live-weighted component excluded from ensemble | Banner in Telegram, dashboard, Mission Control |
| `SUPABASE_PUBLISH_FALLBACK_WARN` | Dashboard publisher uses local_json_top_only | WARN in Telegram summary |
| `SUPABASE_WRITE_PROOF_REQUIRED` | After every persist step | Query count + NULL check, log to mission_control |
| `RPDC_COVERAGE_WARN` | runner_release_candidates > 3 days stale | Pre-flight WARN before scoring |
| `LEARNING_ELIGIBILITY_BLOCK` | Sigma day where improvement_score was constant | Block EOD learning bridge |

**Council action:** Approve gate implementation. Assign implementation owner. These are operational safety gates, not governance hygiene.  
**Blocking:** Until gates are implemented, every scoring run without prior RPDC verification must be manually reviewed post-run.

---

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

**Status:** READY_FOR_COUNCIL_REVIEW — schema upgrade complete  
**Document:** `docs/engineering/feature_registry_manifest_v1.csv`  
**Upgrade:** Registry upgraded from V1 summary schema to V14 governance schema (commit `923f724`). All 17 rows now have: feature_name, feature_family, source, jurisdiction, pre_race_safe, timestamp_provenance, leakage_risk, live_scoring_allowed, shadow_allowed, training_allowed, null_policy, drift_policy, owner, last_reviewed, notes. Validator passes (exit code 0).  
**Key entries for Council review:**
- UK live rows (UK_FORM_CORE, UK_SIDECAR_SCORES, UK_RPDC_TAGS, JTC_D_PROFILES, UK_MACRO_REGIME) — confirm live_scoring_allowed=true and null/drift policies
- HK/FR rows — confirm all live_scoring_allowed=false per INTERNATIONAL_RATING_PROVENANCE_GATE
- SHADOW_ONLY rows (UK_RACE_SHAPE, SHADOW_MODEL_CHALLENGER) — confirm shadow classification
- FUTURE_ENRICHMENT rows (HK_MORNING_ODDS, FR_MORNING_ODDS, FR_PENETROMETER, FR_QUINTET_PLUS, FR_CLASS_PROXY) — confirm not_yet_built status
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
| **0** | **RPDC/Supabase fallback gates** | **IMPLEMENTATION_REQUIRED** | **Yes — next scoring run** |
| 1 | SQPE V18 operator archive decision | COUNCIL_REQUIRED | No (governance only) |
| 2 | CLAUDE.md stale refs | **CLOSED_2026-05-23** | No |
| 3 | Arena V2 provenance / Arena V3 requirement | AUDIT_COMPLETE | Yes — international gate |
| 4 | Feature registry Council review | **READY_FOR_COUNCIL_REVIEW** | No |
| 5 | Policy registry reconciliation + schema upgrade | **CLOSED_2026-05-23** | No |
| 6 | International next gate sign-off | GATE_ACTIVE | Yes — all international work |
| 7 | First implementation slice approval | AWAITING_APPROVAL | Yes — agent harness build |

**Closed this session:**
- Priority 2: CLAUDE.md stale refs — REMEDIATED_DOCUMENTATION_ONLY (commit `da666fe`)
- Priority 5: Scoring weight discrepancy + policy schema upgrade — CLOSED. improvement_score=LIVE_WEIGHTED(0.12), place_prob=BADGE_ONLY, longshot_score=FROZEN. Registry and CURRENT_RUNTIME_TRUTH.md corrected and upgraded to V14 schema (commits `ff34490`, `ce51f0c`, `74a0e90`, `59920c6`)
- Manifest validator: V14_MANIFEST_SCHEMA_UPGRADE_COMPLETE. Both registries upgraded, validator exit 0. Commits `923f724` (feature CSV), `59920c6` (policy JSON).

**Remaining open (4 items require Council/operator decision):**
- Priority 1: SQPE V18 — formal archive decision (pkl present, no runtime risk, no urgency)
- Priority 3: Arena V3 morning odds arena — can only start after operator sign-off + source legality confirmed
- Priority 4: Feature registry — schema upgrade done (commit `923f724`); Council review + formal sign-off now unblocked
- Priority 6: International gate — El Presidente explicit sign-off required
- Priority 7: First implementation slice — Council approval required

---

```
V14_COUNCIL_ACTION_QUEUE_STATUS: ACTIVE
ITEMS_OPEN: 4
ITEMS_CLOSED_THIS_SESSION: 3 (Priority 2, Priority 5 scoring reconciliation, manifest schema upgrade)
PRIORITY_4_STATUS: READY_FOR_COUNCIL_REVIEW — schema upgrade complete, validator passing
HIGHEST_BLOCKING: INTERNATIONAL_GATE_DECISION (Priority 6)
LIVE_SCORING_TRUTH: ESTABLISHED_AND_CLOSED
V14_SINGLE_SOURCE_TRUTH_RECONCILIATION: CLOSED_2026-05-23
V14_MANIFEST_SCHEMA_UPGRADE: COMPLETE_2026-05-23 — validator exit 0
```
