# VÉLØ Production Rollback Runbook V1

**Date:** 2026-05-05

This runbook defines the exact procedures for returning VÉLØ to a last known working state in the event of a failure. It is mandatory insurance before performing any dangerous work (e.g., HFS repair, backfills, schema migrations).

## 1. Code Rollback

**Scenario:** A code deployment (e.g., modifying `build_unified_evidence_corpus.py`) breaks predictions or ingestion.

**Action (Railway UI - Fastest):**
1. Navigate to the Railway Dashboard -> Project `sincere-empathy` -> Service `velo-oracle`.
2. Go to the **Deployments** tab.
3. Find the last successful deployment prior to the incident.
4. Click the three dots (⋮) and select **Rollback / Redeploy**.

**Action (Git CLI - Permanent):**
1. Identify the bad commit hash: `git log --oneline`
2. Revert the commit: `git revert <bad_commit_hash>`
3. Push to trigger a clean CI/CD deploy: `git push origin main`

## 2. Database Schema Rollback

**Scenario:** An Alembic migration modifies a table structure (e.g., `historical_feature_store`) and breaks downstream queries.

**Action (Alembic CLI):**
*Warning: Downgrading may result in data loss for columns created in the bad migration.*
1. Connect to the execution environment.
2. Run: `alembic downgrade -1` (to step back one migration).
3. Verify the schema state matches the previous baseline.

## 3. Data Rollback (The Most Dangerous)

**Scenario:** An agent runs a bad HFS backfill or feature generation script, polluting the database with thousands of fake/proxy rows.

**Prevention (Mandatory before backfills):**
- All bulk inserts/updates MUST include a `batch_id` and `audit_id`.
- Count rows before execution: `SELECT count(*) FROM historical_feature_store;`
- Export affected rows to a CSV backup (e.g., `data/archive/hfs_backup_pre_batch_XYZ.csv`).

**Action (SQL Remediation):**
1. Identify the bad batch:
   ```sql
   SELECT count(*) FROM historical_feature_store WHERE batch_id = 'bad_batch_id';
   ```
2. Execute targeted deletion (Requires explicit approval):
   ```sql
   DELETE FROM historical_feature_store WHERE batch_id = 'bad_batch_id';
   ```

**Action (Supabase PITR - Catastrophic Failure):**
If the data corruption is untraceable or a `DROP TABLE` occurred:
1. Access the Supabase Console -> Database -> Backups.
2. Initiate Point-in-Time Recovery (PITR) to the timestamp immediately preceding the bad agent run.

## 4. Config & Environment Rollback

**Scenario:** Incorrect Railway or Supabase environment variables are applied, causing connection failures.

**Action:**
1. Maintain local backups of production configurations (`.env.production.bak`).
2. Revert variables via the Railway Dashboard -> Variables tab.
3. Railway will automatically trigger a redeploy with the restored variables.

## 5. Learning Rollback (Playbook G)

**Scenario:** Playbook G consumes contaminated training data (e.g., flat proxy signals) and its sentient state is compromised.

**Prevention:** Playbook G operates in **SHADOW_ONLY** mode until signals are proven.

**Action (State Restoration):**
1. Locate the daily backup of the sentient state: `data/sentient_state_backup_YYYYMMDD.json`
2. Overwrite the corrupted active state:
   ```bash
   cp data/sentient_state_backup_YYYYMMDD.json data/sentient_state.json
   ```
3. Quarantine the bad learning events:
   ```bash
   mv data/playbook_g_outcome_events.jsonl data/playbook_g_quarantine_bad_run.jsonl
   ```
4. If applicable, restore the `learned_patterns` row in Supabase from the previous day's snapshot.

---
**Rule:** Create rollback safety before modifying HFS, database schemas, scoring logic, or Playbook G. No rollback, no cowboy changes.
