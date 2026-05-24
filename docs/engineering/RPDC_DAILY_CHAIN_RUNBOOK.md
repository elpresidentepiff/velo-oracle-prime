# RPDC Daily Chain Runbook

**Prepared:** 2026-05-24  
**Classification:** DAILY_OPERATIONS / RPDC_OPTION_B_BRIDGE / NO_SUPABASE_MIGRATION  
**Hard constraint:** Each step runs in order. No step skipped. FEATURE_DEGRADED banner mandatory until improvement_score variance is restored.

---

## Chain Overview

The RPDC daily chain is a sequence of scripts that must run in a specific order.
Each step depends on the previous step's output.

```
YESTERDAY'S EVENING                        TODAY'S MORNING
─────────────────                          ───────────────
results_YYYY_MM_DD.json                    racecard_merged/ files (RP pipeline)
        │                                          │
        ▼                                          ▼
ingest_results_to_horse_runs.py         build_rpdc_daily.py
        │                                          │
        ▼                                          ▼
racing_horse_runs (Supabase)            runner_release_candidates (Supabase)
                                                   │
                                                   ▼
                                          run_prime_today.py
                                                   │
                                                   ▼
                                         velo_verdicts + runner_snapshots
                                                   │
                         ┌─────────────────────────┘
                         ▼
TODAY'S EVENING: run_results_sigma.py → sigma_audits (Supabase)
                         │
                         ▼
                  audit_rpdc_tag_value.py (local reports)
                         │
                         ▼
             ingest_results_to_horse_runs.py (feeds tomorrow)
```

---

## Step 0 — RPDC Preflight (run before morning scoring)

**When:** Morning, before `run_prime_today.py`  
**What:** Check RPDC chain health for today's date.

```bash
source venv/bin/activate
PYTHONPATH=. python scripts/ops/build_rpdc_daily.py --date $(date +%Y-%m-%d) --preflight-only
```

**If RPDC_SOURCE_UNAVAILABLE:**
- No card has been scored yet, or RP merged racecards not generated
- This is normal early in the morning — scoring creates the card
- Proceed with scoring; RPDC will annotate from Option B local JSONL

**If RPDC_CHAIN_OK:**
- runner_release_candidates rows exist for today
- RPDC tags will be attached at scoring time

---

## Step 1 — Morning scoring

**When:** Morning (Railway cron 06:00 UTC or manual)  
**What:** Score today's card using the current VP formula.

```bash
source venv/bin/activate
PYTHONPATH=. python scripts/ops/run_prime_today.py
```

**FEATURE_DEGRADED banner (mandatory until improvement_score variance restored):**

If the following appears in the scoring output, the banner must be reported to
Mission Control and Telegram (not via picks — via status):

```
FORMULA_STATUS: FEATURE_DEGRADED
improvement_score: EXCLUDED (constant 0.0872, zero-variance kill switch)
ACTIVE_COMPONENTS: market_deception_score, sqpe_v17
```

This banner is NOT a failure. It is honest status reporting.

**Do not suppress this banner. Do not claim full formula is running.**

---

## Step 2 — RPDC annotation check

**When:** Immediately after scoring completes  
**What:** Verify RPDC Option B bridge is annotating runners correctly.

```bash
source venv/bin/activate
PYTHONPATH=. python scripts/audit_rpdc_memory_for_card.py --date $(date +%Y-%m-%d)
```

Output: `data/reports/rpdc_memory_card_coverage_{date}.md`

Check:
- match_rate ≥ 50% → GOOD
- match_rate 30–50% → MODERATE (acceptable)
- match_rate < 30% → LOW — check horse name format in racecard source

---

## Step 3 — Evening: sigma (after results close)

**When:** After all races result (typically 18:00–20:00 local)  
**What:** Download results and audit all predictions.

```bash
# Step 3a: Scrape results (Racing API dead — use Sporting Life)
source venv/bin/activate
PYTHONPATH=. python scripts/ops/scrape_results_sl.py --date $(date +%Y-%m-%d)

# Step 3b: Run sigma
PYTHONPATH=. python scripts/ops/run_results_sigma.py --date $(date +%Y-%m-%d)
```

**If sigma fails with 401:** Racing API is dead. Run scraper first (Step 3a), then retry sigma.
**If sigma fails with "no results file":** Scraper didn't run. Run Step 3a.
**NEVER use `close_sigma_loops.py`** — always use `run_results_sigma.py`.

Sigma outputs:
- Telegram Sigma Report (locked format — do not change)
- sigma_audits rows written to Supabase
- `data/sigma_results/sigma_results_{date}.json`

---

## Step 4 — Ingest results into racing_horse_runs

**When:** After sigma (same evening)  
**What:** Write today's results into Supabase racing_horse_runs for tomorrow's RPDC build.

```bash
source venv/bin/activate
PYTHONPATH=. python scripts/ops/ingest_results_to_horse_runs.py --date $(date +%Y-%m-%d)
```

**Safe to re-run** — upsert on (race_id, horse_id). No duplicates created.  
**Does NOT touch velo_verdicts** — immutable audit trail is not affected.  
**Does NOT trigger scoring** — results ingest only.

