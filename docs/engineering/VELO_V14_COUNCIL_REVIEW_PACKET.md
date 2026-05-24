# VÉLØ V14 Council Review Packet

**Prepared:** 2026-05-23  
**Authority:** El Presidente (solo operator)  
**Status:** READ-ONLY — no runtime changes authorised  
**Purpose:** Structured summary of open items requiring operator decision before any system change.

---

## Section 1 — Open Items Requiring Sign-off

### 1A. SQPE V18 — Classification Required (BLOCKING)

**Discovery:** V14 truth map pass (2026-05-23)  
**File:** `models/sqpe_v18/sqpe_v18.pkl` — loadable, unreported in CLAUDE.md  
**Risk:** Unclassified model in production repo. No evidence of when it was trained or what data it used.

**Classification (locked until Council decision):**
```
UNCLASSIFIED_LOADABLE_MODEL
NOT_WIRED
NO_PROMOTION
COUNCIL_CLASSIFICATION_REQUIRED
EVIDENCE_TRAIL_REQUIRED
```

**Hard rules that apply immediately:**
- Do NOT delete it (preserve for Council audit)
- Do NOT wire it to any scoring path
- Do NOT evaluate it as live evidence
- Do NOT promote it under any circumstances until evidence trail is produced and Council reviews

**Required Council action:** Produce evidence trail (training date, training data, purpose) and classify as SHADOW / ARCHIVED / PROMOTE. Until then, quarantine status holds.

---

### 1B. Stale Model References — Cleanup Required

| Reference | Status | Action |
|---|---|---|
| `models/sqpe_v15/` | `STALE_REFERENCE_IN_CLAUDE_MD` / `DOCS_REMEDIATION_REQUIRED` / `NO_RUNTIME_IMPACT_CONFIRMED` | Remove from CLAUDE.md. No runtime impact confirmed. |
| `models/longshot_v6/` | `METADATA_ONLY` / `NOT_LOADABLE` / `NO_RUNTIME_MODEL_PRESENT` | Mark deprecated. Superseded by specialist longshot_model. |
| `models/overlay_v5/` | `METADATA_ONLY` / `NOT_LOADABLE` / `NO_RUNTIME_MODEL_PRESENT` | Mark deprecated. |
| `models/sqpe_v14/` | `METADATA_ONLY` / `NOT_LOADABLE` | Confirm archive or delete. |

**Risk level:** LOW — these are not in the live scoring path. Cleanup prevents future confusion.

### 1C. Verified Discoveries — Acknowledge Only

| Item | Classification |
|---|---|
| `src/velo/council/` | `COUNCIL_MODULE_PRESENT` / `PATH_VERIFIED` |
| `models/shadow/model_arena/` | `SHADOW_ARENA_PRESENT` / `NO_LIVE_PROMOTION` |
| `models/shadow/model_arena_v2/` | `SHADOW_ARENA_PRESENT` / `NO_LIVE_PROMOTION` |

---

### 1D. International Provenance Gate — Pending Arena V2 Result

**Gate:** `INTERNATIONAL_RATING_PROVENANCE_GATE_ACTIVE` (locked `589b428`)

Arena V2 adds SP-based market signal (implied_prob, sp_rank, market_prob_ratio, form_mkt_diverge). This is the first test of whether market consensus, available at race start, is sufficient to beat the favourite baseline.

**Expected outcome range:**
- If gate REOPENED (AUC ≥ 0.75, SR > FavSR): one or more packs eligible for migration discussion → operator sign-off required before any migration.
- If NEEDS_FE (AUC ≥ 0.65, SR > FavSR): signal present, below threshold. Next step: morning odds ingestion (HKJC tote / PMU).
- If still FAILS: all remaining paths require external data.

**Required action if gate reopens:** El Presidente explicit sign-off before any of:
1. Applying `migrations/intl_schemas_v1.sql`
2. Building HKJC/PMU ingest workers
3. Any international model training
4. Any international promotion

---

### 1D. Shadow Model V1 — Promotion Gate Check

**File:** `models/shadow/model_arena/`  
**Forward lane active:** 2026-05-18  
**Current evidence:** PASS_QUARANTINE. Top-decile ROI +11.86% vs VP +4.67% without SP.  
**Promotion gates:** 300+ runners, 75+ top-decile, operator decision.

**Required operator decision when gates are reached:** Explicit sign-off to promote shadow model from evidence accumulation to live shadow scoring path.

---

### 1E. src/velo/council/ — Status Confirmation

