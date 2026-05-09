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

## Section 14 — Sentient Daily Learning Loop: Current Truth (2026-05-08)

### Status

| Layer | Status |
|---|---|
| Manual repair path | **WORKING** — 924/925 observe calls succeeded |
| Normal EOD bridge (pre-patch) | **WAS BROKEN** — patched 2026-05-08 |
| Normal EOD bridge (post-patch) | **WORKING** — audit classification READY_FOR_7_DAY_SHADOW |
| Shadow daily accumulation | **ALLOWED** — bridge audit passes all criteria |
| Live promotion | **BLOCKED** — HFS_TRAINING_SAFE=False + 7–14 day accumulation required |

### What Forensic Audit Proved

The manual repair script (`scripts/sentient_loop_repair_v1.py`) demonstrated that the loop **can** learn. The normal daily bridge (`scripts/eod_shadow_learning_bridge.py`) had four confirmed bugs that prevented real learning:

1. **MPI formula wrong**: was `vp * 100`. Fixed: `(vp*0.6 + mds*0.4)*100` matching ensemble formula.
2. **SP hardcoded**: was always `5.0`. Fixed: extracted from `results_YYYY_MM_DD.json` runners `sp_dec`.
3. **learning_allowed always False**: Fixed: `True` when outcome closed, race_id and winner_id present.
4. **chaos_bloom None → TypeError**: Fixed: derived from `macro_chaos_mode + favourite_trap_risk`, or `0.0` with provenance `defaulted_missing_macro`.

### Bridge Patch Verification (2026-05-07)

| Criterion | Value | Pass |
|---|---|---|
| Events scanned | 41 | — |
| observe_race_outcome attempted | 41 | — |
| observe_race_outcome success | 41 (100%) | ✓ |
| MPI null | 0 | ✓ |
| MPI mean | 20.92 | — |
| chaos_bloom null | 0 | ✓ |
| SP hardcoded | 0 | ✓ |
| Duplicate keys | 0 | ✓ |
| Live state untouched | True | ✓ |
| State Δ races | +41 | ✓ |
| DAILY_CLOSE_READY | True | ✓ |
| LIVE_PROMOTION_READY | False | — |

### Shadow State Files

| File | Purpose | Races |
|---|---|---|
| `data/sentient_state.json` | **Live state** — frozen at 1646 since 2026-04-25 | 1,646 |
| `data/sentient_state_shadow_repair_v1.json` | Manual repair baseline | 930 |
| `data/sentient_state_shadow_daily.json` | **Daily bridge target** — accumulates from today | Growing |
| `data/sentient_state_training_artifact_20260502.json` | Training run artifact — NOT promoted | 4,643 |

### Scripts

| Script | Purpose | Status |
|---|---|---|
| `scripts/eod_shadow_learning_bridge.py` | **Daily bridge** — run after results close | Patched v2 |
| `scripts/audit_sentient_daily_bridge.py` | Bridge regression audit — run after bridge | New |
| `scripts/sentient_loop_repair_v1.py` | Manual repair (one-time) | Complete |
| `scripts/sentient_loop_forensic_audit.py` | Daily loop verification | Active |
| `scripts/sentient_loop_post_repair_audit.py` | Post-repair A-R analysis | Active |

### Daily Accumulation Sequence (after results close)

```
1. scripts/run_results_sigma.py --date YYYY-MM-DD
2. scripts/eod_shadow_learning_bridge.py --date YYYY-MM-DD
3. scripts/audit_sentient_daily_bridge.py --date YYYY-MM-DD
4. scripts/sentient_loop_forensic_audit.py
```

### SENTIENT SHADOW DAILY CLOSE — 7-DAY WINDOW

**Every evening after results close:**

```bash
source venv/bin/activate

# Step 1 — run shadow learning bridge
PYTHONPATH=. python scripts/eod_shadow_learning_bridge.py --date YYYY-MM-DD

# Step 2 — run audit (both steps are mandatory — a day without audit does not count)
PYTHONPATH=. python scripts/audit_sentient_daily_bridge.py --date YYYY-MM-DD
```

