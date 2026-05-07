CANONICAL RUNTIME LOCK — READ FIRST

1. Only /mnt/c/Users/puror/velo-oracle-prime on branch main is canonical.
2. /mnt/c/Users/puror/velo_feature_v10_launch_fix or OneDrive feature_v10_launch_fix is stale reference only.
3. Any work done outside canonical repo is invalid unless labelled FORENSIC_COMPARISON_ONLY.
4. All future commands must first confirm:
   - repo root
   - branch
   - HEAD
   - remote
   - dirty state
5. No scoring, audit, card, report, or deployment command may run from a non-canonical worktree.
6. If canonical check fails, STOP.

### Commands

pwd
git rev-parse --show-toplevel
git branch --show-current
git rev-parse --short HEAD
git remote -v
git status --short

### Labels

CANONICAL:
- /mnt/c/Users/puror/velo-oracle-prime
- branch: main

STALE_REFERENCE:
- /mnt/c/Users/puror/velo_feature_v10_launch_fix
- C:\Users\puror\OneDrive\Documents\New project\velo_feature_v10_launch_fix

---

PRE-RUN LAW

Before any of these commands:
- run_prime_today
- vp30_operator_card
- racing_api_enrichment_operator_card
- cashrun_detector
- router_shadow_audit
- signal_promotion_board
- build_unified_evidence_corpus
- run_execution_bridge_shadow
- close_sigma_loops
- deployment

Run:

python scripts/assert_canonical_worktree.py

If it fails, do not proceed.

---

DEPLOYMENT SOURCE STATUS

Current:
DEPLOYMENT_SOURCE_UNKNOWN

Known:
- Railway start command appears to be uvicorn app.main:app --host 0.0.0.0 --port \${PORT:-8080}
- deployed branch/commit must still be verified

Next required check:
- Railway dashboard/CLI or health endpoint must expose deployed commit
- Until then, “canonical repo” and “deployed runtime” are separate facts

---

# VÉLØ Process Wiring Map V1

> **One Truth document.** Defines how data flows through VÉLØ from scoring through operator output.
> Companion to `TRUTH_REGISTRY.md` (field/table truth) and `VELO_RUNTIME_MAP_V1.md` (file classification).
> Last updated: 2026-05-01.

---

## Daily Flow Overview

```
Racing API
    │
    ▼
run_prime_today.py  ── normalize ── score_race_velo_prime()
    │                                       │
    │                                velo_verdicts (Supabase)
    │                                       │
    ├─── Telegram: VP30 card (A/B/C/D/X)   │
    │                                       │
    ├─── Telegram: PLACE SIGNALS ◄──────────┤ (see Section 1)
    │                                       │
    └─── Local: place_signal_operator_card.py ◄── scripts/place_signal_operator_card.py
                        │
                data/place_signal_operator_card_YYYY_MM_DD.md

After results close:
    run_results_sigma.py ──► sigma_audits (Supabase) / velo_post_race_reviews
```

---

## Section 1 — Place Signal Classifier: Operator Visibility Layer

### Status

```
OPERATOR_VISIBILITY_ONLY
TELEGRAM_OPTIONAL           (gate: VELO_ENABLE_PLACE_SIGNAL_TELEGRAM, default OFF, now ON)
NOT_LIVE_WEIGHTED           (no change to velo_prime_prob, SQPE, ensemble)
NOT_STAKING                 (no betting instruction)
NOT_ROUTER_PROMOTION        (no candidate_route() change)
NO_SCORING_CHANGE           (read-only from velo_verdicts)
```

### Files

| File | Role |
|---|---|
| `src/velo/place_signal_classifier.py` | Core classifier — `PlaceSignal` dataclass + `classify()` + `classify_from_verdict()` |
| `scripts/place_signal_operator_card.py` | Daily operator card — reads `velo_verdicts`, classifies, outputs markdown |
| `scripts/run_prime_today.py` | Wires place signal Telegram via `_build_place_signal_tg()` in STEP 5 |

### Entry Point

```python
from src.velo.place_signal_classifier import classify_from_verdict, PlaceSignal
sig: PlaceSignal = classify_from_verdict(verdict_row)
```

### Inputs (from `velo_verdicts`)

| Field | Threshold | Role |
|---|---|---|
| `velo_prime_prob` | ≥ 0.30 = VP30 | Primary gate — no signal below |
| `decision_tier` | `A` = elite tier | ELITE gate trigger |
| `market_deception_score` | > 0.50 = MDS_HIGH | ELITE / STRONG gate trigger |
| `improvement_score` | > 0.40 = IMP_HIGH | STRONG_PLUS / IMPROVE_WATCH trigger |
| `place_prob` | > 0.80 = PLACE_HIGH | PLACE_SUPPORT trigger |

### Classification Priority (first match wins)

| Label | Conditions | Status | Min Place Odds | E/W 1/4 ROI | n |
|---|---|---|---:|---:|---:|
| `ELITE_PLACE_STACK` | Tier A + VP30 + MDS_HIGH | `LIVE_OPERATOR_PLACE_SIGNAL` | 1.05 | +170% | 28 |
| `STRONG_PLACE_STACK_PLUS` | VP30 + MDS_HIGH + IMP_HIGH | `LIVE_OPERATOR_PLACE_SIGNAL` | 1.05 | +90% | 20 |
| `STRONG_PLACE_STACK` | VP30 + MDS_HIGH | `LIVE_OPERATOR_PLACE_SIGNAL` | 1.05 | +169% | 35 |
| `IMPROVE_PLACE_WATCH` | VP30 + IMP_HIGH (no MDS) | `LIVE_OPERATOR_PLACE_WATCH` | 1.20 | +51% | 46 |
| `SUPPRESS` | Tier B + VP < 0.30 | `SUPPRESS` | never | — | 303 |
| `PLACE_SUPPORT_WATCH` | VP30 + PLACE_HIGH (no MDS, no IMP) | `LIVE_OPERATOR_PLACE_WATCH` | 1.40 | +59% | 251 |
| `BASE_PLACE_TRUST` | VP30 only | `BASE_PLACE_TRUST` | 1.50 | +52% | 380 |
| `BELOW_VP30` | VP < 0.30 | `NO_SIGNAL` | — | — | — |

### Outputs

`PlaceSignal` dataclass fields:

| Field | Type | Notes |
|---|---|---|
| `place_stack_label` | str | Label from table above |
| `place_stack_status` | str | `LIVE_OPERATOR_PLACE_SIGNAL` / `LIVE_OPERATOR_PLACE_WATCH` / `BASE_PLACE_TRUST` / `NO_SIGNAL` / `SUPPRESS` |
| `min_place_odds` | float\|None | Minimum exchange place odds for +EV (operator must verify) |
| `evidence_n` | int | Sample size from audit |
| `evidence_frame_rate` | float | WIN+PLACE rate from audit |
| `evidence_win_sr` | float | Win strike rate from audit |
| `evidence_ew_1_4_roi` | float | Each-way 1/4 place-leg ROI from audit |
| `badges` | list[str] | Flags that fired: `VP30`, `MDS_HIGH`, `IMP_HIGH`, `PLACE_HIGH`, `TIER_A` |
| `suppress_reason` | str\|None | `B_TIER_LOW_VP` if SUPPRESS |
| `place_operator_note` | str | Human-readable evidence note |

