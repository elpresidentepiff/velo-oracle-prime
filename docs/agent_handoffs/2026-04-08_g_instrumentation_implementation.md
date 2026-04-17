# Handover — G Instrumentation Implementation
**Date:** 2026-04-08
**Status:** INSTRUMENTATION COMPLETE — migration required to activate

---

## What Was Built

Three instrumentation components to capture real G data for proper evaluation:

### 1. Doctrine Fire Capture
**Problem:** Doctrine strengths are simulated (~0.0) because `doctrines_fired` was never captured.
**Fix:** `_g_shadow_adjustment` now returns `doctrine_fired` (list of doctrine names).

**New return values:**
```python
def _g_shadow_adjustment(...) -> tuple[float, list[str], list[str], str]
#                                           ^flags  ^doctrine_fired  ^pain_horse_id
```

Doctrine names now tracked:
- `PAIN_RULE` — specific horse + high MPI situation
- `LAY_THE_STORY` — narrative trap doctrine
- `SHADOW_TRACKING` — high-SP miss doctrine
- `NARRATIVE_FRACTURE` — narrative disruption doctrine
- `FAVOURITE_LIABILITY` — favourite with high MDS

### 2. Per-Runner G Shadow Fields

New fields added to `VeloPrimePrediction` dataclass:
- `g_shadow_horse_id: str` — horse_id that triggered pain rule (if any)
- `doctrines_fired: list` — list of doctrine names that fired

These appear in `to_dict()` output and are available for persistence.

### 3. Top-3 Scoring for Rank Movement Analysis

**Problem:** Top-1 winner-flip metric is too blunt. Can't measure:
- Did G demote a bad favourite from 1st to 3rd?
- Did G improve 2nd/3rd ordering?
- Did G reduce decoy exposure?

**Fix:** Build `top3_scores` JSONB per race:
```python
{
  "horse_id": "hrs_XXXXX",
  "velo_prime_prob": 0.3621,    # AFTER G adjustment
  "g_base_prob": 0.3621,         # BEFORE G adjustment
  "g_shadow_multiplier": 0.85,    # G multiplier applied
  "g_adjusted_prob": 0.3078,     # base × multiplier
  "g_shadow_flags": [...],
  "doctrines_fired": ["PAIN_RULE"],
  "is_top_pick": True
}
```

This enables:
- Rank movement: did 2nd-pick become 1st after G adjustment?
- Favourite suppression: did G reduce favourite's adjusted probability?
- Decoy reduction: did G demote decoy candidates?
- Shortlist quality: did G improve top-3 shape?

---

## Files Changed

| File | Change |
|------|--------|
| `src/intelligence/velo_prime_ensemble.py` | `_g_shadow_adjustment` returns `doctrine_fired` + `pain_horse_id`. New dataclass fields `g_shadow_horse_id`, `doctrines_fired`. |
| `app/services/velo_prime_service.py` | Added `top3_scores` construction. Added G shadow columns to row + optional column groups. |
| `supabase/migrations/20260408_005_velo_verdicts_g_shadow_instrumentation.sql` | New migration — adds G shadow columns + indexes. |

---

## Migration Required

**File:** `supabase/migrations/20260408_005_velo_verdicts_g_shadow_instrumentation.sql`

**To apply:**
```bash
# Option 1: Supabase Dashboard > SQL Editor > paste migration
# Option 2: supabase db push
# Option 3: Railway cron job runs this on startup
```

**Columns added:**
- `g_shadow_multiplier FLOAT`
- `g_shadow_flags TEXT[]`
- `g_shadow_horse_id TEXT`
- `g_shadow_mode TEXT`
- `g_top3_scores JSONB`

**Indexes:**
- `idx_velo_verdicts_g_shadow_mult` — find races where G suppressed
- `idx_velo_verdicts_g_shadow_horse` — find races where G flagged a horse
- `idx_velo_verdicts_g_pain_rule` — find races where pain rule fired

**Graceful degradation:** If migration not applied, G shadow columns are stripped via the existing optional column groups mechanism. Scoring continues normally.

---

## Next Measurement Layer (after migration + 1 week live)

Once `g_top3_scores` has ~50+ races of live data, run this comparison:

```
For each race:
  1. Base top-3: top3 before G (g_base_prob)
  2. Shadow top-3: top3 after G (g_adjusted_prob)

  Metrics:
    - Rank movement: count of races where rank order changed
    - Favourite suppression: delta on is_fav runner's adjusted prob
    - Decoy reduction: delta on market_decoy flagged runner
    - Shortlist quality: did top-3 still contain the winner post-G?
    - Frame-to-win: did the frame (top G-adjusted) win more often?
```

---

## Hard Constraints Maintained

- NO live promotion of G
- NO changes to velo_prime_prob computation
- NO oracle layer work
- Shadow-only: `_G_SHADOW_MODE` still controls whether multiplier is applied

---

## What This Unlocks

| Before | After |
|--------|-------|
| Doctrine strengths = simulated (~0.0) | Doctrine strengths = real (from `doctrines_fired` capture) |
| Top-1 winner metric only | Rank movement + shortlist quality metrics |
| Pain rules unverified in live | Pain rules verified via `g_shadow_horse_id` |
| No visibility into G activity | Full visibility via `g_shadow_flags` array |