**Pass criteria (all must be true for day to count):**

| Criterion | Threshold |
|---|---|
| observe count | > 0 |
| null outcome count | = 0 |
| MPI null count | = 0 |
| chaos_bloom null count | = 0 |
| shadow state written to | shadow file only (`sentient_state_shadow_daily.json`) |
| live sentient_state.json hash | UNCHANGED |
| no scoring changes | confirmed |
| no live control | confirmed |
| no promotion | confirmed |

**Fail criteria (any triggers immediate STOP):**

| Trigger | Action |
|---|---|
| live sentient_state.json hash changes | IMMEDIATE HALT |
| null outcomes in bridge output | STOP — debug before next run |
| observe count = 0 when results exist | STOP — check results file for date |
| bridge writes to live scoring path | CRITICAL — halt all bridge ops |
| scoring/model/router mutation | CRITICAL — halt and investigate |

**Classification output:**

```
SENTIENT_DAILY_BRIDGE_READY_FOR_7_DAY_SHADOW   → day counts
REPAIR_INCOMPLETE                               → STOP, fix before next run
BLOCKED                                         → STOP, read block reason in audit output
```

**Window status:** `SHADOW_SENTIENT_LEARNING_LOOP_READY / NOT_LIVE_CONTROL`

### Promotion Gates (unchanged — permanent hard rules)

- `HFS_TRAINING_SAFE=False` — must pass HFS signal integrity audit before any change
- 7–14 consecutive days of DAILY_CLOSE_READY=True in shadow
- Operator sign-off required — no automatic promotion at any threshold
- Live sentient_state.json must never be modified by any script

### Hard Rules

- No live sentient_state.json write from any script without explicit operator command.
- No live promotion until all gates pass.
- No scoring change from shadow learning.
- Shadow-only until explicitly unlocked.

---

## Section 15 — ACCA_LANE_V1: Shadow Chain Quality Lane

### Company line

```text
Racing API  = structure
Racing Post = intent
VP          = probability
MDS         = market deception
CASHRUN     = handicap plot detection
ACCA_LANE   = chain quality / leg compatibility
```

### Status

```text
SHADOW_OPERATOR_ONLY
BUILT_FOR_SHADOW_USE
NO_LIVE_SCORING_CHANGE
NO_STAKING
NO_ROUTER_CHANGE
NO_BETFAIR
FORWARD_TEST_REQUIRED
```

### Purpose

The acca lane should identify whether a race day naturally supports realistic doubles, trebles, and longer fold chains.

This lane must not think like a single-runner scorer.
It must think in:

1. leg quality
2. combo quality
3. day regime

### Day regimes

- `ACCA_DAY_STRONG`
- `ACCA_DAY_PLAYABLE`
- `ACCA_DAY_THIN`
- `NO_ACCA_DAY`

### Leg roles

- `BANKER`
- `GLUE`
- `BOOSTER`
- `WILDCARD`
- `TRAP`
- `BLOCKED`

### Inputs

- same-day `velo_verdicts`
- VP30 / tier / place support
- MDS and blocker labels
- CASHRUN class and confidence when present
- industry selections parsed from Racing Post
- Racing API enrichment as shadow-only context
- race structure fields: course, off_time, field size, handicap state

### Files

| File | Role |
|---|---|
| `scripts/acca_detector.py` | Detects candidate acca legs, assigns roles, classifies day, builds fold ladders |
| `scripts/acca_results_audit.py` | Replays historical dates and measures fold hit-rate / ROI by chain type |
| `docs/engineering/VELO_ACCA_LANE_PROTOCOL_V1.md` | Lane contract |
| `docs/engineering/VELO_ACCA_LANE_PROPOSAL_V1.md` | Proposal and design brief |

### Outputs

| File | Format |
|---|---|
| `data/acca_lane_report_YYYY_MM_DD.md` | Full operator report |
| `data/acca_lane_report_YYYY_MM_DD.json` | Structured machine-readable report |
| `data/acca_lane_report_YYYY_MM_DD.csv` | Candidate-leg and fold table |
| `data/acca_operator_card_YYYY_MM_DD.md` | Compact operator card |