### Telegram Gate

```
Env var:  VELO_ENABLE_PLACE_SIGNAL_TELEGRAM
Default:  0 (OFF)
Current:  1 (ON — set 2026-05-01)
```

When enabled, fires in `run_prime_today.py` STEP 5 — after C-WATCH list, before D/X pass list.
Sends ELITE through BASE_PLACE_TRUST only. SUPPRESS and BELOW_VP30 are excluded from Telegram.
Gated in a try/except — failure is non-fatal, scoring pipeline unaffected.

### Where It Sits in Daily Flow

1. `run_prime_today.py` STEP 3 — verdicts generated + persisted to `velo_verdicts`
2. `run_prime_today.py` STEP 4 — verdicts written to Supabase
3. `run_prime_today.py` STEP 5 — `_build_place_signal_tg()` classifies from `scored` list (in-memory), sends if gate ON
4. Separately: `scripts/place_signal_operator_card.py --date YYYY-MM-DD` — reads from Supabase, outputs full markdown card
5. After results close: outcomes can be matched against place signal class for economics tracking

### Safety Contract

```
NO change to velo_prime_prob
NO change to SQPE
NO change to ensemble weights
NO change to decision_tier
NO change to candidate_route()
NO change to router shadow lanes
NO staking
NO Betfair integration
NO live execution
READ-ONLY from velo_verdicts
```

### Proof Run — 2026-05-01

```
1  ELITE_PLACE_STACK
1  IMPROVE_PLACE_WATCH
8  PLACE_SUPPORT_WATCH
5  BASE_PLACE_TRUST
9  SUPPRESS
19 BELOW_VP30
```

All syntax checks passed. No runtime errors. No scoring pipeline impact.

### Known Next Step

1. Collect outcomes (WIN / PLACED / MISS) per place signal class over next 20+ days
2. Track actual place frame rate vs audit expectation
3. Do not discuss promotion until n≥20 per class with closed results

### Commit History

| Commit | Description |
|---|---|
| `58ed2a1` | feat: add VÉLØ place economics audit and place signal operator visibility |

---

## Section 2 — CASHRUN Detector: Racing Post Intent Layer

### Company line

```
Racing API  = structure
Racing Post = intent
VP          = probability
MDS         = market deception
CASHRUN     = handicap plot detection
```

### Status

```
OPERATOR_INTELLIGENCE_ONLY
NO staking. NO betting instruction. NO scoring change. NO model change.
NO router change. NO Playbook E. NO live execution.
Read-only from per-venue merged JSON + Racing API racecard.
```

### File

| File | Role |
|---|---|
| `scripts/cashrun_detector.py` | Detector — reads merged PDFs + Racing API, scores each horse, outputs MD + CSV |

### Inputs

| Source | Fields |
|---|---|
| `data/racecard_merged/racecard_{VENUE}_{DATE}.json` | `or_run_history`, `ts_run_history`, `spotlight_comment`, `postdata_score`, `intent_signals`, `trainer_form`, `going_flag`, `distance_flag`, `course_flag`, `plot_conviction`, `or_compression_score`, `or_trend_drops` |
| `data/racecards_{DATE}_standard.json` (Racing API) | `ofr`, `ts`, `rpr`, `lbs`, `draw`, `headgear`, `wind_surgery`, `trainer_14_days`, `form`, `jockey`, `trainer`, `last_run`, `spotlight` (fallback) |

### Scoring model

| Signal | Max | Description |
|---|---|---|
| Mark compression | 30 | Current OR vs last winning OR; OR drop trend; career-low OR |
| TS/RPR hidden form | 20 | TS/RPR holding while OR falls; improving TS; RPR ahead of OR |
| Setup run pattern | 20 | Intent signals + course/dist/going flags + setup phrases in spotlight |
| Trainer/jockey intent | 15 | Trainer form + 14-day % + headgear + wind surgery + intent signals |
| Spotlight/postdata intent | 15 | Positive/negative phrase score + postdata pick + plot conviction |

### Classification thresholds

| Class | Score range | Meaning |
|---|---|---|
| `CASHRUN_READY` | 75–100 | Full convergence — all signals aligned |
| `CASHRUN_WATCH` | 55–74 | Partial convergence — monitor for market confirmation |
| `WEAK_SIGNAL` | 35–54 | Some signal but insufficient evidence |
| `SUPPRESS` | 0–34 | No convergence or active negative signals |

### Outputs

| File | Format |
|---|---|
| `data/cashrun_report_YYYY_MM_DD.md` | Full operator report: per-horse detail, field coverage, system integrity |
| `data/cashrun_report_YYYY_MM_DD.csv` | Machine-readable: all scored horses with signal breakdowns |

### Field coverage proof (2026-05-01 run)

| Check | Coverage | Notes |
|---|---|---|
| Files parsed | 6 venues | NMK WAR NCS GOO ASC PUN |
| Horses scanned | 379 | — |
| Last-6 OR | 89% | — |
| Last-6 TS | 88% | — |
| Current RPR | 85% | — |
| Spotlight | 100% | Racing API fallback used for venues without spotlight_comment |
| Postdata | 67% | Only venues with full PDF parse |
| Trainer 14-day | 94% | From Racing API |
| Headgear | 34% | Only flags actual headgear use — missing = no headgear |
| Last-6 RPR | NOT_IN_SOURCE | PDF parser extracts current RPR only; per-run RPR not available |

### 2026-05-01 proof run result

```
CASHRUN_READY:  1  (Police Academy — WAR 6.50 — score 79.0)
CASHRUN_WATCH:  30
WEAK_SIGNAL:    94
SUPPRESS:       254
```

### Safety contract

```
NO change to velo_prime_prob
NO change to SQPE or ensemble
NO change to decision_tier
NO change to router
NO staking
NO Betfair
NO live execution
READ-ONLY from per-venue JSON + Racing API racecard
```

### CASHRUN Result Validation Status

Audit run: 2026-05-01. Script: `scripts/cashrun_results_audit.py`.
Outputs: `data/cashrun_results_audit_latest.md/.csv` (gitignored — not committed).

| Metric | Value |
|---|---|
| Dates audited | 7 (2026-04-22 → 2026-05-01) |
| Total horses scored | 2,933 |
| Result-matched | 2,328 (79%) |
| CASHRUN_READY matched | 6 |
| CASHRUN_READY SR | 0% |
| CASHRUN_READY Frame | 33% |
| CASHRUN_WATCH matched | 149 |
| CASHRUN_WATCH SR | 13% |
| CASHRUN_WATCH Frame | 35% |
| SUPPRESS SR | 10% |
| Classification | **CASHRUN_NEEDS_MORE_DATA** |

**Police Academy (WAR 6.50, 2026-05-01):**
Score=79 (CASHRUN_READY) | SP=2.75 | Pos=2 | **PLACED** | P&L=-1.00

