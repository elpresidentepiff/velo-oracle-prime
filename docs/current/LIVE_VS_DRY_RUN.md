# LIVE_VS_DRY_RUN.md — Status Vocabulary

Every component, lane, or artifact in this system should be describable with one
of these statuses. Ambiguity between these is what the Model Result Reporting Law
(`docs/current/MODEL_RESULT_REPORTING_LAW.md`) was written to eliminate.

| Status | Meaning |
|---|---|
| `LIVE` | Affects production/user-facing output: the scoring formula, persisted `velo_verdicts`, or a Telegram send that is actually enabled. Currently: `run_prime_today.py` scoring path, `SQPE_IMPROVEMENT_MDS_V1` profile, Supabase `velo_verdicts`. |
| `DRY_RUN` | Produces evidence only, no live effect. Runs against real data but does not write to any live/production surface. Example: VFU autopsy passes, Pattern Tribunal watchlist promotions. |
| `SHADOW` | Runs beside the live system for comparison, never overrides or feeds live scoring. Examples: New Build two-lane scorer, No-RPR model, Champion Intent Shadow, Race Shape v1. |
| `REPORT_ONLY` | Creates analysis/dashboard context, no mutation anywhere. Examples: VP Gatekeeper (`docs/current/VP_GATEKEEPER_PROMOTION_V1.md`), Tri-Lane stress test, Course Master, Old VELO Three-Option Card. |
| `QUARANTINE` | Known unsafe/contaminated evidence — must not train or promote anything. Example: Kakirra (VFU-10, confirmed CONTAMINATED — no pre-era data). |
| `TRIBUNAL_ONLY` | Requires human/promotion review before it can move status. Example: Pattern Tribunal candidates sit here until operator reviews the Top 25 human review queue. |

## Current live/shadow/report-only assignment

This table is a pointer, not a duplicate — the authoritative, continuously-updated
version lives in `docs/current/ONE_TRUTH.md` under "What is LIVE" / "What is
SHADOW" / "Paper Intelligence" / "What is DEPRECATED" / "What is EXPERIMENTAL".
Always check that section directly rather than trusting a cached copy here.

As of this writing, the quick summary is:
- **LIVE:** `run_prime_today.py` / `SQPE_IMPROVEMENT_MDS_V1` / `sqpe_v17.pkl` / RP HTML capture / Supabase `velo_verdicts`.
- **SHADOW:** New Build two-lane scorer, No-RPR model, Champion Intent Shadow, Playbook G sentient loopback, Execution bridge paper ledger (SIM only), Router lanes V1/V2/V6, Shadow Model C, Race Shape v1.
- **REPORT_ONLY:** VP Gatekeeper, Radical Shadow VELO, Tri-Lane V2, Tri-Lane Agent Review, Deep Race Agent V1, Course Master, Old VELO Three-Option Card, Model Suggestions dashboard panel.
- **DEPRECATED:** Racing API as a data source, Sporting Life scraper, `velo_race_day_button.py`, `scrape_results_atr.py` (does not exist), root `Makefile`, root `cron.txt`, `COMMAND.json`.
- **EXPERIMENTAL:** International prerace arenas, HK/FR feature builders, Intent Layer V1 (patched, rerun required), sqpe_v18 (`NO_LIFT` verdict, not wired).

## How to label new work

Any new lane, script, or dashboard panel must declare one of the six statuses
above explicitly (in code comments, report headers, or the dashboard's own
`trust_policy`/`velo_scoring_allowed` fields — see `build_intent_shadow_scorecard.py`
for the reference pattern: `trust_policy: ARCHIVE_CONTEXT_ONLY_NOT_SCORING`,
`velo_scoring_allowed: false`). Never leave a new component unlabelled.