### Safety contract

```text
NO change to velo_prime_prob
NO change to SQPE or ensemble
NO change to decision_tier
NO change to router
NO staking
NO Betfair
NO live execution
NO Telegram betting language
READ-ONLY from same-day verdicts, CASHRUN output, and external selection context
```

### Promotion rule

The acca lane is judged only by replay and forward-test results.
It is blocked from live promotion and does not affect VP, router, staking, or execution.

Promotion gate:

- `n < 20 replay days` -> `SHADOW ONLY`
- `n >= 20 replay days` -> calibration review only
- `n >= 50 replay days` -> possible operator-trust review
- live betting promotion -> forbidden

Current replay verdict:

- `SHADOW ONLY`
- VP30 core required
- Racing API enrichment helps
- `BANKER_ONLY` is the cleanest replay shape
- `BANKER_PLUS_GLUE_ONLY` is the next cleanest replay shape
- CASHRUN remains separate until isolated ACCA lift exists
- no live execution

---

## Current Runtime Truth — SQPE and Sidecars (2026-05-08)

Last updated: 2026-05-08 | Source: live_sidecar_ablation_audit + unified evidence audit.

### SQPE v17 (weight=0.45) — LIVE ANCHOR

SQPE v17 is the main scoring anchor. It is the **only** component with proven positive ROI in live audit. All sidecar weights are defined relative to SQPE v17. No sidecar replaces SQPE. No sidecar is promoted without passing the evidence gate.

### Sidecar Status (2026-05-08)

All sidecars are under audit. The classifications below are the current evidence state. No weight changes are applied. No promotion occurs without explicit operator decision and evidence gate passage.

#### improvement_score (weight=0.12 declared — DISABLED from ensemble)

- Weight=0.12 declared in `_WEIGHTS`, but component is listed in `_DISABLED_COMPONENTS`.
- Runtime confirmation: `improvement_score` does NOT enter the weighted average.
- Ablation audit: SR improves at high values, but ROI=-0.194. OVERBET_RISK.
- Unified audit evidence: improvement_score>0.40 SR=43.5% (n=62) — signal exists in threshold range but not in ensemble probability.
- Status: **OVERBET_RISK / BADGE_ONLY_CANDIDATE**
- Under audit. No weight change until evidence gate n>=100 with positive ROI.

#### market_deception_score (weight=0.10 — LIVE)

- Live-weighted at 0.10. Enters ensemble probability.
- Ablation audit: SR improves strongly at high values, ROI=-0.067. OVERBET_RISK.
- Unified audit evidence: MDS>0.5 SR=54.8%, Frame=96.8% (n=31) — highest-lift signal in the system.
- Status: **LIVE_WEIGHT_REDUCE_CANDIDATE / OVERBET_RISK**
- Signal is real and powerful at MDS>0.5 threshold. Risk is in ensemble weight, not the signal itself.
- Under audit. No weight change until prospective n>=50 at MDS>0.5 cleared.

#### place_prob (weight=0.08 — LIVE)

- Live-weighted at 0.08. Enters ensemble probability.
- Ablation audit: SR improves at high values, ROI=-0.094. OVERBET_RISK.
- Unified audit evidence: place_prob>0.80 SR=31.6% (n=392).
- Status: **OVERBET_RISK / BADGE_ONLY_CANDIDATE**
- Frame improves but ROI is negative. Recommended as operator coverage badge, not probability weight.
- Under audit. No weight change.

#### longshot_score (weight=0.07 — LIVE, SP>=10 only)

- Live-weighted at 0.07. Only enters ensemble when SP>=10.
- Ablation audit: SR improves at high values, ROI=-0.116. OVERBET_RISK.
- Small SP>=10 sub-population — low n.
- Status: **OVERBET_RISK / BADGE_ONLY_CANDIDATE**
- Under audit. Isolate to SP>=10 candidate lane, n>=30 before reconsideration.

#### release_window_score (weight=0.00 — NOT IN ENSEMBLE)

