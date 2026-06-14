# JTC-D Profile Bank Audit — 2026-06-10

**Status: JTC_D_PARTIAL** · 494,540 profile rows · generated 2026-06-10T22:39:02.218204+00:00

Coverage on card: trainers 183/204 · jockeys 148/164 · courses 5/5 · combos 202/281

Blockers:
- course_id_mapping: MOOT — profiles key on names, not IDs; '(AW)' suffix handled by normalizer
- dist_f_format: dist_band strings in profiles; map card dist_f to bands at attach time
- leakage: lifetime aggregates; per-date rebuild must lag by one day (guard documented)
- min_sample: use confidence column (already computed) — suppress n<10 joins

SIDECAR ONLY — no live weight, no score change.