# Step 2 — Wire Horse State Brain into Live Scoring
Created: 2026-04-05

## Objective

Inject the Horse State Brain into the live scoring path so every runner gets a full raw horse-state object, a compact summary, and persisted output that can be queried and audited.

This step does not change ranking. It adds state to the organism so later layers can reason on it.

---

## Success Criteria

At the end of this step:

1. `score_race_velo_prime()` produces horse-state tags for every runner
2. Each runner's full state is stored in `full_analysis`
3. Top-level `velo_verdicts` contains compact queryable state for the top/promoted horse(s)
4. Persistence is migration-safe — if new DB columns do not exist, scoring still succeeds
5. No change to weighted ensemble behavior
6. No change to TIE gate behavior

---

## Execution Order

### 1. Find the insertion point

**File:** `app/services/velo_prime_service.py`
**Function:** `score_race_velo_prime(...)`

**Insert after:**
- Ensemble predictions are computed
- Flattened into runner rows

**Insert before:**
- Final persist / velo_verdicts write
- Any future gate/archetype application

Horse states should describe the scored runner in context, not raw pre-scoring input and not post-persist output.

---

### 2. Add Horse State Brain import

**File:** `app/services/velo_prime_service.py`

Import the state engine from `src/intelligence/horse_state_engine.py`.

Use the field-level tagging entrypoint: `HorseStateEngine.tag_field(...)`.

---

### 3. Build the input payload for state tagging

`HorseStateEngine.tag_field()` should receive the already-scored runners. Each runner payload should include at minimum:

**Per-runner fields:**
- `horse`, `horse_id`, `race_id`
- `velo_prime_prob`, `sqpe_v17_prob`, `place_prob`
- `market_deception_score`, `longshot_prob`
- `sp_dec`, `is_fav`, `draw_num`, `field_size`, `class_num`
- `days_since_run`, `class_delta` (if present)
- Horse history derived fields already in the row
- Any market/support fields already present

**Race context:**
- race id, course, distance, going, field size, race type/class, date/time

Goal: the state engine reasons on the same live context the ensemble just used.

---

### 4. Attach full raw state object to every runner

For each returned runner row, attach a full nested structure:

```python
row["horse_state"] = {
    "readiness_state": ...,
    "release_state": ...,
    "rest_pattern": ...,
    "class_move_state": ...,
    "stable_heat": ...,
    "jockey_signal": ...,
    "market_state": ...,
    "race_fit_state": ...,
    "chaos_exposure": ...,
    "signal_count": ...,
    "signals": [...],
}
```

This must live inside the per-runner output that gets stored in `full_analysis`.

**Rule:** Do not flatten everything immediately. Keep the full raw state object intact — that is the inspectable brain.

---

### 5. Create compact queryable summary for top horse

At the race verdict level, add compact summary fields for the top selection.

**Suggested top-level fields on `velo_verdicts`:**

```
top_horse_readiness_state      text
top_horse_release_state        text
top_horse_rest_pattern         text
top_horse_class_move_state     text
top_horse_stable_heat          text
top_horse_jockey_signal        text
top_horse_market_state         text
top_horse_race_fit_state       text
top_horse_chaos_exposure       text
top_horse_signal_count         integer
top_horse_signals              text[]
```

**Rule:** The compact summary is for querying and dashboards. The full raw state remains in `full_analysis`. If there is a promoted horse, extend this pattern later. For now, top horse is enough.

---

### 6. Add DB migration for compact horse-state columns

**Migration file:** `supabase/migrations/20260405_002_velo_verdicts_horse_state.sql`

Follow the same pattern as prior migrations. Add all compact top-horse state columns listed above.

---

### 7. Make persistence fallback-safe

**File:** `app/services/velo_prime_service.py` — where the `velo_verdicts` upsert happens.

Follow the same fallback pattern already used for observability columns:

```
If horse-state columns do not exist:
  - log warning
  - drop only the new compact top-level horse-state columns
  - keep full_analysis intact
  - still persist verdict successfully
```

**Rule:** Scoring must never fail because migration has not run.

---

### 8. Add visible marker inside full_analysis

Each runner item in `full_analysis` must clearly contain `horse_state` — not mixed across unrelated keys, not silently omitted. Queryable by loading one verdict row and inspecting runner items.

---

### 9. Post-wire verification

After wiring, verify with one fresh scored race:

| Check | Test |
|---|---|
| Check 1 | Each runner in `full_analysis` contains `horse_state` |
| Check 2 | Top-level `velo_verdicts` contains compact state fields, or logs fallback warning if migration not applied |
| Check 3 | `velo_prime_prob`, `decision_tier`, active ensemble membership are unchanged |

This step is state injection only, not behavior change.

---

## Pass/Fail Checks

**PASS if:**
- Fresh verdict rows include runner-level `horse_state`
- Compact top-horse state is queryable
- Scoring still succeeds if migration absent
- No ranking drift caused by state injection

**FAIL if:**
- State only exists in memory and not persisted
- Compact state is missing and not recoverable
- Scoring breaks when migration absent
- State wiring mutates ensemble ranking logic

---

## What NOT to Do in This Step

- Do not wire TIE v3 into decisioning yet
- Do not build archetypes yet
- Do not alter `_WEIGHTS`
- Do not change SQPE
- Do not add new models
- Do not convert horse states into probabilities
- Do not collapse the raw state into only a summary

---

## Deliverables

Claude should finish this step with:

1. Code wired in `score_race_velo_prime()`
2. Migration file added (`supabase/migrations/20260405_002_velo_verdicts_horse_state.sql`)
3. Fallback-safe persist logic
4. One verification note showing a fresh verdict row shape
5. Exact keys confirmed present in:
   - `full_analysis[*].horse_state`
   - Top-level `velo_verdicts`

---

## One-Line Instruction

> Wire `HorseStateEngine` into live scoring after ensemble and before persist, store full raw per-runner `horse_state` in `full_analysis`, store compact top-horse state in top-level `velo_verdicts` with migration-safe fallback, and do not change ranking behavior yet.

---

## What Comes After This Step

| Step | Task |
|---|---|
| Step 3 | Wire TIE v3 gate after horse states are flowing |
| Step 4 | Build 5 race archetypes (Structure, Compression, Prep/Release, Public Trap, Chaos) |
| Step 5 | Post-race truth loop — record miss type, state truth, archetype truth, gate truth |
