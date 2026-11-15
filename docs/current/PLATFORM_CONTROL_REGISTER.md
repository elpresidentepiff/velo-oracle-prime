# VÉLØ Platform Control Register

**Authority:** operational inventory only; `ONE_TRUTH.md` remains doctrine.  
**Verified:** 2026-11-05 15:20 Europe/London  
**Production head:** GitHub `main` at `b77bab5a`  
**Mode:** PAPER/SIM only

This register answers what is authoritative, what is deployed, what durable evidence proves a run, and what must be retired or repaired.

## Ownership contract

| Concern | System of record | Contract |
|---|---|---|
| Code, migrations, runbooks, model manifests | GitHub `main` | No production-only or laptop-only code. |
| Scheduled execution and runtime secrets | Railway production | Jobs follow `main`; the laptop scheduler is never authoritative. |
| Cards, predictions, results, gates, learning evidence and reports | Supabase | Every dashboard claim needs a durable row or view. |
| Raw authenticated RP HTML/browser state | Railway worker ephemeral storage today | Remaining storage gap; use encrypted object storage with hashes and retention. |
| Laptop | Disposable operator console/emergency scratch | No unique truth. Important evidence must be persisted or declared incomplete. |

Railway, Supabase and GitHub do **not** gain access to the operator's laptop merely because Velo uses them. They receive only code/data/credentials explicitly pushed or transmitted. A separate remote-control agent, tunnel or exposed local service would be required for laptop access.

## Today — 2026-11-05

| Check | Verified state |
|---|---|
| UK/IRE scoring | `PASS/completed`; 45 races, 420 runners; 07:19–07:20 UTC |
| Scoring SHA in terminal row | `d4802bf8` (older than current `main`; valid run evidence, but deployment lineage needs tightening) |
| Canonical model capture | Ten model families present: Main, No-RPR, New Build A/B, Champion Intent, MDS-heavy, three Old Velo roles and Passport proxy |
| Later rerun | Stopped truthfully: 43/47 FormFav coverage because two Abu Dhabi supplement cards wrongly inflated a GB/IE gate denominator; no bypass |
| World shadow | 233 races; 224 provider-predicted; immutable Velo world scorecards already frozen pre-off for 120 races / 1,100 runners |
| UK Sigma/EOD | Not due at audit time; 0/45 settled |
| Dashboard | Core cards/canonical rows load from Supabase; Truth Cockpit and several paper overlays still have local/deploy-time dependencies; repair in progress |

## Laptop dependencies (audited 2026-11-15)

Rule: a race day must run from GitHub, Railway and Supabase alone. This table lists everything the cloud run was found to need from the laptop.

| What | Where it lived | State after `CLOUD-STATE-01` |
|---|---|---|
| Horse passport bank | `data/new_build/passports/horse_passports_v1.jsonl`; git copy from 2026-08-04, full copy on the laptop | **Supabase** `new_build_horse_passports`. Merged into the run at the start, changed rows written back after each capture (`scripts/ops/cloud_state.py`) |
| Per-run form history (source of the bank and of Champion Intent features) | `data/race_shape/form_history_*.json`; 78 files in git, the rest on the laptop | **Supabase Storage** `rp_imports`: seed `velo-archive/v1/data/race_shape/` (102 files, archived 2026-09-19), new captures in `velo-state/race_shape/` |
| New Build Lane C model | `data/new_build/models/soft_label_challenger/champion_model.pkl`, git-ignored | **GitHub**: loaded from `data/new_build/models/champion/champion_model.pkl`, byte-identical (same MD5 in the archive) |
| Racing Post ratings sheets (PDF) | fetched into a OneDrive folder path hard-coded in two scripts | Checkout path `data/pdf_inbox` off the laptop; the fetch signs in within its own browser context. **Not yet confirmed on Railway** |
| Mid-Price Specialist model | `models/sqpe_v17_midprice_specialist_staging/sqpe_v17_midprice_specialist.pkl` | **STILL LAPTOP ONLY.** Not in any branch or tag, not in the Supabase archive (it covers `data/` only) |
| Radical Shadow sigma gates | `models/radical_sigma_gate_staging/sigma_win_gate.pkl`, `sigma_frame_gate.pkl` | **STILL LAPTOP ONLY.** Same search, same result |
| Form history captured on the laptop between 2026-09-19 and now | laptop `data/race_shape/` | **STILL LAPTOP ONLY.** Each horse's full career returns the next time the cloud captures it |
| Raw Racing Post HTML | Railway container disk, lost at exit | Unchanged. Parsed output is in Supabase |

The three laptop-only model files can now be added with a plain `git add` (`.gitignore` exceptions added). Once they are pushed, nothing in the daily run depends on the laptop.

## Railway inventory