- Previously believed disabled. Runtime audit confirmed weight=0.00 in this worktree. Monitor only.
- Required features (setup_run_flag, cash_run_flag, trainer_timing_score) are NOT wired in `_build_live_features()`.
- Attribution audit: std=0.0, unique=1 — zero variance kill-switch fires.
- Status: **HOLD / SHADOW_ONLY**
- No live weight. Re-enable only when required feature pipeline is fully wired.

#### comment_intel_score (weight=0.00 — NOT IN ENSEMBLE)

- Previously believed disabled. Runtime audit confirmed weight=0.00 in this worktree. Monitor only.
- Required features (quiet_run_score, decoy_support_flag, jockey_switch_intent) are NOT wired.
- Attribution audit: std=0.0, unique=1 — zero variance kill-switch fires.
- Status: **HOLD / SHADOW_ONLY**
- No live weight. Re-enable only when required feature pipeline is fully wired.

#### Racing API enrichment (weight=0.00 — SHADOW/OPERATOR ONLY)

- No live weight. Connection/course/distance shadow scores stored in `racing_api_shadow_forward_ledger.csv`.
- Leakage status: `RETROSPECTIVE_SIGNAL_TEST_WITH_LEAKAGE_RISK` — no production weight changes until prospective validation clears.
- Status: **SHADOW_ONLY**

#### POWER_ANCHOR (paper only — hard live guard)

- Paper ledger only. Hard RuntimeError if VELO_EXECUTION_MODE=LIVE.
- Current state: n=3, gate is n>=20 before first review.
- 2/2 closed wins (Hickory Lad, Infraad). Gate confirmed non-decorative.
- Status: **PAPER_ONLY — no review until n>=20**

#### V2 router (promotion held)

- V2_CLASS4_ONLY: n=17, needs +3 results to reach WATCHLIST gate (n=20).
- V1_BASE: n=27, WATCHLIST status. Needs +23 → SHADOW_CANDIDATE.
- V6_GOLD_SEAM: n=5, LOW_SAMPLE.
- No router rule changes. Evidence accumulation only.
- Status: **V2 promotion-held at n=17, gate is n=20**

### Hard Rules (permanent — never override)

```
NO sidecar gets promoted without evidence gate passage.
NO sidecar gets demoted without evidence gate passage.
NO weight changes from audit script output alone — operator decision required.
NO live staking.
NO model changes.
NO router promotion below threshold.
```

### Next Audit Thresholds

| Signal | Current n | Gate | Action |
|---|---|---|---|
| V2_CLASS4_ONLY router | 17 | +3 → WATCHLIST | Accumulate results |
| POWER_ANCHOR paper | 3 | +17 → first review | Accumulate results |
| MDS>0.5 prospective | 31 (historical) | +50 prospective → weight review | Build prospective sample |
| improvement_score>0.40 | 62 (historical) | +38 prospective → badge discussion | Build badge lane |
| SQPE_ALONE audit | running | n>=50 for classification | sqpe_alone_control_audit.py |
- no staking

---

## Ensemble Surgery v1 — Active Profile (2026-05-08)

**Commit:** b7e4e0c  
**Branch:** main  
**Status:** LIVE_PROFILE_UNDER_MONITORING

### Before / After

| Component | LEGACY_FULL_ENSEMBLE (before) | SQPE_IMPROVEMENT_MDS_V1 (after) |
|---|---|---|
| sqpe_v17 | LIVE (0.45) | LIVE (0.45) |
| improvement_score | DISABLED | LIVE (0.12) |
| market_deception_score | LIVE (0.10) | LIVE (0.10) |
| place_prob | LIVE (0.08) | BADGE_ONLY (excluded from VP) |
| longshot_score | LIVE (0.07, sp>10) | FROZEN (excluded from VP) |
| release_window_score | STORED_ONLY | STORED_ONLY |
| comment_intel_score | STORED_ONLY | STORED_ONLY |

**Evidence:** sqpe_alone_control_audit n=338-342 (2026-05-08)  
- LEGACY ROI = **-3.1%**  
- SQPE_IMPROVEMENT_MDS_V1 ROI = **+13.5%**

