# NEXT_ACTIONS.md — Ordered Roadmap

## Required order

1. **Accept / close VFU-12 if clean.** Per `docs/current/ONE_TRUTH.md` and
   `docs/current/VFU_INDEX.md`, VFU-12 (Sigma Pattern Tribunal) is already recorded
   as COMPLETE with 3 patterns on a dry-run watchlist only — no live doctrine
   promoted. Operator to confirm this remains accepted as-is.
2. **Complete DOCS-01.** This mission — the documentation spine in `docs/current/`.
   Status: this file is part of that completion.
3. **VFU-22 — False-GREEN Feature Autopsy** — **COMPLETE**. Merged PR #137
   (`4f789b1`). 6 of 16 GREEN days (37.5%) confirmed false-green;
   `CONFIDENCE_FLOOD_FALSE_GREEN` class identified. See
   `data/reports/vfu_22_false_green_feature_autopsy.md`.
3a. **VFU-23 — Confidence Flood Retrospective Diagnostic** — **COMPLETE**. Merged
   PR #138 (`797cdef`). Reproduces the VFU-22 false-green set 6/6 with zero
   extras; 21 tests pass. See `docs/current/CONFIDENCE_FLOOD_DIAGNOSTIC.md`.
3b. **VFU-24 — Confidence Flood Root-Cause Split** — IN PROGRESS (opened
   2026-07-06 per operator formal dispatch, following VFU-23). Splits the six
   confirmed false-green days into root-cause subtypes: 4
   `GAP_COLLAPSE_FALSE_GREEN`, 2 `HEALTHY_GAP_FALSE_GREEN` (both also carrying
   `THRESHOLD_FLOOD_FALSE_GREEN`). Task contract: `ops/task_contracts/VFU-24.json`.
   Branch: `vfu-24-confidence-flood-root-cause-split`. Proposes no cure, no
   gate change — see `docs/current/CONFIDENCE_FLOOD_ROOT_CAUSE_SPLIT.md`.
4. **Plan Knowledge Graph only after evidence objects are clean.** Not started.
   Depends on VFU-21 (awaiting VCP-00 Truth Lock completion) and VFU-24 closing
   clean.

## Postponed lanes (not started, no artifacts exist yet)

These are named in the DOCS-01 mission spec as postponed. No repo evidence exists
for any of them yet — do not assume partial progress:

- Latent Race Concept Layer
- Knowledge Graph
- Hybrid RAG Memory
- TurboVec Benchmark
- SQL Forensic Audit
- Security Sentinel
- Market Intelligence Agent
- Media Stack
- Race-State Simulation

## Also outstanding (from ONE_TRUTH.md, not part of the required order above)

- **VCP-00 Truth Lock** — IN PROGRESS as of 2026-06-29.
- **VCP-03 Ten-Day Coherence Burn-In** — 1/10 days as of last recorded entry in
  `data/reports/vcp_03_burn_in_log.md` (check current count before assuming more
  days have passed; this index does not re-derive that count).
- **VCP-04 Shadow Judgment** — NOT STARTED, requires 10 passing burn-in days +
  operator sign-off.
- **VFU-21** — NOT STARTED, awaiting VCP-00 completion.

## Hard rule for whoever picks this up

DOCS-01 was mapping/governance only — no live scoring, no Supabase writes, no
Telegram, no model promotion occurred while producing this spine. VFU-22 (the
work formerly proposed as VFU-13) is a separate mission opened after DOCS-01
merged (PR #136) and the operator's numbering ruling. VFU-13 itself is dead —
never resurrect that number for new work.