**Signal observations:**
- READY sample n=6 — too small for win/ROI verdict
- Score band correlation not fully monotonic (35–54 band frame > 55–74) — calibration work needed
- WATCH SR 13% vs SUPPRESS 10% — modest separation only
- High average SP in READY class (20.6) — detector firing on longer-priced horses
- CASHRUN_NEEDS_MORE_DATA: need ≥10 READY closed results before signal verdict

**What this means:**
CASHRUN detector reads the right fields, classifies consistently, and produced its first READY call correctly (Police Academy placed). But the sample is too thin to confirm whether the scoring model separates intent from noise. Accumulate more days. No live weight impact. No staking.

### Commit history

| Commit | Description |
|---|---|
| (pre-existing) | `cashrun_detector.py` built during CASHRUN session |
| (pending approval) | SETUP_PHRASES expanded; spotlight fallback; NOT_IN_SOURCE label; `cashrun_results_audit.py` added |

---

## Section 3 — HFS Signal Contract Repair: MPI / Chaos Bloom

### Root Cause

`VeloPrimePrediction.to_dict()` never emitted `mpi` or `chaos_bloom`.
`backfill_historical_feature_store.py` used `payload.get("mpi")` → None → NULL.
13,361 HFS rows (2026+ live era) were signal-dark.

### Fix Applied

Patch: `src/intelligence/velo_prime_ensemble.py`
- `mpi`, `chaos_bloom`, `mpi_source`, `chaos_bloom_source`, `mpi_block_reason`,
  `chaos_bloom_block_reason`, `signal_contract_version`
  added to `VeloPrimePrediction` dataclass and `to_dict()`
- `_compute_hfs_signals()` method added, called at end of `compute()`

Formula version: `hfs_signal_contract_v1`
- `mpi = velo_prime_prob * 0.6 + market_deception_score * 0.4`, bounded [0,1], null-safe
- `chaos_bloom = macro entropy from chaos_mode + favourite_trap_risk`, bounded [0,1], null-safe

Provenance fields:
- `mpi_source`: `"derived_from_vp_mds"` | `"derived_from_vp_only"`
- `chaos_bloom_source`: `"derived_from_macro_field_trap"`
- `signal_contract_version`: `"hfs_signal_contract_v1"`

### Backfill

Script: `scripts/backfill_hfs_mpi_chaos_bloom.py`
Status: DRY-RUN complete (2026-05-02)

```
HFS rows scanned:                    13361
HFS total rows:                      31936
Rows with mpi NULL:                  13361  (41.8%)
Rows with chaos_bloom NULL:          13361  (41.8%)
Signal index coverage:               1539 (race_id, horse_id) pairs from velo_verdicts
MPI eligible for repair:             2102
MPI blocked (missing inputs):        11259
chaos_bloom eligible for repair:     2102
chaos_bloom blocked:                 11259
Rows with at least one update:       2102
MPI distribution (proposed):         n=2102  min=0.0008  max=0.4646  mean=0.0510  std=0.0540
chaos_bloom distribution (proposed): n=2102  min=0.3000  max=0.3000  mean=0.3000  std=0.0000
```

Note: 11,259 blocked rows have no signal source in velo_verdicts — these are pre-scored
historical runs where no verdict was stored. They remain NULL until the full backfill
(backfill_historical_feature_store.py) is re-run with the patched pipeline.

### HFS Integrity Audit

Script: `scripts/audit_hfs_signal_integrity.py`
Output: `data/hfs_signal_integrity_audit_latest.md`
Classification: `HFS_TRAINING_BLOCKED`

```
Blocked reason: mpi null% = 41.8% (> 10% threshold)
Blocked reason: chaos_bloom null% = 41.8% (> 10% threshold)
```

After `--apply` backfill + re-run of `backfill_historical_feature_store.py`:
- 2102 rows repaired immediately via `backfill_hfs_mpi_chaos_bloom.py --apply`
- Remaining 11,259 repaired via full `backfill_historical_feature_store.py` re-run
- Re-run audit to confirm `HFS_TRAINING_READY` classification before any training

### HFS Signal Integrity Repair — Batch 1 Reconstruction

Controlled apply via `backfill_historical_feature_store.py` (patched with null-signal targeting):

**Pre-conditions confirmed (2026-05-02):**
- Previous null rate: 35.3% (11,259 rows, after `backfill_hfs_mpi_chaos_bloom.py` partial repair)
- All 11,259 rows are 2026 live-era (2026-03-15 to 2026-04-26), scoring_status=`missing_prediction`
- Root cause: `score_race_velo_prime()` returned no prediction for these runners (missing age/weight/OR fields in `runner_results`)
- 1,379 unique race_ids: all present in `races` DB table — 100% reconstructable when DB password is set
- Backup CSV written: `data/hfs_recon_backup_batch1_20260502.csv` (11,259 rows)

**Script patched — new CLI flags added to `scripts/backfill_historical_feature_store.py`:**
- `--year 2026` — filter to races from this calendar year
- `--only-null-signals` — target HFS rows where mpi IS NULL or chaos_bloom IS NULL (UPDATE, not INSERT)
- `--dry-run` — compute but do not write to DB
- `--limit-races N` — stop after N races
- `--batch-size N` — alias for --batch-races
- `--audit-before-after` — print null counts before and after run
- `load_dotenv()` added to script startup via `runtime_env.load_optional_env_file`

**Dry-run status: BLOCKED — DB direct connection unavailable**
- `SUPABASE_DB_URL` in `.env` contains placeholder password (`your_db_password`)
- `db.ltbsxbvfsxtnharjvqcm.supabase.co:5432` unreachable via IPv6 from WSL2
- Supabase pooler (`aws-0-eu-west-2.pooler.supabase.com:5432`) IS reachable
- To unblock: update `SUPABASE_DB_URL` in `.env` with real DB password:
  `postgresql://postgres.ltbsxbvfsxtnharjvqcm:[REAL_PASSWORD]@aws-0-eu-west-2.pooler.supabase.com:5432/postgres`
- Get password from: Supabase Dashboard → Settings → Database → Connection string

**Batch 1 controlled apply — PENDING (not yet run)**
- Batch 1 target: 100 races, 2026+, null-signal only
- Rows updated: [pending — requires DB password]
- Rows remaining dark: [pending]
- Command when ready:
  ```bash
  source venv/bin/activate && PYTHONPATH=. python scripts/backfill_historical_feature_store.py \
    --year 2026 --only-null-signals --dry-run --limit-races 25 --audit-before-after
  ```
  Then (after dry-run passes):
  ```bash
  source venv/bin/activate && PYTHONPATH=. python scripts/backfill_historical_feature_store.py \
    --year 2026 --only-null-signals --limit-races 100 --audit-before-after
  ```

**Current audit state (2026-05-02 post-session):**
- Total HFS rows: 31,936
- NULL mpi rows: 11,259 (35.3%)
- NULL chaos_bloom rows: 11,259 (35.3%)
- Classification: `HFS_TRAINING_BLOCKED`
- Blocked reasons: mpi null% = 35.3% | chaos_bloom null% = 35.3%