### Rollback

```bash
VELO_ENSEMBLE_PROFILE=LEGACY_FULL_ENSEMBLE
```
Restores pre-surgery state immediately. No code change required.  
Profile is logged in every `verdict_flags` as `profile:{name}`.

### VP Recalibration Warning

Average VP dropped ~0.05 because `improvement_score` raw values (0.02–0.15) are much lower than `place_prob` (0.40–0.80). The weighted average compresses.

| Gate | Legacy count (2026-05-07 test n=41) | New profile count |
|---|---|---|
| VP ≥ 0.30 | 17 (41.5%) | 9 (22.0%) |
| VP ≥ 0.25 | 23 (56.1%) | 14 (34.1%) |
| VP ≥ 0.20 | 32 (78.0%) | 22 (53.7%) |

**DO NOT change VP thresholds until 30 live sigma days are resolved.**  
VP25-30 band is flagged `UNDER_CALIBRATION` until evidence arrives.

### 30-Day Monitoring Requirement

- Daily: run `scripts/run_ensemble_shadow_comparison.py --date YYYY-MM-DD`
- Output: `data/ensemble_profile_comparison_YYYY_MM_DD.md`
- Track: `data/ensemble_profile_monitor_latest.csv`
- Decision gate: 2026-06-08 (30 live days from surgery)

### No Staking / No Betfair / No Telegram Betting

The surgery changed **only** the VP weighting profile.

| System | Changed? |
|---|---|
| Betfair order execution | NO — hard RuntimeError gates unchanged |
| Telegram betting alerts | NO — no betting message path changed |
| Paper ledger (POWER_ANCHOR) | NO — SIM mode unchanged |
| Candidate execution gate | NOT CHANGED — VP30 floor unchanged |
| CASHRUN | NOT CONNECTED |
| Racing API shadow lane | SHADOW_ONLY unchanged |

### Release Safety State

```
LIVE_SCORING_PROFILE_CHANGED
LIVE_PROFILE_UNDER_MONITORING
NO_STAKING
NO_BETFAIR
NO_AUTOMATIC_PROMOTION
VP_GATE_RECALIBRATION_REQUIRED (after 30 live days)
```

---

## Sidecar Training & Calibration Spine (2026-05-08)

### Racing API Stats — Connection Status

Racing API trainer/jockey/course/distance analysis tables are CONNECTED in Supabase.
**Total: 374,799 rows across 6 tables.**

| Supabase Table | Rows | Purpose |
|---|---|---|
| `racing_api_trainer_analysis_courses` | 39,740 | Trainer × course stats |
| `racing_api_trainer_analysis_distances` | 32,698 | Trainer × distance stats |
| `racing_api_trainer_analysis_jockeys` | 146,395 | Trainer × jockey combo stats |
| `racing_api_jockey_analysis_courses` | 28,391 | Jockey × course stats |
| `racing_api_jockey_analysis_distances` | 20,573 | Jockey × distance stats |
| `racing_api_jockey_analysis_trainers` | 106,842 | Jockey × trainer combo stats |

**These stats are NOT live-weighted. They are TIER 1/TIER 2 only.**
**No direct live activation without evidence gate passage.**

### Always-Available Access

```bash
# Build local SQLite cache for offline/operator use:
PYTHONPATH=. python scripts/refresh_racing_api_stat_cache.py --full-refresh

# Pre-load for tomorrow's runners:
PYTHONPATH=. python scripts/refresh_racing_api_stat_cache.py --runner-card YYYY-MM-DD

# Check coverage:
PYTHONPATH=. python scripts/refresh_racing_api_stat_cache.py --stats

# Look up single entity:
PYTHONPATH=. python scripts/refresh_racing_api_stat_cache.py --check-entity trn_12345
```

Cache: `data/racing_api_cache.db` — local SQLite, always accessible, no API rate limit.

### Sidecar Promotion Tier Ladder

