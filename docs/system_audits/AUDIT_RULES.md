# System Audits — Schedule and Rules

## Weekly Audit Checklist

Before each new session:

### 1. Repo State
- [ ] `git status` — any uncommitted changes?
- [ ] Last commit date on `src/v13/racing_analogs/`
- [ ] Any new files added to `src/` that aren't tracked?

### 2. Supabase State
- [ ] Count `velo_verdicts` rows — is live pipeline running?
- [ ] Check `raceform` count — is backfill complete?
- [ ] Verify `fingerprint_signal_summary` has recent entries
- [ ] Check `shadow_log` table exists (or not)

### 3. Live System State
- [ ] Any new entries in `velo_verdicts` since last session?
- [ ] Any new columns added to `velo_verdicts` schema?
- [ ] Has `velo_prime_ensemble.py` been modified?
- [ ] Has `sqpe.py` been modified?

### 4. Sidecar State
- [ ] Does `/tmp/states_12m_seq.pkl` still exist?
- [ ] Any new modules in `src/v13/racing_analogs/`?
- [ ] Are cron jobs still running?
- [ ] Any new Supabase errors in recent runs?

### 5. Security
- [ ] Any exposed keys in recent git commits?
- [ ] Supabase service key rotated recently?
- [ ] Any new API keys or credentials added to `.env`?

---

## Monthly Audit Checklist

### Schema Changes
- [ ] Any new columns in `velo_verdicts`? Document them.
- [ ] Any new tables in Supabase?
- [ ] Any schema drift between code and actual Supabase tables?

### Architecture
- [ ] Have any live files been modified?
- [ ] Are there any new files in `src/intelligence/`?
- [ ] Has the 13-feature locked set been maintained?

### Performance
- [ ] Shadow mode query time still acceptable (<5 min for 200 runners)?
- [ ] Historical index build time still acceptable (<30s for 171K states)?
- [ ] Any memory issues with the 12-month pickle file?

### Data Quality
- [ ] Feature fill rates still reasonable?
- [ ] Any new data quality issues in raceform?
- [ ] Any gaps in the historical backfill?

---

## What to Do When Something Drifts

1. Document the drift in this file
2. Create a new audit entry in `docs/system_audits/YYYY-MM-DD_audit.md`
3. Update MASTER_STATE.md immediately
4. Do NOT assume — verify

---

## Audit Log

| Date | Auditor | Findings | Actions |
|------|---------|----------|---------|
| 2026-04-08 | Hermes-Prime | Initial audit — SQPE bridge complete, sidecar operational | Cron scheduled, key rotation pending |