### Playbook G Status

BLOCKED — no training until `HFS_TRAINING_READY` classification confirmed.

### Safety

```
NO scoring change
NO SQPE change
NO VP change
NO router change
NO staking
NO Telegram change
NO live execution
```

---

## Dashboard Data Contract — Governed Card + Sidecar Stack

### Main governed card lane

- Endpoint: `app/main.py`
- Function: `governed_card`
- Request shape: `/api/governed-card?date=YYYY-MM-DD`
- Exact-date sources:
  - local `data/velo_prime_verdicts_YYYY_MM_DD.json`
  - same-day Supabase `velo_verdicts` rows
- Governance overlay:
  - same-day Supabase `velo_verdicts` fields merged by `race_id`
- Metadata hydrator:
  - `src/velo/race_metadata_resolver.py`
- Contract:
  - requested `date` must be served exactly
  - cross-date fallback is forbidden by default
  - if exact-date data is missing, response must fail loud
  - fallback is allowed only with `allow_fallback=true`

### Governed card response truth fields

- `requested_date`
- `loaded_date`
- `source`
- `status`
- `allow_fallback`
- `date_match`
- `stale_data_blocked`
- `governed_card_loaded_date`
- `governed_card_status`
- `sidecar_loaded_date`
- `sidecar_status`
- `sidecar_date_match`
- `metadata_coverage`

### Governed card status rules

- `PASS_EXACT_DATE`
  - exact requested date served
  - no stale substitution
- `FAIL_DATE_MISMATCH`
  - requested date data missing
  - stale fallback refused
  - `stale_data_blocked = true`
- `FALLBACK_USED`
  - only possible when `allow_fallback=true`
  - response must expose requested date, loaded date, and mismatch

### Sidecar lane

- Primary file: `app/static/dashboard/sidecar_stack_latest.json`
- Generator: `scripts/sidecar_stack_operator_card.py`
- Metadata resolver: `src/velo/race_metadata_resolver.py`
- Metadata audit artifact:
  - `data/sidecar_stack_metadata_audit_YYYY_MM_DD.json`

### Sidecar contract

- `sidecar_stack_latest.json` must carry:
  - `date`
  - `status`
  - `metadata_audit.metadata_coverage`
  - `metadata_audit.unresolved_rows`
- sidecar rows must carry:
  - `metadata_source`
  - `metadata_complete`
  - `missing_metadata`
  - `missing_fields`
- no sidecar row may silently show blank metadata without status
- sidecar display is valid only when metadata status is visible

### Current hard truth

- `governed-card` is the main dashboard lane
- `sidecar_stack_latest.json` is the sidecar lane
- both lanes must match the requested date to be considered release-grade
- current May 2 sidecar lane is same-date but metadata-incomplete
- current May 2 governed card lane is same-date after the exact-date patch, but course/off_time remain unresolved for same-day Supabase verdict rows

---

## Change Log

| Date | Change |
|---|---|
| 2026-05-01 | Document created. Section 1: Place Signal Classifier wired. |
| 2026-05-01 | Section 2: CASHRUN Detector wired. Proof run complete. |
| 2026-05-01 | Section 2: Validation status added. Verdict: CASHRUN_NEEDS_MORE_DATA (n=6 READY matched). |
| 2026-05-02 | Section 3: HFS Signal Contract Repair (MPI/chaos_bloom). Root cause confirmed. Patch applied. Backfill dry-run complete. |
| 2026-05-02 | Section 3: HFS Batch 1 Repair mission. Script patched (null-signal targeting). DB password blocker identified. Backup CSV written. Audit confirms 35.3% null rate. |
| 2026-05-01 | Section 4: Daily Learning Loop — Signal Tracker added. velo_signal_tracker.py built. |
| 2026-05-02 | Section 5: HFS Option A — Scale Normalisation complete. 18,575 rows normalised. 11,259 dark rows excluded. Audit: HFS_TRAINING_READY. Playbook G training initiated. |
| 2026-05-02 | Section 6: Sentient State Cleanup. Contaminated training state rolled back. Supabase PATCH 200. Both layers clean. STEP 7 gated. SENTIENT_RESTORE_PATH_CLEAN. |

---

## Section 4 — Daily Learning Loop: Signal Tracker

### Purpose

Closes the daily learning loop by matching closed results against sidecar signal classes
and tracking whether each proven signal is performing at or below its audit baseline SR.

**Loop:** scoring → verdict → result → sigma → signal_tracker → doctrine update → next scoring

### Status

```
OPERATOR_VISIBILITY_ONLY
NO staking. NO betting instruction. NO scoring change. NO model change.
NO router change. NO SQPE change. NO live execution.
Read-only from velo_post_race_reviews + sidecar stack local files.
```

### File

| File | Role |
|---|---|
| `scripts/velo_signal_tracker.py` | Daily tracker — reads sigma reviews, computes per-stack stats, appends ledger |

### Entry Point

```bash
python scripts/velo_signal_tracker.py --date YYYY-MM-DD
```

### Inputs

| Source | Fields used |
|---|---|
| `velo_post_race_reviews` (Supabase) | `race_id`, `horse`, `outcome`, `velo_prime_prob`, `market_deception_score`, `improvement_score`, `place_prob`, `decision_tier`, `sigma_hit`, `sigma_frame` |
| `data/sidecar_stack_operator_card_YYYY_MM_DD.json` | Stack counts for context (not required) |

### Signal Classes Tracked

| Stack Label | Condition | Baseline SR | Alert threshold |
|---|---|---:|---|
| `MDS_HIGH` | MDS > 0.50 | 54.8% | SR < 30% at n ≥ 10 |
| `IMP_HIGH` | IMP > 0.40 | 43.5% | SR < 25% at n ≥ 10 |
| `VP30_TIER_A` | VP ≥ 0.30 + Tier A | 40.1% | SR < 20% at n ≥ 10 |
| `ELITE_STACK` | Tier A + VP30 + MDS_HIGH | 40.1% | SR < 15% at n ≥ 8 |
| `STRONG_STACK` | VP30 + MDS_HIGH | 54.8% | SR < 20% at n ≥ 8 |
| `VP30_IMPROVE` | VP30 + IMP_HIGH | 43.5% | SR < 20% at n ≥ 8 |
| `VP30_BASE` | VP30 only | 32.2% | SR < 15% at n ≥ 15 |

### Outputs

| File | Format |
|---|---|
| `data/velo_signal_tracker_{date}.md` | Markdown report per day |
| `data/velo_signal_tracker_ledger.csv` | Append-only rolling ledger |

### Ledger Format

```csv
date,stack_label,n_fired,n_won,n_placed,sr,frame_rate,alert_flag
2026-05-02,MDS_HIGH,2,1,2,0.5000,1.0000,
2026-05-02,VP30_TIER_A,8,3,6,0.3750,0.7500,
```

`alert_flag` = `ALERT` if diverging from baseline at threshold; blank if OK.

