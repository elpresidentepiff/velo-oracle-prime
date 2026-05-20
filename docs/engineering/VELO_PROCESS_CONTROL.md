# VÉLØ Process Control V1

This document defines the canonical operating map for VÉLØ.

## 1. Process Map

| Process Name | Canonical Command | Read-First Docs | Source of Truth |
|---|---|---|---|
| **AGENT_BOOT** | N/A | `CLAUDE.md`, `VELO_MASTER_LOG.md` | `ARTIFACT_MAP.md` |
| **DAILY_PREDICTIONS** | `python3 scripts/run_prime_today.py` | `docs/VELO_DAILY_PROCESS.md` | Supabase `races`, `runners` |
| **PDF_TRACK_INTAKE** | `python3 scripts/ingest_racecard_pdfs.py` | `docs/PDF_PARSING.md` | `data/incoming_pdfs/` |
| **SIGMA_RESULTS** | `python3 scripts/run_results_sigma.py` | `docs/VELO_SIGMA_FORENSIC_AUDIT.md` | Racing API `/results` |
| **DASHBOARD_PUBLISH** | `python3 scripts/publish_daily_predictions_to_dashboard.py` | `docs/engineering/DASHBOARD_DAILY_PREDICTIONS_PUBLISHER_V1.md` | `velo_verdicts` table |
| **RACING_API_CAP** | `python3 scripts/explore_racing_api.py` | `docs/API_INTEGRATION.md` | Racing API Swagger/Probe |
| **HFS_INTEGRITY** | `python3 scripts/audit_hfs_signal_integrity_block001.py` | `docs/FEATURE_MART.md` | `historical_feature_store` |
| **PLAYBOOK_G_LOOP** | `app/playbooks/playbook_g_sentient_loopback.py` | `docs/SENTIENT_PLAYBOOK_G.md` | `data/sentient_state.json` |

## 2. Success Criteria & Failure Modes

### DAILY_PREDICTIONS
- **Success:** Persistent predictions in Supabase + Telegram summary sent.
- **Failure Mode:** Racing API rate limit or missing PDF intelligence.

### PDF_TRACK_INTAKE
- **Success:** PDFs parsed and signals attached to horse records.
- **Failure Mode:** Regex mismatch on filenames or corrupt PDF structure.

### SIGMA_RESULTS
- **Success:** Daily reconciliation report sent to Telegram + `runner_results` updated.
- **Failure Mode:** Unmatched horse names (fuzzy matching required).

## 3. Known Blockers (P0/P1)
- **HFS Flatness (P0):** MPI/Chaos Bloom signals in Block 001 are not currently usable for training.
- **Supabase Dependency (P1):** Pipeline depends on `supabase` python package which is missing in some environments.

## 4. Repo Hygiene
- **Forbidden:** Never commit `.env`, `.claude.json`, or `settings.local.json`.
- **Forbidden:** Never modify scoring logic during a dashboard publish run.
- **Mandatory:** Always dry-run PDF ingestion before writing to Supabase.
