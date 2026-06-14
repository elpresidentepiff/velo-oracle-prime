# JTC-D WIRING PLAN — SIDECAR ONLY

**Date:** 2026-06-10 · Status from live audit: **JTC_D_PARTIAL** (auditor: `scripts/ops/audit_jtcd_profile_bank.py`).

## What it is
~494k profile rows: trainer×course (82k), trainer×dist (91k), jockey×course (75k), jockey×dist (67k), trainer×jockey combo (179k) — each with wins/runs/raw_sr/adj_sr/confidence/jtc_signal.

## Audit result (June 10 card)
Trainers 183/204 (90%) · courses 4/5 (Kempton "(AW)" suffix — fixed by normalizer) · combos 202/281 (72%). The historic blockers dissolve: profiles key on **names** (course_id moot), dist maps to bands at attach time.

## Wiring (3 steps, all sidecar)
1. **Attach** at scoring time via the same normalizer family as `rpdc_attach` (suffix-stripping, whitespace): add `jtcd_trainer_course_signal`, `jtcd_combo_signal`, `jtcd_confidence` to the top-pick payload — **stored, never weighted** (same pattern as BHA badges).
2. **Suppress** low-sample joins using the existing `confidence` column (n<10 → null).
3. **Evidence loop**: after 30+ days, slice sigma outcomes by jtc_signal bands — promotion discussion only via the standard gates.

## Guards
No live weight · no score change · per-date rebuilds must lag one day (leakage) · IRE courses partially covered (Limerick unmatched — note in attach status).