### How Tracker Feeds Operator Decisions

1. **Daily** — run after sigma close. Append one day of signal class outcomes to the ledger.
2. **Rolling window** — when any class reaches n≥10 (n≥8 for stack-specific), alert threshold fires.
3. **DIVERGENCE ALERT** — operator reviews the signal class:
   - Is sample size too small for verdict? (likely at n<20)
   - Is there a systematic miss pattern? (race type, SP band, going?)
   - Does this warrant a doctrine note?
4. **No automatic model change** — tracker informs, operator decides.
5. **Promotion gates unchanged** — tracker output feeds the operator review process, not any code gate.

### Harness Integration

Wired as final step of `velo_daily_harness.py --mode close`:

```
[STEP 6/6] velo_signal_tracker --date YYYY-MM-DD
```

### Safety Contract

```
NO change to velo_prime_prob
NO change to SQPE or ensemble
NO change to decision_tier
NO change to router or router shadow lanes
NO staking
NO Betfair integration
NO live execution
READ-ONLY from velo_post_race_reviews (Supabase) + local sidecar JSON
```

### Known Limitations

- `velo_post_race_reviews` win detection uses `sigma_hit` and `outcome` field.
  If outcome field is not populated, classification falls back to keyword matching.
- Signal tracker is daily-granular — no intra-day tracking.
- n=0 on any day (no results yet) produces all-zero stats — expected until sigma runs.

---

## Section 5 — HFS Scale Normalisation: Option A + Playbook G Training

### Status

```
HFS_TRAINING_READY — confirmed 2026-05-02 16:57 UTC
Playbook G training: INITIATED
```

### What Happened

The HFS had a three-tier scale problem:
- **Pre-2026 (18,575 rows):** mpi in 0–100 legacy scale, chaos_bloom in 37–97 legacy scale
- **2026 repaired (2,102 rows):** mpi/chaos_bloom in 0–1 (hfs_signal_contract_v1)
- **2026 dark (11,259 rows):** NULL mpi/chaos_bloom — no prediction source

This was incompatible for training. Any mixed-era model would have seen 100× scale mismatch.

### Option A — Applied 2026-05-02

Script: `scripts/normalise_hfs_legacy_scale.py`
Backup: `data/hfs_normalise_backup_pre_apply.csv`

| Action | Rows | Method |
|---|---|---|
| mpi ÷100, chaos_bloom ÷100 | 18,575 | PATCH per-row via aiohttp async (20 concurrent) |
| Stragglers second pass | 633 | Same — rate-limited on first pass |
| chaos_bloom stragglers | 17 | Same |
| reconstruction_version = EXCLUDED_DATA_DARK | 11,259 | PATCH per-row |

### Post-Normalisation Audit Result

```
Total HFS rows:                    31,936
Active rows (used for audit):      20,677
Excluded rows (EXCLUDED_DATA_DARK):11,259

MPI Signal
  Null count:     0  (0.0%)
  min: 0.0008  max: 1.0  mean: 0.3954  std: 0.3066

Chaos Bloom Signal
  Null count:     0  (0.0%)
  min: 0.30    max: 0.97  mean: 0.618   std: 0.1298

CLASSIFICATION: HFS_TRAINING_READY
No blocking conditions detected.
```

### Scale Contract (permanent)

| Signal | Scale | Source |
|---|---|---|
| mpi | **0.0 – 1.0** | `hfs_signal_contract_v1` formula or legacy ÷100 |
| chaos_bloom | **0.0 – 1.0** | same |

**All future mpi/chaos_bloom values MUST be 0–1. No 0–100 values permitted in HFS.**

The audit script (`audit_hfs_signal_integrity.py`) now excludes EXCLUDED_DATA_DARK rows from null% classification — these 11,259 rows are permanently non-contributing.

### Playbook G Threshold Update

Playbook G (`app/playbooks/playbook_g_sentient_loopback.py`) thresholds updated from 0-100 to 0-1 scale:

| Check | Old threshold | New threshold |
|---|---|---|
| BEC: market_lies_detected | mpi > 70 | mpi > 0.70 |
| BEC: safe_bets_imploded | chaos_bloom < 30 | chaos_bloom < 0.30 |
| REE: pain_rules trigger | mpi > 70 | mpi > 0.70 |
| Kingmaker: chaos_navigator | chaos_bloom > 40 | chaos_bloom > 0.40 |

### Playbook G Training

Script: `scripts/run_playbook_g_training.py`
Input: 20,677 active HFS rows grouped by race_id
Construction method:
- `power_anchor` = horse_id with highest mpi in race (predicted winner)
- `story_anchor` = horse_id with lowest sp_dec (favourite)
- `mpi` = race-level signal (max mpi of race)
- `chaos_bloom` = max chaos_bloom of race
- `narrative_disruption` = derived from chaos_bloom (chaos_bloom × 100 for emotion engine)
- `actual_result.winner` = horse_id where winner_flag=True

State output: `data/sentient_state.json`
Cloud backup: `learned_patterns` table, row `SENTIENT_STATE_BACKUP`

### Training Result — 2026-05-02

```
Races trained:         2,997
Power anchor SR:       0.592  (1,774/2,997)
Favourite win rate:    0.590  (1,769/2,997)
Training time:         520s
Total races observed:  4,643 (was 1,646)

Appetite state:
  aggression_level:              0.6500
  pattern_recognition_sensitivity: 1.0000
  doctrine_firing_threshold:     0.1400
  directive_firing_threshold:    0.1400   ← read by Playbook F
  narrative_skepticism:          1.0000
  chaos_tolerance:               0.0000
  manipulation_sensitivity:      1.0000

Top doctrine strengths (by EMA score):
  SHADOW_TRACKING:  0.2300  — confirmed active pattern
  ENGINE_SUPREMACY: 0.2300  — confirmed active pattern
  CHAOS_BLEED:      0.2140  — confirmed active pattern
  VETP_ECHO:        0.1610
  [rest decayed to ~0 — insufficient evidence in training data]

Behaviour Echo Chamber:
  market_lies_detected:  1,260  (mpi>0.70, fav lost)
  safe_bets_imploded:    1,041  (chaos<0.30, fav lost)
  favourites_protected:  1,905
  favourites_abandoned:  2,738  (59.1% — matches evidence layer 55-60% non-fav zone)

Emotion laws: 50 pain + 50 triumph + 50 anger (all capped at 50 per category)
```

**Interpretation:** The engine has trained on 8+ years of race data. Doctrines SHADOW_TRACKING, ENGINE_SUPREMACY, and CHAOS_BLEED show the strongest learned signal — consistent with the VP≥0.30 + MDS evidence from the 49-day unified audit. directive_firing_threshold dropped from 0.60 → 0.14 on a profitable run — Playbook F will fire more aggressively. chaos_tolerance collapsed to 0.0 — engine learned chaos regimes are unpredictable. manipulation_sensitivity at 1.0 — maximum alertness to market deception signals.

### Safety

```
NO scoring change
NO SQPE change
NO VP change
NO router change
NO staking
NO live execution
Training output is sentient_state.json only — read by Playbook F appetite threshold
```

