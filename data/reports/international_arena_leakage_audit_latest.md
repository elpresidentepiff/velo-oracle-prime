# International Arena Leakage Audit

**Generated:** 2026-05-23T20:03:05.050659+00:00
**Verdict:** REVIEW_REQUIRED
**Arena features audited:** 21

---

## Summary

| Status | Count | Features |
|---|---|---|
| KEEP (confirmed safe) | 13 | age_num, dist_f, draw_num, draw_pct, field_size, going_code, is_aw, or_num, or_vs_field, rpr_num, rpr_vs_field, ts_num, wgt_lbs |
| DROP (post-race/leakage) | 0 | — |
| UNKNOWN_REVIEW (timing unconfirmed) | 8 | class_num, course_fit_score, distance_fit_score, going_fit_score, mark_compression_score, runs_since_place, runs_since_win, trainer_timing_score |

---

## Dropped Arena Features

| Feature | Decision | Reason |
|---|---|---|
| — | — | — |

## Features Requiring Review

| Feature | Decision | Issue |
|---|---|---|
| class_num | UNKNOWN_REVIEW | timing unconfirmed |
| course_fit_score | UNKNOWN_REVIEW | timing unconfirmed |
| distance_fit_score | UNKNOWN_REVIEW | timing unconfirmed |
| going_fit_score | UNKNOWN_REVIEW | timing unconfirmed |
| mark_compression_score | UNKNOWN_REVIEW | timing unconfirmed |
| runs_since_place | UNKNOWN_REVIEW | timing unconfirmed |
| runs_since_win | UNKNOWN_REVIEW | timing unconfirmed |
| trainer_timing_score | UNKNOWN_REVIEW | timing unconfirmed |

## Confirmed Safe Features

| Feature | Decision | Basis |
|---|---|---|
| age_num | KEEP | confirmed pre-race |
| dist_f | KEEP | confirmed pre-race |
| draw_num | KEEP | confirmed pre-race |
| draw_pct | KEEP | confirmed pre-race |
| field_size | KEEP | confirmed pre-race |
| going_code | KEEP | confirmed pre-race |
| is_aw | KEEP | confirmed pre-race |
| or_num | KEEP | confirmed pre-race |
| or_vs_field | KEEP | confirmed pre-race |
| rpr_num | KEEP | confirmed pre-race |
| rpr_vs_field | KEEP | confirmed pre-race |
| ts_num | KEEP | confirmed pre-race |
| wgt_lbs | KEEP | confirmed pre-race |

---

## Why Results Are Suspicious

AUC=0.95 and SR=80%+ exceeds typical racing model benchmarks. Fit scores (course_fit_score, going_fit_score, distance_fit_score, trainer_timing_score) may be computed using the current race's result if not properly time-gated. These features have 0.10-0.13 target correlation. If time-gate is clean, their combination with RPR (corr=0.37) could legitimately produce high AUC — but 0.95 warrants shuffle test confirmation.

**Primary suspect:** `course_fit_score, going_fit_score, distance_fit_score, trainer_timing_score`

**Secondary concern:** class_num null rate 42% — zero-fill may create a spurious signal

**Confirmed clean:** rpr_vs_field (corr=0.367), rpr_num (corr=0.267) — pre-race ratings, expected to be clean

---

## Next Steps

1. Run shuffle test (`audit_international_arena_sanity.py`) — definitively confirms/denies leakage
2. Run safe arena (`audit_international_baseline_arena_safe.py`) — results using only confirmed pre-race features
3. Investigate fit score time-gating in source code before using in any model

---

```
LEAKAGE_AUDIT_STATUS:  REVIEW_REQUIRED
ARENA_VERDICT_HOLD:    YES — do not promote until sanity + safe arena pass
MIGRATION_STATUS:      NOT_RUN
WORKER_STATUS:         BLOCKED
```