**Discovery:** Council module exists (`src/velo/council/`) but is not documented in CLAUDE.md.  
**Files:** `council_orchestrator.py`, `agents.py`, `verification.py`, `tool_registry.py`, `evidence_packet.py`

**Required operator decision:** Is this module active/inactive? What pipeline does it serve?

---

## Section 2 — Gate Status Summary

| Gate | Status | Operator Action Required |
|---|---|---|
| INTERNATIONAL_PROVENANCE_GATE | ACTIVE — arena V2 result pending | Sign-off if gate reopens |
| SQPE_V18_CLASSIFICATION | UNCLASSIFIED | Classify: SHADOW / ARCHIVED / PROMOTE |
| SHADOW_MODEL_V1_PROMOTION | ACCUMULATING | Sign-off when n≥300 runners |
| VP40_TIER_A_SHORTPRICE | UNDER_REVIEW | Sign-off when n≥150 |
| POWER_ANCHOR_PAPER_LEDGER | n=3 (need n≥20) | First review at n≥20 |
| PLAYBOOK_G_PROMOTION | TRAINING_READY | Sign-off when promoted |

---

## Section 3 — Architecture Health Assessment

### Green (stable, no action required)

- ✅ UK daily pipeline: LIVE_RUNTIME, all scripts path-verified
- ✅ SQPE v17 ensemble: active, evidence confirmed (ROI +13.5% vs legacy)
- ✅ All 7 specialist models: pkl files verified
- ✅ TIE v9: loadable
- ✅ Sigma process: locked, run_results_sigma.py enforced
- ✅ VP band truth: monotonic, 49-day audit confirmed
- ✅ Feature safety: 49 PRE_RACE_SAFE international features audited
- ✅ HK/FR pre-race V2 parquets: built with market signal, 100%/99.9% coverage

### Amber (monitoring required, no immediate action)

- ⚠️ B-tier VP<0.30: confirmed drag, suppression test shows modest gain — track coverage cost
- ⚠️ Mid-priced winner miss (SP 3–8.5): 58% of all misses — primary unsolved problem
- ⚠️ Router lanes V1/V2/V6: evidence accumulating, below promotion thresholds
- ⚠️ Release day prob: 10% live weight — n=0 in sigma (pipeline gap, RPDC fix 2026-05-08)

### Red (requires decision before proceeding)

- 🔴 SQPE V18: unclassified model in repo, no evidence trail
- 🔴 International gate: ACTIVE — no migration/workers/training until resolved
- 🔴 Stale CLAUDE.md model references: sqpe_v15, longshot_v6 pkl, overlay_v5 pkl

---

## Section 4 — Hard Rules (Permanent, Never Override)

```
1. No live staking
2. No candidate_route() changes without evidence gate passed
3. No router rule changes
4. No model changes from single-day analysis
5. No baseline overwrite
6. No force push
7. No Playbook E
8. No scoring changes without operator sign-off
9. No model promotion without n≥100 + operator sign-off
10. Sigma: ALWAYS run_results_sigma.py. NEVER close_sigma_loops.py.
11. Telegram format: LOCKED. Never change.
12. 2026-05-20: SCORING_FLATLINE_CONTAMINATED. Must not enter training.
13. Credentials: .env only. Never hardcode. Never commit.
14. International gate: No migration/workers/training until INTERNATIONAL_PROVENANCE_GATE closes.
15. fr_research and hk_research schemas NOT YET CREATED in Supabase.
16. UK pipeline: UNCHANGED during all international work.
```

---

## Section 5 — Recommended Next Actions (Operator Priority Order)

1. **[IMMEDIATE]** Review arena V2 result — determine gate status for each pack.
2. **[THIS WEEK]** Classify SQPE V18 (Shadow / Archive / Promote).
3. **[THIS WEEK]** Clean up stale CLAUDE.md model references (sqpe_v15, longshot_v6, overlay_v5).
4. **[IF GATE REOPENS]** El Presidente sign-off on international migration — explicit approval, one pack at a time.
5. **[ONGOING]** Continue router lane evidence accumulation: V2 needs +3 qualifying results for WATCHLIST gate.
6. **[ONGOING]** Shadow Model V1: continue forward accumulation until n≥300 runner threshold.

---

```
COUNCIL_REVIEW_PACKET_V1_STATUS: COMPLETE
PREPARED: 2026-05-23
AUTHORITY: El Presidente
OPEN_ITEMS: 5 (1A SQPE_V18, 1B stale refs, 1C intl gate, 1D shadow promo, 1E council module)
NO_RUNTIME_CHANGES_AUTHORISED_BY_THIS_DOCUMENT
```
