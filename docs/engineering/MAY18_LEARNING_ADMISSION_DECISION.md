# MAY 18 LEARNING ADMISSION DECISION

**Date:** 2026-05-18  
**Status:** HOLD — PENDING OPERATOR APPROVAL  
**Classification:** VALID_PARTIAL_SIGMA_AFTER_REPAIR | BASELINE_MODEL_RESULT | GUARDED_LEARNING_REVIEW_REQUIRED | NO_AUTO_CONSUME

---

## Why the Original Sigma Was Invalid

May 18 Sigma ran on a broken identity contract. Commit `1dc8d5b` introduced synthetic RP horse IDs in `_load_rp_profile_as_racecards()` using `.lower()` only, preserving spaces from the ALL-CAPS `horse_norm` parquet column:

```
'IMPERIAL GUARD'.lower() → 'imperial guard'
RP_ prefix → 'RP_imperial guard'   ← SPACE IN ID
```

The result scraper used `re.sub(r"[^a-z0-9]", "", name.lower())` which strips spaces:

```
'Imperial Guard' → 'imperialguard'
RP_ prefix → 'RP_imperialguard'    ← NO SPACE
```

Sigma strict equality failed for every multi-word horse name. Of 34 predictions:
- **7 evaluated** — only the 7 single-word names where spaces don't matter
- **24 classified NR-ABSENT** — actually identity failures, not non-runners
- **3 genuine absent** — tier X races not in result file

That sigma was rejected under classification `MAY18_SIGMA_INVALID_SAMPLE`.

---

## What Was Fixed

**Commit `dc33a5e`** — one line in `run_prime_today.py` line 236:

```python
# Before (bug — spaces preserved):
horse_norm_val = str(row.get("horse_norm") or row.get("horse") or "").lower()

# After (fix — spaces stripped):
horse_norm_val = _norm_horse_name(row.get("horse_norm") or row.get("horse") or "")
```

`_norm_horse_name()` was already defined at line 808:
```python
def _norm_horse_name(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(name or "").lower())
```

**Commit `7d0c9c5`** — sigma normalised-ID fallback (`_sid_norm()`) for existing spaced-ID records in Supabase. No predictions overwritten.

**15/15 regression tests** pass in `tests/test_rp_synthetic_id_normalisation.py`.

---

## Post-Fix Sigma Coverage

Sigma rerun `2026-05-18` with normalised matcher:

| Metric | Value |
|---|---|
| Total predictions | 34 |
| Matched in result file | 29 |
| True NR/DNF (excluded) | 2 |
| No result / Tier X absent | 3 |
| **Evaluated** | **29** |
| **Strike rate** | **17.2% (5/29)** |
| **Frame rate** | **41.4% (12/29)** |
| Identity failures recovered | 22 |
| Identity failures remaining | 0 |
| sigma_audits rows written | 28 |

**Verdict: AT BASELINE — not an anomalous collapse, not an anomalous positive.**

---

## Eligible Row Count

Audit script: `scripts/audit_may18_learning_eligibility.py`  
Artifact: `data/reports/may18_learning_eligibility_audit.json`

| Category | Count | Race IDs |
|---|---|---|
| **Learning eligible** | **28** | All WIN/MISS/PLACED reconciled |
| Excluded — Tier X | 4 | CRL_400, Lingfield_350, Windsor_610, Windsor_640 |
| Excluded — True NR/DNF | 2 | Lingfield_250 (High Favour), ROS_650 (Rising Sky) |
| Excluded — No result | 0 | — |
| Excluded — Identity residual | 0 | — |

---

## Excluded Row Count

| Reason | Count | Explanation |
|---|---|---|
| Tier X | 4 | Permanently excluded from sigma and learning |
| True NR/DNF | 2 | Genuine non-finishers (position=DNF in result) |
| No result | 0 | Tier X races classified before no-result check |
| Identity failure | 0 | Zero after normalisation fix |

**Total excluded: 6 of 34**

---

## Learning Engine Gate Assessment

The learning engine (`app/services/learning_engine.py`) correctly gates on `sigma_audits` presence. Only races with a sigma_audits row can generate learning events. Since sigma_audits contains exclusively the 28 WIN/MISS/PLACED reconciled rows, no patching was required:

- NR/DNF races → not written to sigma_audits by sigma script → excluded
- No-result races → not in sigma_audits → excluded
- Tier X races → blocked from sigma_audits in step 6 → excluded

**No patch needed to learning engine (Task 2).**

---

## Whether May 18 Can Enter Shadow

Yes, after operator approval, with the following constraints:

1. Only the 28 reconciled rows enter shadow training.
2. The 2 NR/DNF rows must never be included.
3. The 4 Tier X rows must never be included.
4. No row with `consumed_live=True` is permitted.
5. `target_state = shadow_full_train_v2` (not live state, not rollback state).

**Events built and staged (not consumed):**
- `velo_learning_events` May 18: 28 rows written
- `consumed_shadow = False` on all 28
- `consumed_live = False` on all 28
- `learning_allowed = True` on all 28
- `sentient_state_touched = False`
- `playbook_g_promoted = False`
- `playbook_g_consumed = False`

---

## Whether May 18 Should Be Treated as Baseline Day

Yes. SR=17.2% is within the 49-day global baseline of 20.6% — within normal session variance. Frame rate 41.4% is below the 48.4% average, consistent with a baseline-to-weak day.

May 18 is **not** a negative outlier that should trigger model review. It was a baseline-quality day behind a broken infrastructure identity contract. The infrastructure is now fixed.

---

## No Live Promotion Rule (Permanent)

```
NO_LIVE_PROMOTION          = TRUE (unconditional)
NO_PLAYBOOK_G_PROMOTION    = TRUE (until paper ledger n>=20)
NO_SCORING_CHANGE          = TRUE
NO_MODEL_CHANGE            = TRUE
NO_ROUTER_CHANGE           = TRUE
NO_STAKING_CHANGE          = TRUE
NO_EOD_CONSUME             = TRUE (until operator approves)
NO_SHADOW_CONSUME          = TRUE (until operator approves)
```

---

## Commit Reference

| Commit | Content |
|---|---|
| `99130ba` | Forensics investigation — May 18 reconciliation failure |
| `5ed34e0` | Forensics artifacts — regression proof table, commit audit |
| `dc33a5e` | **Fix** — RP synthetic ID normalisation, 15 regression tests |
| `7d0c9c5` | **Sigma patch** — normalised-ID fallback (Option A) |

---

## Operator Decision Required

Do not consume May 18 shadow until Presidente explicitly approves.

Action on approval:

```bash
source venv/bin/activate && PYTHONPATH=. python workers/velo_ops_worker.py learn-shadow \
  --date 2026-05-18 \
  --execute \
  --target-state shadow_full_train_v2 \
  --allow-warn
```

This will consume the 28 staged events into shadow state. It will NOT promote Playbook G. It will NOT touch live state.
