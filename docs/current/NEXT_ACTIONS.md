# NEXT_ACTIONS.md — Ordered Roadmap

## Required order

1. **Accept / close VFU-12 if clean.** Per `docs/current/ONE_TRUTH.md` and
   `docs/current/VFU_INDEX.md`, VFU-12 (Sigma Pattern Tribunal) is already recorded
   as COMPLETE with 3 patterns on a dry-run watchlist only — no live doctrine
   promoted. Operator to confirm this remains accepted as-is.
2. **Complete DOCS-01.** This mission — the documentation spine in `docs/current/`.
   Status: this file is part of that completion.
3. **Open VFU-13 — False-GREEN Feature Autopsy** — **BLOCKED pending numbering
   resolution.** `ONE_TRUTH.md` already records VFU-13 to VFU-19 as COMPLETE
   (contamination catches). The next VFU work should not silently reuse "VFU-13" —
   an agent must not resolve this itself (that would be inventing a decision the
   operator hasn't made). Options for the operator: (a) name it VFU-22 (following
   VFU-21, which is itself not started — see below), or (b) explicitly confirm
   "VFU-13" is intentionally being reused as a new phase name distinct from the
   historical VFU-13-19 group. Flagged in `docs/current/VFU_INDEX.md` and
   `docs/current/CURRENT_STATE.md`.
4. **Plan Knowledge Graph only after evidence objects are clean.** Not started.
   Depends on VFU-21 (awaiting VCP-00 Truth Lock completion) and the outcome of
   item 3 above.

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

Do not start VFU-13 (or its renamed successor) inside a documentation-only
mission. DOCS-01 was mapping/governance only — no live scoring, no Supabase
writes, no Telegram, no model promotion occurred while producing this spine.