Verify:
```bash
PYTHONPATH=. python -c "
import os, urllib.request, json
sb_url = os.getenv('SUPABASE_URL', '')
sb_key = os.getenv('SUPABASE_SERVICE_KEY', '') or os.getenv('SUPABASE_SERVICE_ROLE_KEY', '')
import datetime
d = str(datetime.date.today())
req = urllib.request.Request(
    f'{sb_url}/rest/v1/racing_horse_runs?race_date=eq.{d}&select=count',
    headers={'apikey': sb_key, 'Authorization': f'Bearer {sb_key}', 'Accept': 'application/vnd.pgrst.object+json', 'Prefer': 'count=exact'}
)
with urllib.request.urlopen(req, timeout=10) as r:
    print('Rows for today:', r.headers.get('Content-Range', 'unknown'))
"
```

---

## Step 5 — RPDC tag value audit update

**When:** After sigma, after ingest  
**What:** Refresh the RPDC tag value report with today's closed result.

```bash
source venv/bin/activate
set -a && source .env && set +a
PYTHONPATH=. python scripts/audit_rpdc_tag_value.py
```

Output: `data/reports/rpdc_tag_value_latest.json` and `.md`

Review the per-tag SR/Frame metrics. Check if STABLE_WARM or CYCLE_RUN_2 are
accumulating towards the promotion gates in `RPDC_SHADOW_LANES_V1.md`.

---

## Step 6 — Tomorrow's RPDC build

**When:** After Step 4 (results ingested). Run in evening or early morning.  
**What:** Build RPDC tags for tomorrow's runners using updated racing_horse_runs.

```bash
source venv/bin/activate
PYTHONPATH=. python scripts/ops/build_rpdc_daily.py --date $(date -d "tomorrow" +%Y-%m-%d)
```

On WSL, if `date -d` is not available:
```bash
PYTHONPATH=. python -c "
from datetime import date, timedelta
print((date.today() + timedelta(days=1)).strftime('%Y-%m-%d'))
" | xargs -I{} python scripts/ops/build_rpdc_daily.py --date {}
```

**If RPDC_SOURCE_UNAVAILABLE for tomorrow:** No runners are known yet (no racecard).
This is normal — rerun in the morning after RP merged racecards are generated.

---

## Step 7 — Mission Control update

**When:** After sigma  
**What:** Update Mission Control chain status.

```bash
source venv/bin/activate
PYTHONPATH=. python scripts/ops/update_mission_control.py
```

Mission Control should show (when FEATURE_DEGRADED):
```json
"rpdc_chain": {
  "status": "OPTION_B_LOCAL_MEMORY",
  "formula_status": "FEATURE_DEGRADED",
  "improvement_score_constant": true,
  "improvement_score_value": 0.0872,
  "active_components": ["market_deception_score", "sqpe_v17"]
}
```

---

## FEATURE_DEGRADED state — learning gate

When `improvement_score` is excluded (zero-variance kill switch fires):

```
LEARNING_BLOCKED:      YES
FULL_FORMULA_CLAIM:    PROHIBITED
DEGRADED_CARD_LABEL:   MUST appear in any scoring output summary
```

A degraded card is NOT used to update Playbook G or learning patterns.
The sigma run still proceeds — the outcome is recorded but the card is
classified as evidence from a FEATURE_DEGRADED engine.

---

## RPDC Option B maintenance

The local JSONL does not need daily rebuilds. It is a static snapshot.

To extend the JSONL to include new scored dates:

```bash
source venv/bin/activate
PYTHONPATH=. python scripts/backfill_rpdc_historical_local.py
```

This rebuilds from all available results files. Safe to re-run. No Supabase write.

---

## Error handling

| Error | Action |
|---|---|
| `RPDC_SOURCE_UNAVAILABLE` | Normal early-morning state. Proceed with scoring. RPDC annotates from local JSONL. |
| `sigma fails 401 Racing API` | Run `scrape_results_sl.py --date` first. |
| `ingest fails conflict` | Safe — upsert handles conflicts. Check row count to confirm. |
| `build_rpdc_daily fails` | Check racing_horse_runs has rows for the previous date. If not, run ingest first. |
| `kill switch fires on improvement` | Report FEATURE_DEGRADED status. Do not suppress. Do not change formula. |
| `RPDC match rate < 30%` | Check racecard source. RP merged racecards may have horse name format issues. |

---

## What this chain does NOT do

```
CHANGES_LIVE_VP_FORMULA:          NO
CHANGES_FORMULA_WEIGHTS:          NO
MUTATES_OLD_VERDICTS:             NO
APPROVES_SUPABASE_MIGRATION:      NO
APPROVES_NINE_DATE_INGEST:        NO
APPROVES_RPDC_AS_LIVE_SIGNAL:     NO — shadow only until promoted
```

---

## Classification

```
CHAIN_STATUS:              OPTION_B_LOCAL_MEMORY_BRIDGE
SUPABASE_MIGRATION:        NOT_APPROVED
SCORING_FORMULA_CHANGE:    NONE
FEATURE_DEGRADED_STATE:    YES (improvement_score excluded)
LEARNING_BLOCKED:          YES (degraded card)
RPDC_SIGNAL_STATE:         SHADOW_ONLY
DAILY_MAINTENANCE:         ZERO (JSONL static snapshot)
```