---

## Section 6 — Sentient State Cleanup: 2026-05-02

### Status

```
SENTIENT_RESTORE_PATH_CLEAN
LIVE_CONTROL_STILL_BLOCKED
AUDIT_ONLY
```

### What Happened

Playbook G training (`run_playbook_g_training.py`) ran against 2,997 HFS races and overwrote `sentient_state.json` with a contaminated state:

```
directive_firing_threshold: 0.14  (was 1.0)
aggression_level:           0.65  (was 0.3)
total_races_observed:       4,643 (was 1,646)
```

Additionally, `run_results_sigma.py` STEP 7 was found to contain fabricated proxy inputs (`mpi = 80 if sp > 10 else ...`, `chaos_bloom = 40`, `narrative_disruption = 45`) with no idempotency and wrong `favourite_won` semantics.

### Cleanup Actions

| Action | Result |
|---|---|
| `sentient_state.json` rolled back to Apr 25 backup | Clean |
| Supabase `SENTIENT_STATE_BACKUP` PATCH | Status 200 — confirmed |
| `run_results_sigma.py` STEP 7 gated behind `VELO_G_FEED_ENABLED` | Disabled |
| Contaminated training artifact preserved | `data/sentient_state_training_artifact_20260502.json` |

### Verified Clean State (both layers)

```
total_races_observed:        1,646
directive_firing_threshold:  1.0
aggression_level:            0.3
last_observed:               2026-04-25T13:52:14.756912
Supabase updated_at:         2026-05-02T19:55:26.059253
```

### Restore Path Safety

- Local `data/sentient_state.json` → clean
- Supabase `SENTIENT_STATE_BACKUP` → clean (PATCH 200 verified)
- If Railway restarts → `_restore_from_supabase()` loads clean state
- Contaminated artifact at `data/sentient_state_training_artifact_20260502.json` — not read by any live path

### Sigma STEP 7 — Permanently Gated

```python
# run_results_sigma.py STEP 7
# DISABLED — gate: VELO_G_FEED_ENABLED (default OFF)
# Reason: fabricated mpi/chaos_bloom/narrative_disruption proxies,
# no idempotency, no event ledger, wrong favourite_won semantics,
# overwrites live sentient state.
```

To re-enable: idempotency + outcome event ledger + shadow mode must be built first.
See required schema in Section 5 (Sentient Loop Patch Safety Audit).

### Safety

```
NO training
NO sigma feed
NO Playbook G called
NO model changes
NO scoring changes
NO router changes
NO staking
NO Telegram
NO live execution
Contamination repair only
```

## Section 7: VÉLØ Lane Control Policy

Defined in `src/velo/weight_policy_registry.py`. Controls scoring logic across environments.

| Lane | Status | Description |
| :--- | :--- | :--- |
| **LIVE_BASELINE_CURRENT** | LIVE_CURRENT | Current runtime weights. Value anchor: SQPE. |
| **SHADOW_SAFE_V2** | SHADOW_ONLY | Candidate policy. SQPE 0.80, reduced Improvement risk. |
| **SHADOW_FULL_STACK_V1** | SHADOW_RESEARCH | Testing Racing API + CASHRUN lift. Not for live use. |
| **PAPER_EXECUTION_POLICY** | PAPER_ONLY | No VP weights. Reads bridge directives only. |

**Promotion Rule:** No lane promoted to LIVE without 30 days of shadow evidence showing ROI lift > 5%.

## Section 8: Playbook G / Sentient Feed Status

- **Loop Status:** Restored (Patched `run_results_sigma.py`).
- **Feed Control:** Gated **OFF** by default via `VELO_G_FEED_ENABLED`.
- **Expert Promotion:** **BLOCKED**. No Expert/Sentient promotion until sandbox proof.
- **Safety Requirement:** Idempotency audit + event ledger verified. No double-feeding permitted.
- **Current Classification:** **SENTIENT_FEED_READY_FOR_SANDBOX**.

## Section 9: Live Sidecar Reduction — Release/Comment Disabled

Following the live_sidecar_ablation_audit (2026-05-02), the following components have been removed from the weighted Meta-Ensemble to protect ROI and prevent over-bet bias.

- **release_day_prob / release_window_score**: STORED_ONLY, not live weighted (Weight 0.00).
- **comment_intel_score**: STORED_ONLY, not live weighted (Weight 0.00).
- **VP/SQPE**: Live core anchor (Weight 0.45).
- **MDS**: Live sidecar retained (Weight 0.10).
- **Place Prob**: Live sidecar retained (Weight 0.08).
- **Improvement Score**: Live sidecar retained (Weight 0.12).
- **Longshot Score**: Live sidecar retained, gated SP >= 10.0 (Weight 0.07).
- **Racing API enrichment**: Shadow only (Weight 0.00).
- **CASHRUN**: Not live weighted.
- **POWER_ANCHOR**: Paper only.

**Reasoning:** Audit flagged harmful ROI profile for Release and Comment intel components. Fields remain logged for forensic observability but no longer influence the final Velo Prime probability.

## Section 11: Sidecar Safety Patch v1 — Calibration Research Only

A structured impact audit was conducted on 2026-05-02 comparing the current live ensemble against two safety patch designs (A and B) using the 2026-05-01 race corpus.

- **Design A (Renormalized)**: Removed harmful weights from the denominator.
  - **Verdict**: REJECTED.
  - **Reason**: Caused aggressive inflation of raw probabilities (+0.04 Avg VP), creating false confidence and expanding the VP30 list by +3 runners without evidence of selection improvement.
- **Design B (Fixed Denominator)**: Set harmful weights to 0 but kept the original denominator (dampening mode).
  - **Verdict**: CALIBRATION_RESEARCH_CANDIDATE.
  - **Reason**: Produced identical top selections and normalized rankings as Design A but with dampened raw probabilities. Held for future calibration research only.
- **Production Status**: UNCHANGED. `LIVE_BASELINE_CURRENT` remains active. No live weight change approved. Sidecar ROI risk remains open.

**Next Required Step**: Larger multi-day ablation audit required to prove ROI lift before any live weight migration.

## Section 12: Race-Day Identity Rule

This section defines the mandatory protocol for identifying and querying race-day data to prevent date-resolution incidents.

- **Truth Source:** Every operator card and race-day audit must identify the target races by a **race_id manifest** derived from local standard/merged racecards for that date.
- **Join Key:** `race_id` is the canonical join key between racecards, verdicts, results, and audits.
- **Retrieval:** Verdicts must be fetched from Supabase using the manifest list (`IN (race_id_list)`), not by `generated_at` timestamp.
- **Provenance:** `generated_at` is for provenance/audit tracking only and must never be used as the primary day selector.
- **Metadata:** All race metadata (Course, Time) must be resolved by `RaceMetadataResolver` using the `race_id`.
- **IDs:** Runner-specific IDs (trainer, jockey) must be extracted from `full_analysis.predictions` blocks.
- **Fail Fast:** If no race-day manifest (local JSON) exists, the process must fail clearly with `FAIL_NO_RACE_ID_MANIFEST` rather than attempting a `generated_at` search.


