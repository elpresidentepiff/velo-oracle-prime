# Phase 2 Handover — Shadow Lab Operational
**Date:** 2026-04-09
**Status:** COMPLETE
**Agent:** Hermes Prime
**Branch:** `shadow-lab`

---

## What Was Built

### Shadow Lane Infrastructure

1. **`scripts/shadow_lab.py`** (428 lines)
   - Follower lane, not a scorer
   - Watermark-based consumption of production verdicts
   - G shadow evaluation (ported from production code)
   - Top-3 rank movement analysis
   - Audit logging per row
   - All writes to shadow tables only

2. **Shadow tables in Supabase:**
   - `public.shadow_watermarks` — idempotency state
   - `public.shadow_audit_log` — per-row processing log
   - `public.velo_shadow_results` — G shadow results
   - `public.velo_shadow_rank_movement` — rank movement analysis

3. **Railway service: `velo-shadow-lab`**
   - Branch: `shadow-lab`
   - Cron: `30 9 * * 1-6` (09:30 UTC Mon-Sat)
   - Deployment: `440cc7e8` (SUCCESS)

---

## Verified Working

- Shadow lab processed 96 rows end-to-end locally
- All 4 shadow tables populated correctly
- Watermark advanced to `2026-04-09T06:25:51`
- Railway `velo-shadow-lab` deployed SUCCESS
- Production scoring confirmed unaffected (still at 06:25)

---

## G State Note

Current G output: `G_TOO_FEW_RACES` for all rows
- G is underpopulated in `learned_patterns` (0 races observed)
- Shadow multiplier is 1.0 neutral — correct fallback
- G will become informative once Supabase `learned_patterns` is populated from real scoring

---

## What Remains

1. **Populate G state** — once real scoring runs accumulate, G state in `learned_patterns` will evolve and G shadow signals will become substantive
2. **Analog comparison** — port analog matching from local scripts to shadow_lab
3. **RLS policies** — RLS not yet applied to shadow tables (Anthropic key exposure concern — needs separate key setup)
4. **Promotion gate** — shadow must prove value over ≥2 weeks before any promotion discussion

---

## Credentials

All Supabase keys were rotated 2026-04-09 after exposure in chat. New keys stored in Railway project vars. Rotate immediately if any further exposure occurs.

---

## File Locations

| File | Path |
|------|-------|
| Shadow lab entrypoint | `scripts/shadow_lab.py` |
| Shadow tables migration | `supabase/migrations/20260409_001_shadow_lab_tables.sql` |
| Railway service | `velo-shadow-lab` (ID: `b772d439-be21-4a02-9d46-4c79c7bf2ede`) |
| Master state | `docs/live_state/MASTER_STATE.md` |
| Split spec | `docs/system_audits/RAILWAY_SPLIT_SPEC.md` |
| This handover | `docs/agent_handoffs/2026-04-09_phase2_shadow_lab_handover.md` |

---

## Next Agent Instructions

- Do NOT push any G/sentient/analog code to `main`
- Shadow lab evolves on `shadow-lab` only
- When G state is populated, shadow lab output will transition from `G_TOO_FEW_RACES` to real doctrine signals
- Monitor `velo_shadow_results` and `velo_shadow_rank_movement` for signal emergence
- Production is protected. Shadow is free. Follow the split spec.
