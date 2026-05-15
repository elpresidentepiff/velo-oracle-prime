# MAY 15 EOD READINESS RUNBOOK

## Status

```
State: HOLDING — waiting for May 15 race results
Results: WAITING
Sigma: NOT READY
EOD: BLOCKED
```

Do not run EOD until this runbook clears all gates.

---

## Gate 1 — Results Exist

```bash
# Check if results file exists and is non-empty
ls data/results_2026_05_15.json 2>/dev/null || echo "MISSING"
python3 -c "
import json
d = json.load(open('data/results_2026_05_15.json'))
races = d.get('results', d) if isinstance(d, dict) else d
print(f'Races: {len(races)}')
"
```

**Gate pass:** File exists AND contains > 0 races.
**If missing:** Wait for results. Do not proceed.

---

## Gate 2 — Sentinel Not BLOCK

```bash
source venv/bin/activate && PYTHONPATH=. python workers/velo_ops_worker.py healthcheck \
  --date 2026-05-15 --target-state shadow_full_train_v2 2>/dev/null
# Or run Mission Control:
PYTHONPATH=. python scripts/velo_mission_control.py --date 2026-05-15
```

**Gate pass:** Sentinel classification = SAFE or WARN.
**If BLOCK:** Fix the blocking condition. Do not proceed.
**Typical WARN reasons:** repo_dirty (runtime files), runbook_docs_dirty — acceptable with `--allow-warn`.

---

## Gate 3 — Run Sigma First

```bash
source venv/bin/activate && PYTHONPATH=. python scripts/run_results_sigma.py --date 2026-05-15
```

**Sigma must complete before EOD.** EOD calls sigma internally, but running it standalone first
confirms result quality and populates `sigma_audits` rows.

**Gate pass:** Sigma exits 0 AND reports at least 1 sigma row written.
**If sigma fails:** Diagnose the failure. Do not run EOD.
**Expected output:** "Sending Telegram..." → SKIP (Telegram disabled). "Done. N sigma rows."

Note: Telegram is disabled. The sigma script may log a warning about Telegram. This is expected.

---

## Gate 4 — Sigma Audits Confirmed

```bash
source venv/bin/activate && PYTHONPATH=. python -c "
import os; os.environ.setdefault('PYTHONPATH', '.')
from dotenv import load_dotenv; load_dotenv('.env')
from app.services.ops_service import OpsService
ops = OpsService(dry_run=True, execute=False)
resp = ops._get_sb().client.table('sigma_audits').select('race_id', count='exact').eq('date', '2026-05-15').execute()
print(f'sigma_audits for 2026-05-15: {resp.count}')
"
```

**Gate pass:** `sigma_audits` count > 0.
**If zero:** Sigma ran but wrote nothing — investigate sigma output. Do not run EOD.

---

## Gate 5 — Target State Confirmed

```bash
echo $VELO_SHADOW_TARGET
# If not set, default will be used — confirm default is correct
```

**Required target:** `shadow_full_train_v2`
**Never:** `shadow_full_train_v1` (contaminated — Sentinel BLOCK)

---

## Gate 6 — Live State Hash Unchanged

```bash
python3 -c "
import hashlib, pathlib
p = pathlib.Path('data/sentient_state.json')
if p.exists():
    h = hashlib.sha256(p.read_bytes()).hexdigest()[:12]
    print(f'live hash: {h}')
else:
    print('sentient_state.json: NOT FOUND')
"
```

Record this hash before EOD. The EOD command checks it post-run automatically.
**Gate pass:** Hash matches what Sentinel pre-run report recorded.

---

## Gate 7 — Cloud Backup Unchanged

The Sentinel checks this automatically. No manual step required.
If `consumed_live_true_at_preflight` appears, STOP.

---

## Gate 8 — Official Predictions Not To Be Overwritten

The May 15 prediction artifact already exists: `data/velo_prime_verdicts_2026_05_15.json`

**Do not run `predict --execute` again.** Sentinel will BLOCK it (`prediction_overwrite_risk`).
EOD does not re-run predict — it runs sigma → learn-shadow build → consume → healthcheck.

---

## Gate 9 — Telegram Disabled

Telegram token is not rotated. Telegram is disabled.
Sigma and EOD may log Telegram errors — this is expected and non-blocking.
Do not attempt to send Telegram messages manually.

---

## EOD Command (only after all gates pass)

```bash
source venv/bin/activate && PYTHONPATH=. python workers/velo_ops_worker.py daily-eod \
  --date 2026-05-15 \
  --execute \
  --allow-network \
  --target-state shadow_full_train_v2 \
  --allow-warn
```

`--allow-warn` is required because `repo_dirty` and `approved_shadow_target` (for sigma sub-call)
will fire WARN.

The Sentinel BLOCK condition `approved_shadow_target` fires on `daily-eod` because `learning_requested=True`
and the sub-call to sigma uses the shared target which is `shadow_full_train_v2`. This will classify
as WARN (not BLOCK) only if all BLOCK conditions are clear.

Wait — the approved_shadow_target check BLOCKs only if `learning_requested=True AND target != shadow_full_train_v2`.
With `--target-state shadow_full_train_v2`, this check should PASS. Verify before running.

---

## Stop Conditions (abort EOD immediately if any fire)

| Condition | Action |
|---|---|
| `[SENTINEL BLOCK]` appears | Stop. Fix the blocking condition. |
| `[HARD STOP] sentient_state.json hash changed` | Stop. Investigate. |
| `[HARD STOP] Cloud backup updated_at changed` | Stop. Investigate. |
| `[HARD STOP] consumed_live=True detected` | Stop. Investigate. |
| Sigma exits non-zero inside EOD | EOD stops automatically. Diagnose sigma. |
| `SIGMA_RESULTS_NOT_READY` in EOD output | Results not yet in sigma_audits. Rerun sigma first. |

---

## Expected Artifacts After Successful EOD

| Artifact | Location |
|---|---|
| Daily EOD report | `data/phase4_daily_reports/2026-05-15_daily_eod_report.json` |
| Learning events | `velo_learning_events` rows for 2026-05-15, target=shadow_full_train_v2 |
| Shadow state updated | `data/sentient_state_shadow_full_train_v2.json` (race count incremented) |
| Ops worker dry-run artifacts | `data/ops_worker_dry_run/2026-05-15_*.json` |

---

## Post-EOD Checks

```bash
# 1. Verify shadow state grew
python3 -c "
import json
d = json.load(open('data/sentient_state_shadow_full_train_v2.json'))
print(f'shadow races: {d.get(\"total_races_observed\")}')
"

# 2. Verify live state unchanged
python3 -c "
import hashlib, pathlib
p = pathlib.Path('data/sentient_state.json')
h = hashlib.sha256(p.read_bytes()).hexdigest()[:12]
print(f'live hash after: {h}')
"
# Must match the hash from Gate 6.

# 3. Check consumed_live is still zero
# (Sentinel pre-flight on next command will confirm this)
```

---

## Version History

| Version | Date | Notes |
|---|---|---|
| V1 | 2026-05-15 | Initial May 15 EOD runbook. Pre-race. Waiting for results. |