## Section 13: Worktree / Nexus Rule

This section defines the mandatory protocol for multi-repo environment stability.

- **Canonical Target:** Repo A (`/mnt/c/Users/puror/velo-oracle-prime`) is the only authorized environment for scoring, development, and commits.
- **Reference Only:** Repo B (`velo_feature_v10_launch_fix`) is quarantined and serves as a read-only source for historical migration.
- **Migration Protocol:** No code merge. Deliberate file migration only. Migrated files must be listed in `VELO_NEXUS_WORKTREE_REGISTRY.md`.
- **Zero-Tolerance:** No agent may execute scripts from sibling worktrees.

## Section 14: Security and Credential Spine

This section defines the release-gate security contract for the live VELØ control plane.

### Secrets

- Secrets must live in environment variables only.
- Secrets must not live in tracked repo files.
- Secrets must not live in docs.
- Secrets must not live in generated artifacts under `data/`.
- Placeholder templates are allowed only when they contain no real values.

### Current source files

- API ingress hardening lives in `app/main.py`.
- Runtime config contract lives in `app/core/config.py`.
- Racing API env-only clients live in:
  - `app/integrations/racing_api_client.py`
  - `app/api/racing_api_client.py`
  - `workers/racing_api_fetcher.py`
- Rotation and incident procedure lives in:
  - `docs/security/VELO_SECRET_ROTATION_RUNBOOK.md`
- Environment ownership contract lives in:
  - `docs/security/VELO_ENV_CONTRACT.md`

### Security controls now enforced

- Trigger endpoints use constant-time secret comparison.
- `target_date` validation is enforced before subprocess, log, or Supabase use.
- Live Betfair remains blocked unless explicitly approved and separately guarded.
- Security work is a release gate, not optional cleanup.

### Current audit truth

- Current HEAD is env-only for Racing API secrets.
- Historical exposure is confirmed by commit `53ec195` replacing hardcoded credentials with env references.
- Immediate credential rotation is therefore required.
- History rewrite is recommended later, but rotation is the first required action.

### Operational law

- No dashboard, scoring, sigma, or operator workflow is release-grade if secret hygiene is not controlled.
- No engineer or agent may paste credentials into chat logs, markdown reports, or screenshots.

---

## Section 10 — Live Sidecar Risk Register

### Status

```
SIDE_CAR_RISK_CONTROL_ACTIVE
HARMFUL_COMPONENTS_REMOVED (2026-05-02)
```

### Risk Mitigation Audit (2026-05-02)

Following the `live_sidecar_ablation_audit`, the following components have been removed from the live weighted Meta-Ensemble to protect ROI and prevent over-bet bias.

| Component | Status | Weight | Reason |
|---|---|---|---|
| `release_day_prob` | REMOVED | 0.00 | Harmful ROI profile; over-bet bias |
| `release_window_score`| REMOVED | 0.00 | Harmful ROI profile |
| `comment_intel_score` | REMOVED | 0.00 | Signal-to-noise ratio too low |

### Live Weights (Baseline)

| Component | Weight | Role |
|---|---|---|
| VP / SQPE | 0.45 | Core probability anchor |
| MDS | 0.10 | Market deception sidecar |
| Place Prob | 0.08 | Place support sidecar |
| Improvement Score | 0.12 | Potential sidecar |
| Longshot Score | 0.07 | Gated SP >= 10.0 |

---

## Section 11 — LLM Council Status

### Status

```
SHADOW_OPERATOR_GOVERNANCE
NO_LIVE_CONTROL
EVIDENCE_GATED
```

### Governance Policy

The VÉLØ LLM Council is the final reasoning layer that synthesizes evidence for operator visibility.

1. **Read-Only:** Council reads evidence; it does not create truth.
2. **No Promotion:** Council cannot promote signals or lanes.
3. **No Control:** Council cannot alter VP, weights, router, staking, or execution.
4. **Evidence Gated:** Council is invalid if the Evidence Packet is incomplete (VP30 or Racing API missing).
5. **Hierarchy:** Council is below One Truth, Signal Board, Router Audit, and Daily Close SOP.
6. **Output:** SHADOW / OPERATOR ONLY.

### Required Evidence Spine

- VP30 Card
- Racing API Enrichment
- CASHRUN Detector
- Sidecar Ablation Audit
- Signal Promotion Board
- Router Shadow Audit
- One Truth (Wiring Map)

---

## Section 12 — CASHRUN Detector

### Status

```
SHADOW_OPERATOR_ONLY
DEV_LOCKED
NOT_PROVEN
FORWARD_TEST_REQUIRED
```

### Governance Policy

The CASHRUN detector identifies possible handicap/cash-run intent from Racing Post and merged racecard data.

1. **Read-Only:** Detector provides intelligence only; it does not change live scoring.
2. **Inputs:** Spotlight, Postdata, current OR, last-six OR, last-six TS, last-six RPR, trainer, jockey, class, trip, going.
3. **Rules Locked:** Scoring logic and thresholds are locked (CASHRUN_V1_DEV_LOCK).
4. **No Control:** Cannot alter VP, weights, router, staking, or execution.
5. **Evidence Status:** Forward-test required.
6. **Data Warning:** 2026-05-01 run is flagged as TUNED_ON_SAME_DAY_DATA; performance is DEV_ONLY_NOT_EVIDENCE.
7. **Audit Rule:** Performance must be reported using identity-grade matches only. Global fallback matches are diagnostic only, not proof.
8. **RPR History:** Currently missing until RPR-specific PDF source is added.

### Process Pipeline

Racing Post PDFs
→ PDF ingestion / merged JSON
→ `cashrun_detector.py`
→ `cashrun_report_YYYY_MM_DD.md/csv`
→ Operator Card
→ Future evidence audit (identity-grade join only)
→ **NO LIVE SCORE IMPACT**

### Thresholds

- **CASHRUN_READY:** 75–100
- **CASHRUN_WATCH:** 55–74
- **WEAK_SIGNAL:** 35–54
- **SUPPRESS:** 0–34

---

## Section 13 — Race Day Bootstrap — Mandatory Order

### Process Order

1. **Environment preflight:** Validate dependencies (`loguru`, `.env`, keys).
2. **Racecard fetch:** Retrieve daily Racing API standard cards.
3. **RP/PDF ingestion:** Parse locally supplied Racing Post PDFs.
4. **Merged racecard creation:** Combine Racing API and Racing Post intel.
5. **Scoring:** Run VÉLØ Prime (dry-run) to generate predictions and verdicts.
6. **VP30 card:** Hydrate the candidate gate and metadata.
7. **Racing API enrichment card:** Append operator metadata (shadow).
8. **CASHRUN card:** Score handicap plots and trainer intent.
9. **Result close later:** Process results.

### Hard Rules

- No operator card may run before verdicts exist.
- No CASHRUN may run before Racing Post fields exist.
- No VP30 card may pass without metadata and candidate gate.
- No script should be run manually out of order if the bootstrap command (`scripts/velo_day_bootstrap.py`) exists.

