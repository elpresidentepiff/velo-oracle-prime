# TREASURE AND JUNK — FULL ASSET INVENTORY

**Date:** 2026-06-10 · Honest sweep of everything on disk. Repo ~11.2GB (data 11G, models 77M).

## TREASURE — assets worth real money/leverage

| Asset | Size / scale | Why it matters | Status |
|---|---|---|---|
| `data/raceform_clean.parquet` + `raceform_v17_features.parquet` | **1,702,741 runner rows, 2015-01-01 → 2025-07-05**, 37/47 cols incl. SP, position, target, implied prob | **The crown jewel.** Ten years of UK raceform = offline validation universe for ANY tier rule, model, or staking policy — including replaying the Tier-A economics over a decade before believing 365 picks | Sitting idle. Wire into the evaluation harness |
| Supabase `racing_horse_runs` (94,915) + `sigma_audits` (2,528) + `velo_verdicts` (3,390) | live, current | The operating record + the canonical conclusions universe | Active, now provable |
| `data/features/jtc_d/` (5 parquets, **~494k profile rows**: trainer/jockey × course/distance/combo) | 75k–179k rows each | Trainer-jockey combo signal already showed SR 46.3% (n=95, TIER 3) — mostly **unwired** | Treasure unplugged. Two known blockers (course_id mapping, dist_f format) |
| `data/new_build/` (1.4G): training splits (`core_v0_*` train/val/test), 610M sidecars, normalized entity tables | proper ML hygiene | Champion Core_V0_OR_Passport (AUC 0.6922, **4/4 unseen gates** — an *honest* AUC, unlike sqpe_v17's suspicious 0.94) | The credible next-model lane |
| `models/shadow/` (47M, model_arena + v2) | Model C ensemble | PASS_QUARANTINE, top-decile ROI +11.86% in shadow | Forward lane active since May 18 |
| `models/sqpe_v17` + `models/specialist/` (improvement, MDS) | 22M | The live engine — now with proven Tier-A SP economics (+4.3%, n=365) | Live, frozen |
| BHA pack: `bha_perf_figures_latest.csv` (11,851 horses), `bha_or_diff_latest.csv` (1,143), macro parquet (2012–2026) | current | Official-rating diffs + surface trajectories, badges already wired | Refresh weekly |
| `data/new_build/passports/` (6,168 horses) | partial coverage | Horse career passports — feeds two-lane scorer | Coverage gap vs ~17k runner universe |
| The June-10-era tooling | — | Truth ledger, loop checkers, preflight, ROI auditor, 23 boundary tests — the proof culture itself | New, committed |
| `data/racing_post_account_parsed/` + `racecard_merged/` (105M) | parsed daily truth | Replayable inputs for the golden-day test | Keep |

## JUNK — dead weight, candidates for the approved sweep

| Item | Size | Verdict |
|---|---|---|
| `data/racing_post_account_raw/` | **8.3G (74% of repo)** | Raw HTML already parsed downstream. Treasure as *archive*, junk on a working disk — compress to tar.zst per day (~10:1) or move to cold storage. Never delete the parsed layer |
| `data/browser_profiles/` | 403M | Playwright session — keep ONE live profile, the rest is bloat |
| `models/tie_v9`, `sqpe_v14`, `overlay_v5`, `longshot_v6` | **0 bytes — empty dirs** | Docs claim they exist (CLAUDE.md "TIE v9 EXISTS on disk" — false). Delete dirs, fix doc |
| `velo_memory.db` (root) | 1 race, 17 runners | Vestigial experiment. Archive |
| `training_data/synthetic_dataset_v1.json` | 1.3M | Synthetic toy data. Archive |
| `data/backtest_50k.csv` | **does not exist** | CLAUDE.md still lists it. Doc lie, remove reference |
| `scripts/data/velo_unified_evidence_corpus_v1.csv` | header only | Empty placeholder. Archive |
| `railway_hermes_env.txt` (1,775 lines!), `railway_velo_oracle_env.txt` | 284K | Railway variable dumps at repo root — **operator handles secrets**; flagged again, highest-priority manual review |
| `hackathon/` (8.1M), `presentation*/` (1.4M), `moltbook/`, `feast_repo/`, `mlruns/` | ~12M | Side-quests. Archive wholesale |
| `data/racing_api_raw/` (23M) + API-era scripts | — | Decommissioned source. Archive per Racing API audit |
| `tmp/`, `incoming/` (1.8M + scratch), `quarantine/app` | — | Scratch. Sweep |
| `Makefile`, `cron.txt`, `COMMAND.json`, `sigma_tonight.sh` | — | Already classified DELETE_AFTER_APPROVAL |

## AMBIGUOUS — operator decision needed

| Item | Question |
|---|---|
| International lane (`data/features/hk/fr parquets` 70M, 12 audit scripts) | Park officially (SHADOW, no work) or archive? Leakage risk was flagged in April |
| `data/race_shape/` (30M, May 24–27 form histories) | Race Shape v1 stalled at DESIGN_PENDING — resume or archive? |
| `workers/ingestion_spine/` (2M, the only thing CI tests) | Retire with Racing API era, or keep PDF parser? |
| `telegram_cards/` (1.4M), `out/`, `results/` (2.1M), `predictions/` | Outputs of past eras — archive after checking nothing reads them |
| `data/rpdc_backfill/` (12M) | RPDC historical backfill staging — feeds repair item B? Verify then keep until repair done |
| 18 cron-era days in Supabase with no local backup | Accept as HISTORICAL_OUTPUT_ONLY forever (recommended) |

## The honest summary
**~80% of disk is replaceable raw capture; ~95% of the *value* sits in five things:** the 1.7M-row decade of raceform, the live Supabase operating record, the JTC-D profile bank, the new_build training discipline, and the shadow arena. The plans are ambitious but the funding assets already exist — what was missing was knowing where they were.
