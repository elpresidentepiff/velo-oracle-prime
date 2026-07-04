# COURSE-01 Design Spec

## Mission: Draw and Pace Shadow Feature Registry

REPORT_ONLY design spec. NOT IMPLEMENTED.
Status: DESIGN_SPEC_ONLY — COURSE-01 implementation pending VCP-03 completion.

---

## Objective

Create shadow-only draw/pace/course-position features that can explain
mid-price misses without affecting live scoring. All fields are shadow-only
until promotion gates are met.

---

## Shadow fields to add

- `shadow_draw_pos` — runner's stall draw (integer, from RP racecard)
- `shadow_draw_bias_flag` — 1 if draw matches bias direction for this course+distance, else 0
- `shadow_draw_bias_side` — "favoured" / "unfavoured" / "neutral" / "unknown"
- `shadow_front_runner_flag` — 1 if runner is classified as front-runner pace type
- `shadow_pace_map_position` — "lead" / "prominent" / "hold-up" / "unknown"
- `shadow_aw_surface` — fibresand / polytrack / tapeta / n/a (from static registry)
- `shadow_circuit_type` — sharp / galloping / undulating / flat_straight / unknown
- `shadow_run_in_f` — run-in furlongs float (from static registry)
- `shadow_uphill_finish` — yes / no / unknown (from static registry)
- `shadow_sprint_chute` — yes / no / unknown (from static registry)

---

## Data ingestion plan

- Source 1: draw available in RP racecard (runner.draw) — already parsed via rp_account_collector
- Source 2: course static profiles — _COURSE_EYES registry (this script)
- Source 3: draw bias lookup table by course+distance — built from _COURSE_EYES
- Source 4: pace proxy — derive from in-running comments post-race (partial coverage only)

---

## Promotion requirements

- n >= 300 prospective shadow race validation
- Course-specific sample gates (n >= 50 per course before course-level inference)
- False-green guard: no silent improvement (shadow correlation must be audited against control)
- No direct score change without VCP-03 completion and VFU review
- Operator decision required at each promotion gate

---

## What this does NOT do

- Does not change sqpe_v17_prob
- Does not change vp score
- Does not affect sigma output
- Does not affect live model weights
- Does not affect Supabase tables
- Does not trigger VFU-21 or VCP-04

---

## Build order (when authorised)

1. Draw ingestion from RP racecard parser (shadow field only)
2. Static course registry join (course+distance -> draw_bias_side)
3. Shadow draw_bias_flag computation
4. Pace proxy from post-race comment parser (shadow only)
5. Shadow feature validation table (n >= 300 before review)
6. Operator review gate
7. If approved: promote to scoring with VFU-21 protocol

---

## Status

DESIGN_SPEC_ONLY — COURSE-01 implementation pending VCP-03 completion.
NO_COURSE_01_IMPLEMENTATION constraint active.
