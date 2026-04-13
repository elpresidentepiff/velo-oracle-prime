# Scripts Classification — VÉLØ Oracle Prime

## PRODUCTION (safe to run with production write keys)

| Script | Purpose |
|--------|---------|
| `run_prime_today.py` | Daily scoring pipeline |
| `close_sigma_loops.py` | Full sigma reconciliation + truth loop |
| `run_results_sigma.py` | Lightweight sigma reconciliation |
| `feed_sigma_loop.py` | Sigma → Playbook G feed |
| `velo_morning_cockpit.py` | Operator morning briefing (read-only) |
| `preflight_10am_check.py` | Pre-flight health check (read-only) |
| `post_run_persistence_check.py` | Post-run verification (read-only) |

## MAINTENANCE (one-off data fixes — run manually with caution)

| Script | Purpose | Risk |
|--------|---------|------|
| `backfill_miss_evidence.py` | Backfill miss_category on old reviews | Writes to velo_post_race_reviews |
| `gate_e_evidence.py` | Gate E evidence injection | Writes to learned_patterns |
| `populate_entity_bibles.py` | Entity bible population | Writes to entity tables |
| `review_proposals.py` | Governance proposal review | Writes to governance tables |
| `generate_verdicts.py` | Manual verdict generation | Writes to velo_verdicts |
| `ingest_march16_card.py` | One-off historical ingestion | Writes to race data |

## RESEARCH / TEST (must NOT run with production write keys)

| Script | Purpose | Risk |
|--------|---------|------|
| `proof_governance_e2e.py` | Governance E2E proof | Creates test governance data |
| `proof_playbook_g_persistence.py` | Playbook G persistence proof | Creates test patterns |
| `proof_sentient_bridge.py` | Sentient bridge proof | Reads only |
| `run_ablation_backtest.py` | Ablation backtesting | Research only |
| `run_attribution_audit.py` | Attribution audit | Research only |
| `run_suppression_audit.py` | Suppression audit | Research only |
| `continuous_training.py` | Auto-training pipeline | Writes model artifacts |
| `deploy_schema.py` | Schema bootstrap (legacy) | DDL operations |
| `test_*.py` | Test scripts | Various |

## Rule

> Scripts in the RESEARCH / TEST category must never be run with `SUPABASE_SERVICE_ROLE_KEY`.
> Use a read-only Supabase key or a staging project for these scripts.