| Tier | Label | Effect on VP |
|---|---|---|
| TIER 0 | DATA_AVAILABLE | Data exists, no effect |
| TIER 1 | OPERATOR_VISIBLE | Appears on operator cards, no VP |
| TIER 2 | SHADOW_SCORED | Produces scores and logs, no VP |
| TIER 3 | CALIBRATION_TEST | Offline/forward calibration experiments, no VP |
| TIER 4 | PAPER_MODIFIER | Can alter paper-only ranking, no live VP |
| TIER 5 | LIVE_WEIGHT_CANDIDATE | Only after evidence gates + explicit approval |

### Current Sidecar Tier Assignments

| Component | Current Tier | Notes |
|---|---|---|
| sqpe_v17 | **TIER 5 — LIVE** | Core anchor (0.45 weight) |
| improvement_score | **TIER 5 — LIVE** | Active from 2026-05-08 (0.12 weight) |
| market_deception_score | **TIER 5 — LIVE** | Active (0.10 weight) |
| place_prob | TIER 2 — BADGE_ONLY | Frozen from live VP (2026-05-08) |
| longshot_score | TIER 2 — FROZEN | FREEZE_CANDIDATE, ROI=-6.5% |
| release_day_prob | TIER 1 — OPERATOR_VISIBLE | Feature pipeline not wired |
| comment_intel_score | TIER 1 — OPERATOR_VISIBLE | Feature pipeline not wired |
| trainer_course_stats | TIER 3 — CALIBRATION_TEST | In full_analysis, n=19 VP30+ (9.9% coverage) |
| trainer_dist_stats | TIER 3 — CALIBRATION_TEST | In full_analysis, 4.1% coverage |
| jockey_course_stats | TIER 3 — CALIBRATION_TEST | **98.1% coverage** (fixed 2026-05-08: racing_horse_runs join) |
| jockey_dist_stats | TIER 3 — CALIBRATION_TEST | **98.1% coverage** (fixed 2026-05-08: distance_normalizer) |
| trainer_jockey_combo | TIER 3 — CALIBRATION_TEST | 72.3% coverage, VP30 SR=44.5% (n=101) |
| jockey_trainer_combo | TIER 3 — CALIBRATION_TEST | 99.8% coverage, needs outcome analysis |
| rpdc_score | TIER 2 — SHADOW_SCORED | 80.3% coverage, field mapping fixed 2026-05-08 |

### Training Dataset

```bash
# Build full feature dataset:
PYTHONPATH=. python scripts/build_sidecar_training_dataset.py
# Output: data/sidecar_training_dataset_v1.csv (11,542 rows, 10.7% win base rate)
#         data/sidecar_training_dataset_v1.md  (coverage report)
```

**Time-aware split:** train (pre-2026-04-09) / validation / test — NO random shuffle.

### VP Gate Recalibration

```bash
PYTHONPATH=. python scripts/vp_gate_recalibration_audit.py
# Output: data/vp_gate_recalibration_audit_latest.json/.md
```

**Current recommendation: KEEP_VP30** (2026-05-08 calibration run)

Key findings (recalibrated 2026-05-08 with fixed joins):
- VP30 baseline: SR=35.2%, frame=75.7%, ROI=-0.1159 (negative — SP compression from tight market)
- VP30 + trainer_course_win_pct > 15%: SR=42.1%, ROI=+0.4632 (n=19 — needs more data)
- VP30 + jockey_dist_win_pct > 15%: **SR=51.0%, ROI=+0.1388 (n=96 — NEWLY LIVE after fix)**
- VP30 + trainer_jockey_win_pct > 15%: SR=44.5%, ROI=+0.1587 (n=101 — promising)
- Class 1-2 VP30: SR=45.0%, ROI=+0.2695 (n=20 — strong signal, small sample)
- SP 4-8 band VP30: SR=7.8%, ROI=-0.6250 — **SUPPRESS in 4-8 SP range**

**DO NOT change VP threshold until 30 live sigma days after Ensemble Surgery v1 (~2026-06-08).**

### VP Gate Recalibration Required Items

