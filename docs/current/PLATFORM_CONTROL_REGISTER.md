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

## Railway inventory

| Service | Role | Verdict / action |
|---|---|---|
| `velo-rp-capture` | 07:00 UTC RP capture + UK scoring | KEEP; sole morning owner |
| `velo-results-sigma` | 21:00 UTC governed EOD | KEEP; sole UK EOD owner |
| `velo-formfav-live` | provider ingestion/results | KEEP; provider facts only, no provider prediction in Velo features |
| `velo-formfav-uk-shadow` | UK enrichment evidence | KEEP; remove obsolete Racing API secrets after dependency proof |
| `velo-formfav-us-shadow` | hourly AU/CA/FR/HK/JP/US Velo shadow | KEEP; rename to `velo-world-shadow` in an approved cleanup |
| `velo-oracle` | dashboard/API | KEEP; Supabase-only truth target |
| `velo-prime-scoring` | unscheduled legacy scorer | DUPLICATE; retire after dependency proof |
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