| Service | Role | Verdict / action |
|---|---|---|
| `velo-rp-capture` | 07:00 UTC RP capture + UK scoring | KEEP; sole morning owner |
| `velo-results-sigma` | 21:00 UTC governed EOD | KEEP; sole UK EOD owner |
| `velo-formfav-live` | provider ingestion/results | KEEP; provider facts only, no provider prediction in Velo features |
| `velo-formfav-uk-shadow` | UK enrichment evidence | KEEP; remove obsolete Racing API secrets after dependency proof |
| `velo-formfav-us-shadow` | hourly AU/CA/FR/HK/JP/US Velo shadow | KEEP; rename to `velo-world-shadow` in an approved cleanup |
| `velo-oracle` | dashboard/API | KEEP; Supabase-only truth target |
| `velo-prime-scoring` | duplicate scorer; **holds a live `0 7 * * *` cron and the same start command as `velo-rp-capture`** (verified 2026-11-15) | DUPLICATE. Both ran on 2026-11-14 and contended for Racing Post. From `MORNING-TIMEOUT-OWNER-01` its scheduled run stands down in code (`VELO_MORNING_OWNER_SERVICE`, default `velo-rp-capture`); an authorised rescore still runs here. Operator: remove its cron, then retire after dependency proof |
| `velo-daily-ingestion` | unscheduled Racing API worker | LEGACY; retire after dependency proof |
| `ingestion-spine` | deleted branch; build mutates source | NON-REPRODUCIBLE; quarantine then retire |
| `velo-shadow-lab` | deleted branch | DEAD; retire after evidence export |
| `velo-oracle-prime` | no start command | IDLE duplicate; retire or assign a documented role |
| `hermes-agent` | failed deploys; malformed variable-name set | RETIRED/BROKEN; isolate from production |
| `presidente-bot` | different repository with broad credentials | OUTSIDE VELO; separate credential/ownership audit |
| `Postgres-8kOH` | Railway database | UNMAPPED; prove a consumer or retire separately |

## GitHub control

Audit basis: `origin/main=b77bab5a`.

| Branch | Behind | Ahead | Classification |
|---|---:|---:|---|
| `research/evo2-challenger-lab` | 36 | 40 | Preserve research; chronological validation before merge |
| `fix/rp-session-alerting-and-venue-allowlist` | 98 | 28 | High-drift salvage review only |
| `fix/railway-cloud-raceday-20261004` | 86 | 21 | High-drift salvage review; partly superseded |
| `fix/velo-daily-sigma-racing-horse-runs` | 12 | 6 | Relevant EOD candidate; diff against current EOD |
| `codex/production-truth-audit` | 11 | 4 | Reconcile findings, then close |
| `ops/recovery` | 0 | 4 | Inspect four commits; PR or archive |
| `fix/ci-ruff-c420-b023` | 13 | 2 | Likely superseded; verify then close |
| `ops/rescue-score-20261004` | 85 | 1 | Inspect unique commit, then archive |
| `fix/formfav-shadow-enrichment` | 49 | 0 | Fully contained in main; retirement candidate |

Open PRs are the Evo² draft plus eight dependency updates. The dependency PRs target the legacy ingestion-spine subtree and must not be bulk-merged before deciding that service's future.

## Platform comparison

Production prediction systems separate feature definitions, model lineage, immutable prediction captures, monitoring and promotion. Velo owns fragments of all five but lacks a single control plane.

| Capability | Velo now | Target |
|---|---|---|
| Feature consistency | Feature code + Supabase + local sidecars | Versioned feature manifest on every prediction: source time, freshness, null-rate and contract version |
| Model registry/lineage | Model files in Git; one stale registry record | Model version + feature contract + code SHA + source snapshot on every frozen prediction; operator-gated champion alias |
| Immutable prediction ledger | UK and World canonical scorecards | Only prediction source used by dashboard; post-off overwrite prohibited |
| Settlement | UK Sigma and World Sigma | One state machine with unresolved/provisional/final/void counts |
| Monitoring | Ad-hoc gates/audits | Scheduled feature drift, missingness, identity, calibration and ranking-quality reports with alerts |
| Orchestration | Railway crons plus duplicates | One morning owner, one UK EOD owner, one world owner; alerts and idempotent retries |
| Reproducibility | GitHub plus partial SHA stamps | Deployed SHA equals source SHA; no deleted branches or build-time source mutation |
| Dashboard truth | Mixed Supabase/local JSON | Supabase-only reads with freshness and producer lineage on every panel |

## P0 queue

1. Cut dashboard paper/truth panels over to `velo_report_artifacts` or canonical tables; remove local-only production reads.
2. Materialize one durable daily state machine: `MORNING_READY → RACING → EOD_PENDING → EOD_COMPLETE | BLOCKED`.
3. Retire duplicate/legacy/dead Railway services after read-only dependency proof.
4. Minimize credentials and separately audit `presidente-bot`.
5. Populate a real model registry before any promotion discussion.
6. Salvage unique branch commits into small PRs, then close/archive superseded branches.
7. Add encrypted object storage for raw RP evidence; never put cookies/secrets/raw HTML in GitHub.

## Daily acceptance contract

A date is complete only when the cloud control plane proves:

- date-scoped terminal row with SHA, counts and PASS/blocker;
- immutable per-runner predictions for required model lanes;
- result coverage and unresolved count;
- Sigma, Council, final Mission Control and learning-gate outcomes;
- dashboard freshness and lineage;
- no laptop-only artifact is required to reproduce what is displayed.