- [x] Resolve dist_f format mismatch — **FIXED 2026-05-08** (`src/velo/distance_normalizer.py` + racing_horse_runs join)
- [x] Add course_id join — **FIXED 2026-05-08** (`src/velo/course_identity_resolver.py` + racing_horse_runs.course_id)
- [ ] Collect 30+ live race days under SQPE_IMPROVEMENT_MDS_V1 profile
- [ ] Re-run calibration with prospective data (current dataset is historical)

### Racing API Sidecar Join Contract (as of 2026-05-08)

Source of truth: `racing_horse_runs` table (90,869 rows).

| Join | Source | Key | Coverage |
|---|---|---|---|
| course_id | racing_horse_runs | (race_id, horse_id) → course_id | 94.5% of velo_verdicts race_ids |
| distance_f | racing_horse_runs | (race_id, horse_id) → distance_f (float furlongs) | 94.5% |
| dist_f string | `float_to_dist_key()` in distance_normalizer | float → "Xf" / "X.Xf" | matches Racing API table format |

**Resolver files:**
- `src/velo/distance_normalizer.py` — `float_to_dist_key(float)` → "Xf" string
- `src/velo/course_identity_resolver.py` — `CourseIdentityResolver.get_course_id_by_race(race_id)` → "crs_XXXX"

The `/courses` API endpoint is not on the current plan (403). Course resolution uses
`racing_horse_runs.course_id` directly — no API call required.

### Operating Rules (permanent)

```
NO direct Racing API live-weight injection without evidence gate.
NO Cashrun connection until RP ingestion pipeline is proven stable.
NO VP threshold change before 2026-06-08 (30-day monitoring gate).
NO sidecar promotion based on historical calibration alone — need prospective confirmation.
```

---

## Dual Source Fusion — Racing API + Racing Post

_Added: 2026-05-08_

### Architecture Declaration

Racing API and Racing Post are not competing sources. They are two halves of the same brain:

- **Racing API** = identity, structure, connection strength
- **Racing Post** = form, intent, mark compression, handicap plot trail

Both feed one runner intelligence packet. Neither source overwrites the other.
Every field in the fused packet must preserve its provenance:
`source = Racing API | Racing Post | derived`
`status = LIVE | SHADOW | OPERATOR | BLOCKED`

### Source Field Map

**Racing API provides:**

| Field group | Fields |
|---|---|
| Identity | race_id, horse_id, trainer_id, jockey_id, course, distance, class |
| Trainer stats | trainer_course_win_pct, trainer_dist_win_pct, trainer_jockey_win_pct |
| Jockey stats | jockey_course_win_pct, jockey_dist_win_pct, jockey_trainer_win_pct |
| Sample context | A/E ratios, sample sizes per stat |

**Racing Post provides:**

| Field group | Fields |
|---|---|
| Ratings | current OR, current TS, current RPR |
| Form history | last 6 OR, last 6 TS, last 6 RPR, last winning OR (if available) |
| Narrative | Spotlight, Postdata, form comments |
| Signals | setup-run language, class/trip/going clues, handicap mark history |
| Form string | full form string |

### Source Priority Rules

| Field category | Primary source | Fallback |
|---|---|---|
| Identity fields (race_id, horse_id, etc.) | Racing API / Supabase | Racing Post race header |
| Race metadata (course, distance, class) | Supabase races / Racing API | Racing Post race header |
| Trainer/jockey stats | Racing API analysis tables | None |
| OR / TS / RPR (current + last 6) | Racing Post | None |
| Spotlight / Postdata | Racing Post only | None |
| CASHRUN derivation | Racing Post mark/form trail + Racing API trainer/jockey/course/distance support | — |

### Runner Intelligence Packet Schema

The fused packet consumed by CASHRUN:

```
api_identity:
  race_id          — source: Racing API / Supabase
  horse_id         — source: Racing API / Supabase
  trainer_id       — source: Racing API / Supabase
  jockey_id        — source: Racing API / Supabase
  course           — source: Racing API / Supabase
  distance         — source: Racing API / Supabase
  class            — source: Racing API / Supabase

api_stat_context:
  trainer_course_win_pct     — source: Racing API, status: SHADOW
  jockey_course_win_pct      — source: Racing API, status: SHADOW
  trainer_distance_win_pct   — source: Racing API, status: SHADOW
  jockey_distance_win_pct    — source: Racing API, status: SHADOW
  trainer_jockey_win_pct     — source: Racing API, status: SHADOW
  jockey_trainer_win_pct     — source: Racing API, status: SHADOW
  ae_ratio                   — source: Racing API, status: SHADOW
  sample_sizes               — source: Racing API, status: SHADOW

rp_form_context:
  current_or       — source: Racing Post, status: OPERATOR
  current_ts       — source: Racing Post, status: OPERATOR
  current_rpr      — source: Racing Post, status: OPERATOR
  last_6_or[]      — source: Racing Post, status: OPERATOR
  last_6_ts[]      — source: Racing Post, status: OPERATOR
  last_6_rpr[]     — source: Racing Post, status: OPERATOR
  last_winning_or  — source: Racing Post, status: OPERATOR (if available)
  form_string      — source: Racing Post, status: OPERATOR

rp_intent_context:
  spotlight        — source: Racing Post, status: OPERATOR
  postdata         — source: Racing Post, status: OPERATOR
  form_comments    — source: Racing Post, status: OPERATOR
  keywords: [
    "well handicapped", "dangerous", "back on winning mark",
    "below last winning mark", "interesting", "better than bare result",
    "shaped better", "return to trip", "market support significant"
  ]

derived_cashrun_signals:
  mark_compression_score       — source: derived, status: OPERATOR
  ts_rpr_hidden_form_score     — source: derived, status: OPERATOR
  setup_run_score              — source: derived, status: OPERATOR
  trainer_jockey_intent_score  — source: derived (Racing API + RP), status: OPERATOR
  spotlight_postdata_intent_score — source: derived, status: OPERATOR
  negative_suppression_score   — source: derived, status: OPERATOR
  final_cashrun_score          — source: derived, status: OPERATOR
  final_cashrun_class          — source: derived, status: OPERATOR
```

### CASHRUN Signal Derivation Rules

**mark_compression_score**
```
if current_or < last_winning_or:
    mark_compression_score = (last_winning_or - current_or) / last_winning_or
else:
    mark_compression_score = 0.0
```
Captures how far below its last winning mark a horse is running — the primary CASHRUN indicator.

**ts_rpr_hidden_form_score**
Low variance in last_6_ts + RPR holding steady despite OR drop → latent form present.
Signals that handicapper has not caught up with true ability.

**trainer_jockey_intent_score**
Uses Racing API `trainer_jockey_win_pct` + course and distance stats.
A positive combo (above-average partnership at this course/distance) lifts the score.
Reflects deliberate placement and connection intent.

**final_cashrun_class thresholds**

| Class | Score threshold | Meaning |
|---|---|---|
| CASHRUN_A | ≥ 0.65 | High-confidence setup — all signals aligned |
| CASHRUN_B | ≥ 0.45 | Probable setup — most signals positive |
| CASHRUN_WATCH | ≥ 0.25 | Partial signal — monitor for market confirmation |
| SUPPRESS | < 0.25 | Insufficient evidence — do not surface |

### Status Governance

All CASHRUN-related signals are currently: **OPERATOR_VISIBILITY_ONLY**

They are not in VP weights. They do not affect `velo_prime_prob`.
They are surfaced in operator cards and audit trails only.

Promotion path: OPERATOR → SHADOW_SCORED → CALIBRATION_TEST → PAPER_MODIFIER → LIVE_WEIGHT_CANDIDATE
Each step requires evidence gate passage (n ≥ 50 prospective resolved rows minimum).

### Cockpit Metaphor

```
Racing API    = the skeleton          (who, where, connection strength)
Racing Post   = the nervous system    (form, intent, mark trail)
CASHRUN       = the intent detector   (is this horse being set up today?)
VP            = the probability engine (how likely is this horse to win?)
Operator card = the cockpit           (everything the operator needs to decide)
```

No confusion if provenance is kept. Every field says where it came from.
VÉLØ can see the whole race without hallucinating what is connected.