---

## Safe Ensemble Candidate Review

**Date:** 2026-05-07  
**Simulation script:** `scripts/simulate_safe_ensemble_variants.py`  
**Evidence corpus:** `data/velo_unified_evidence_corpus_v1.csv` (794 rows, 721 with won+SP)  
**Sample:** 321 top-selections at VP≥0.25  

### Current Live Blend Status

| Metric | Value |
|---|---|
| SR | 26.48% |
| Frame rate | 64.49% |
| ROI | **-24.38%** |
| Avg SP | 6.06 |
| V0 baseline selections | 321 |

The live blend is economically negative. SQPE is the only confirmed value-positive anchor. Several sidecars add SR/frame signal but degrade ROI by pulling the system toward overpriced/short-SP selections.

### Harmful Sidecar Findings

| Sidecar | Audit finding | ROI impact (ablation) |
|---|---|---|
| release_day_prob | Harmful (combined effect) | Worsens ROI when removed alone (-1.35pp) |
| comment_intel_score | Harmful (combined effect) | Worsens ROI when removed alone (-1.35pp) |
| place_prob | Overbet-risk | Marginal improvement when removed (+1.15pp) — FRAME_ONLY |
| improvement_score | Overbet-risk | Worsens ROI when removed alone (-2.22pp) |
| market_deception_score | Strong signal | Significant hurt when removed (-5.45pp) — KEEP |
| longshot_prob | Overbet-risk | Minor hurt when removed (-1.69pp) |

**Key finding:** Individual ablations show small effects because the other harmful sidecars remain. The collective removal of non-MDS sidecars (V3, V5) delivers the improvement.

### Simulated Candidate Blends

| Variant | SR% | ROI% | ROI Δ vs V0 | Changed | W+ | W- |
|---|---|---|---|---|---|---|
| V0_CURRENT_LIVE | 26.48 | -24.38 | — | — | — | — |
| V1_SQPE_ONLY | 17.13 | -12.28 | +12.10pp | 354 | 25 | 55 |
| V2_SQPE_MDS_PLACE | 26.48 | -29.02 | -4.64pp | 232 | 24 | 24 |
| **V3_SQPE_MDS_ONLY** | **27.10** | **-7.79** | **+16.59pp** | 262 | 24 | 22 |
| V4_REMOVE_HARMFUL | 25.55 | -29.95 | -5.57pp | 228 | 23 | 26 |
| **V5_VALUE_DISCIPLINE** | **26.17** | **-8.34** | **+16.04pp** | 260 | 22 | 23 |

### Direct Question Answers

1. **Does removing release_day_prob improve ROI?** No — removing it alone worsens ROI (-1.35pp). It has no standalone positive effect. Collective removal with other non-MDS sidecars is needed.
2. **Does removing comment_intel_score improve ROI?** No — same as above (-1.35pp alone). Collective removal required.
3. **Does removing improvement_score reduce SR but improve ROI?** No — removing it worsens ROI (-2.22pp). Its SR/frame contribution is real. The issue is the full blend overweights confidence sidecars collectively.
4. **Does MDS deserve to stay live?** Yes — removing MDS costs -5.45pp ROI. Confirmed value-additive.
5. **Does place_prob deserve live or frame-only?** Frame-only. Removing it marginally improves ROI (+1.15pp) — it inflates confidence on placeable-but-not-winning horses.
6. **Is SQPE-only better economically than current?** Yes — SQPE-only ROI=-12.28% vs current -24.38% (+12.10pp). However, SR drops from 26.48% to 17.13% (lost 55 winners to gain 25). Not a clean trade.
7. **Safest candidate blend:** V3_SQPE_MDS_ONLY (ROI=-7.79%, SR=27.1%, +16.59pp vs current).

### Recommended Action

| Decision | Status |
|---|---|
| KEEP_CURRENT_LIVE | Yes — no production change yet |
| CREATE_SHADOW_SAFE_BLEND | Pending — V3_SQPE_MDS_ONLY is the candidate |
| FREEZE_RELEASE_COMMENT_FOR_REVIEW | Yes — confirmed collectively harmful |
| PAPER_COMPARE_SAFE_BLEND | Next step — shadow-run V3 alongside current |
| DO_NOT_CHANGE | Overridden only when shadow comparison evidence clears |

**No production weight change unless explicitly approved after shadow comparison.**  
Prove the safer blend first. If V3_SQPE_MDS_ONLY beats current on ROI/drawdown in forward shadow without killing strike/frame → create SHADOW_SAFE_BLEND gate.

### Operating Rules (Permanent)

```
NO production weight change without shadow evidence gate passed
NO SQPE change
NO model retraining
NO router promotion
NO staking
V3_SQPE_MDS_ONLY is the candidate blend for shadow comparison
MDS stays live — confirmed value-positive
place_prob moves to frame-annotation only if V3 shadow confirms
```

---

## SHADOW_SAFE_BLEND V3 — SQPE 70 / MDS 30

**Status:** SHADOW_ONLY  
**Version:** v1_sqpe70_mds30  
**Created:** 2026-05-07  
**Source:** `src/velo/shadow_safe_blend.py`  
**Ledger:** `data/safe_blend_v3_shadow_ledger.csv`  
**Audit:** `scripts/safe_blend_v3_forward_audit.py`  

### Formula

```
safe_blend_v3_score = 0.70 * sqpe_v17_prob + 0.30 * market_deception_score
```

### What it does

- Scores every race's runners using V3 formula after live scoring completes
- Logs top V3 pick per race to the forward shadow ledger
- Records whether V3 changed the top selection vs the live pick
- Result columns (sp, won, placed, P&L) filled by sigma close

### What it does NOT do

- Does NOT modify live velo_prime_prob
- Does NOT affect candidate_execution_allowed
- Does NOT affect router decisions
- Does NOT trigger staking
- Does NOT send Telegram betting alerts
- Does NOT affect live execution in any way
- Zero production scoring side effect — SHADOW_ONLY at all times

### Evidence basis (historical simulation, 2026-05-07)

| Metric | V0 Current | V3 SQPE+MDS | Delta |
|---|---|---|---|
| n | 321 | 321 | — |
| SR | 26.48% | 27.10% | +0.62pp |
| ROI | -24.38% | -7.79% | **+16.59pp** |

### Forward gate

| Condition | Gate |
|---|---|
| n < 30 | OBSERVE_ONLY |
| n ≥ 30, V3 ROI > live ROI, V3 SR ≥ 24% | SHADOW_SAFE_BLEND_CONFIRMED |
| n ≥ 60, still better | LIVE_WEIGHT_REVIEW_CANDIDATE |
| n ≥ 100 | Formal co-founder discussion only |
| Automatic promotion | NEVER |

### Hard rules

```
NO production weight change until gate SHADOW_SAFE_BLEND_CONFIRMED
NO SQPE change
NO model retraining
NO router promotion
NO staking
NO Telegram betting alert
Automatic promotion: NEVER
Gate advancement: operator decision only at each threshold
```
