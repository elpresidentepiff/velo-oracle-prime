# VÉLØ Persistence Rule
> Non-negotiable. A race day is not complete unless all three outputs exist.

---

## The Rule

**A race-day run is COMPLETE only when ALL THREE are true:**

```
1. Suggestions generated (local JSON written)
2. Suggestions sent to Telegram
3. Suggestions persisted to Supabase — velo_verdicts table
```

If any one is missing: **RUN = INCOMPLETE.**

---

## System of Record Hierarchy

| System | Role | System of Record? |
|---|---|---|
| Supabase `velo_verdicts` | Cloud persistence — truth | YES — primary |
| Local JSON `data/velo_verdicts_YYYY_MM_DD.json` | Backup / debug | NO |
| Telegram messages | User alerts | NO |
| Console output | Debug only | NO |

**Local JSON is NOT the system of record.**
**Telegram is NOT the system of record.**
**Supabase is the system of record.**

---

## Supabase Persistence Requirements

After each race verdict is generated, `persist_race_predictions()` must be called.

Target table: `velo_verdicts`
Date field: `generated_at`
Required columns: `race_id`, `generated_at`, `engine_version`, `velo_prime_prob`, `full_analysis`

After the full card run:
- Row count in `velo_verdicts` for today must equal races generated
- If counts do not match: run is INCOMPLETE, Telegram must receive FAIL alert

---

## Persistence Verification

After every race-day run, execute:
```bash
python scripts/post_run_persistence_check.py
```

This script compares expected races (local JSON count) vs actual Supabase rows.
If counts do not match, it exits non-zero and triggers a Telegram FAIL alert.

---

## Failure Handling

If Supabase persistence fails for any race:
1. Log the failure with exact race_id and error
2. Continue generating remaining verdicts (do not abort)
3. After the full run, send Telegram PERSISTENCE FAIL alert with deficit count
4. Run `post_run_persistence_check.py` — will report FAIL
5. Investigate and re-persist from local JSON if needed

**Never suppress persistence errors.** A silent failure is worse than a loud one.

---

## INC-0003 Lesson

On 2026-03-17: 37 verdicts were generated and sent to Telegram. Only 1 was persisted to Supabase.
Root cause: `run_todays_races.py` called the 5-agent orchestrator directly but never called `persist_race_predictions()`.
The persist function existed and was correct but was never wired into the daily script.

This rule exists to prevent that failure from recurring.

---

*Created: 2026-03-17. This rule is permanent. Do not remove persistence calls from any race-day script.*
