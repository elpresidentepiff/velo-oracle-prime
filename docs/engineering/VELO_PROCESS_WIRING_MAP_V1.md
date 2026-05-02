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
