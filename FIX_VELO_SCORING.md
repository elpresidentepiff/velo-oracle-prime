# VELO SCORING PIPELINE — FIX RUN

## Goal
Fix three production issues and verify the pipeline end-to-end.

---

## ISSUE 1: velo_verdicts.region column missing

The `region` column doesn't exist in `velo_verdicts`. This must be added before the next scoring run or region filtering breaks.

**Run in Supabase SQL Editor (supabase.com/dashboard → SQL Editor → New Query):**

```sql
ALTER TABLE public.velo_verdicts ADD COLUMN IF NOT EXISTS region TEXT DEFAULT '' NOT NULL;
```

Click **Run**. Verify with:
```sql
SELECT column_name, data_type FROM information_schema.columns WHERE table_name = 'velo_verdicts' AND column_name = 'region';
```
Expected: `region | text`

---

## ISSUE 2: Railway cron times are wrong

velo-prime-scoring fires at **09:33 UTC** — this is halfway through the UK race day (07:00–20:00 UTC). Should be **06:00 UTC**.

In Railway dashboard (railway.app → project focused-dream):

1. Go to **velo-prime-scoring** service → **Settings** → **Cron**
2. Change cron expression from `33 9 * * *` (or whatever it shows) to: `0 6 * * *`
3. Save

Similarly for **velo-results-sigma** (if it exists as a separate cron): `0 22 * * *`

---

## ISSUE 3: UK/IRE filter may not be deployed

**Check which branch Railway is watching:**

In Railway dashboard → velo-prime-scoring → **Settings** → **Deploy**:

Look at the **Branch** field. Options:
- If it says `main` → Railway IS getting the latest pushes. Redeploy to pick up the UK/IRE filter.
- If it says `feature/v10-launch` → Railway is on a divergent branch. The UK/IRE filter (on `main`) is NOT deployed.

**If Railway watches `main`:**
1. In Railway dashboard → velo-prime-scoring → **Deploy** → click **Redeploy** (or push a dummy commit to trigger)
2. Verify: after redeploy, check pipeline_runs shows `environment=production` for the next run

**If Railway watches `feature/v10-launch`:**
Merge `main` into `feature/v10-launch` on the Windows machine:
```bash
git checkout feature/v10-launch
git merge origin/main
git push origin feature/v10-launch
```
Then redeploy in Railway dashboard.

---

## ISSUE 4: Backfill missing sigma_audits

7 races from today (2026-03-23) have no sigma_audits — Racing API returned 404 for those races at close time.

**Run locally on Windows:**
```bash
cd C:\path\to\velo-oracle-prime
git checkout main
git pull origin main
python scripts/close_sigma_loops.py --date 2026-03-23
```

Or on Railway: redeploy velo-results-sigma to pick up the latest code, then run the backfill.

---

## VERIFICATION QUERIES

After all fixes, run these to confirm:

**1. Migration applied:**
```sql
SELECT column_name FROM information_schema.columns WHERE table_name = 'velo_verdicts' AND column_name = 'region';
```

**2. velo_verdicts has region data after next scoring run:**
```sql
SELECT race_id, region, velo_prime_prob, decision_tier, generated_at FROM velo_verdicts ORDER BY generated_at DESC LIMIT 10;
```
All rows should have `region='GB'` or `region='IRE'`. No nulls, no France.

**3. sigma_audits have dates:**
```sql
SELECT race_id, date, track, outcome, decision_tier FROM sigma_audits ORDER BY created_at DESC LIMIT 10;
```
All rows should have `date` and `track` populated (not NULL).

**4. Pipeline health:**
```sql
SELECT service_name, status, started_at, environment, races_processed FROM pipeline_runs ORDER BY started_at DESC LIMIT 5;
```
Next velo-prime-scoring run should show `environment=production` (not `local`).

---

## FILES THAT SHOULD BE ON MAIN (verified by VOX)

- `scripts/run_prime_today.py` — UK/IRE filter at lines 455-458
- `scripts/close_sigma_loops.py` — sigma_audits date fix via `_get_race_record()`
- `app/services/velo_prime_service.py` — region field persisted in `persist_race_predictions()`

---

## WHAT NOT TO CHANGE

- Do NOT modify `src/intelligence/velo_prime_ensemble.py` — scoring model is working
- Do NOT modify `app/services/model_manager.py` — SQPE v17 is working
- Do NOT touch the learned_patterns table directly — sigma loop manages it
