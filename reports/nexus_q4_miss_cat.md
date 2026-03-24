# NEXUS Q4 — miss_category / miss_evidence Readers

**Query:** What reads `miss_category` and `miss_evidence`? What reads `velo_post_race_reviews`? Does `miss_category` drive scoring, tier assignment, or learning rate?

---

## 1. `miss_category` — What Reads It?

**Result: NOTHING in the codebase reads `miss_category`.**

`miss_category` is only written by one script — `backfill_miss_evidence.py`. No consumer reads it.

| File | Line(s) | Action | Detail |
|------|---------|--------|--------|
| `scripts/backfill_miss_evidence.py` | 27 | Defines options | `# miss_category options:` |
| `scripts/backfill_miss_evidence.py` | 34, 52, 71, 94, 112, 130, 151 | Writes | `"miss_category": "<value>"` in backfill logic |
| `scripts/backfill_miss_evidence.py` | 173 | Reads (pre-write check) | `.select("id, race_id, miss_category")` — only to skip already-categorised rows |
| `scripts/backfill_miss_evidence.py` | 184–185 | Reads | `row.get("miss_category")` — skip-if-present guard |
| `scripts/backfill_miss_evidence.py` | 189, 195, 203 | Writes | Writes `miss_category` into `velo_post_race_reviews` |
| `supabase/migrations/20260322_004_miss_category_evidence.sql` | 6, 10–11 | DDL | `ADD COLUMN miss_category TEXT` + `COMMENT ON COLUMN` |

**No other Python module, service, or script reads `miss_category`.**

---

## 2. `miss_evidence` — What Reads It?

**Result: NOTHING in the codebase reads `miss_evidence`.**

Same story — only written by `backfill_miss_evidence.py`.

| File | Line(s) | Action | Detail |
|------|---------|--------|--------|
| `scripts/backfill_miss_evidence.py` | 35, 53, 72, 95, 113, 131, 152 | Writes | `"miss_evidence": { ... }` JSONB blobs |
| `scripts/backfill_miss_evidence.py` | 196 | Writes | Writes `miss_evidence` into `velo_post_race_reviews` |
| `supabase/migrations/20260322_004_miss_category_evidence.sql` | 7, 13–14 | DDL | `ADD COLUMN miss_evidence JSONB` + `COMMENT ON COLUMN` |

**No consumer reads `miss_evidence`.**

---

## 3. `velo_post_race_reviews` — What Reads This Table at All?

`velo_post_race_reviews` is read by two scripts. Neither reads `miss_category` or `miss_evidence`.

### `scripts/velo_morning_cockpit.py` — Line 116
```python
rows = (db.table("velo_post_race_reviews")
        .select("race_id, outcome, miss_reason, verdict_confidence, decision_tier, review_outcome, created_at")
        ...
```
Selected columns: `race_id`, `outcome`, `miss_reason` (legacy), `verdict_confidence`, `decision_tier`, `review_outcome`, `created_at`.  
**`miss_category` and `miss_evidence` are NOT selected.**

### `scripts/feed_sigma_loop.py` — Line 88
```python
review_rows = (
    db.table("velo_post_race_reviews")
    .select(
        "verdict_id, race_id, top_pick_won, top_pick_placed, top_pick_position, "
        "actual_winner_id, actual_winner_sp, verdict_accuracy_score, review_outcome"
    )
    ...
```
Selected columns: `verdict_id`, `race_id`, `top_pick_won`, `top_pick_placed`, `top_pick_position`, `actual_winner_id`, `actual_winner_sp`, `verdict_accuracy_score`, `review_outcome`.  
**`miss_category` and `miss_evidence` are NOT selected.**

### `velo_post_race_reviews` Writers

| File | Line(s) | Action |
|------|---------|--------|
| `scripts/close_sigma_loops.py` | 1292 | `db.table("velo_post_race_reviews").upsert(review, on_conflict="verdict_id")` — writes via `generate_review()` at line 339 |
| `scripts/backfill_miss_evidence.py` | 193 | Updates rows: sets `miss_category`, `miss_evidence`, `learning_ready` |

**Key finding:** `generate_review()` in `close_sigma_loops.py` (line 339) does NOT populate `miss_category`, `miss_evidence`, or `learning_ready`. Those fields are added only by the `backfill_miss_evidence.py` one-shot script.

---

## 4. Does `miss_category` Alter Scoring, Tier Assignment, or Learning Rate?

**No. `miss_category` has zero downstream impact on any active code path.**

Evidence:
- No active scoring pipeline (`run_prime_today.py`, `velo_prime_service.py`) references `miss_category`.
- No tier assignment code (`decision_tier` in `run_results_sigma.py`, `run_prime_today.py`, `velo_morning_cockpit.py`) reads `miss_category`.
- No learning rate logic (`src/learning/genesis_protocol.py`, `src/memory/velo_memory.py`, `src/intelligence/sqpe.py`, `scripts/continuous_training.py`) reads `miss_category`.
- The only code that reads `miss_category` is `backfill_miss_evidence.py` itself, and only as a skip-guard (line 184: `if row.get("miss_category"):`).

---

## Summary

| Field | Written By | Read By | Active in Scoring? | Used for Tier/LR? |
|-------|-----------|---------|-------------------|-------------------|
| `miss_category` | `backfill_miss_evidence.py:195` | **None** | No | No |
| `miss_evidence` | `backfill_miss_evidence.py:196` | **None** | No | No |
| `learning_ready` | `backfill_miss_evidence.py:197` | **None** | No | No |

**Conclusion:** `miss_category`, `miss_evidence`, and `learning_ready` are ghost fields — populated by a backfill script but never consumed by any active pipeline. They exist in the schema but are inert. The new miss taxonomy (`market_decoy_followed`, `genuine_blind_spot`, `data_gap`) is not yet wired into scoring, tier assignment, or the learning system.
