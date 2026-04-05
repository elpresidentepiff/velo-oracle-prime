# VELO Status Map and Rebuild Plan
Created: 2026-04-05

---

## Mission

Turn VELO from a cleaned scoring spine into a true horse-state decision organism.

**The rule from now on is simple:** No new additive model enters live unless it proves lift. New intelligence should first appear as state, gate, archetype, or truth-loop logic — not ensemble clutter.

---

## 1. What VELO Is Right Now

### Live core — the real engine

These are the only proven live components that should currently influence the weighted ensemble:

| Component | Status | Notes |
|---|---|---|
| SQPE v17 | LIVE | Main ranking backbone |
| Place model | LIVE | Proven lift over SQPE-only |
| Market Deception | LIVE | Marginal but real lift over SQPE+Place |
| Longshot | LIVE (conditional) | Only when SP gate applies |

### Explicitly not in the weighted ensemble

| Component | Status | Reason |
|---|---|---|
| Improvement | DISABLED | Proved harmful to top-1 |
| Release Window | DISABLED | Dead — missing real signal flow |
| Comment Intel | DISABLED | Dead — missing real signal flow |
| TIE (v1/v2) | DISABLED | Failed as additive probability component |
| Benter | NOT LIVE | Not wired |

**Current plain-English truth:**
> Live VELO is: SQPE + Place + Market Deception + conditional Longshot. That is the proven spine.

---

## 2. What Has Been Proven

### SQPE
- SQPE is the strongest real ranking model in the system
- SQPE v18 did not beat v17 — days_since_run and class_delta did not help ranking
- **Decision: SQPE v17 stays live. SQPE v18 is HOLD.**

### Place model
- SQPE+Place materially improves top-1 over SQPE-only. It stays.

### Market Deception
- Small but real additive lift over SQPE+Place. It stays.

### Improvement model
- Proven harmful. It is cut.

### Release Window and Comment Intel
- Dead / constant in live behavior. Disabled.

### TIE v1 and v2
- Both failed as scoring components
- **Conclusion: TIE must be a gate/filter, not a weighted probability model**

---

## 3. Where the Brain Is

### Brain Layer 1 — Built
**Horse State Brain** (`src/intelligence/horse_state_engine.py`)

Purpose: compute explicit horse-state tags, make reasoning auditable, stop treating horses as just score rows.

Current tags:
- `readiness_state`
- `release_state`
- `rest_pattern`
- `class_move_state`
- `stable_heat`
- `jockey_signal`
- `market_state`
- `race_fit_state`
- `chaos_exposure`

These are not probabilities. They are state descriptors that playbooks and gates can reason over.

### Brain Layer 2 — Partially Built
**TIE v3 Gate** (`src/intelligence/tie_v3_gate.py`)

Role: not a scorer, not in `_WEIGHTS`. Sits after scoring, before final action/tiering.

Intended jobs:
- Promote C→B or D→C when state and intent align
- Add EW/playable flag
- Rescue prepared horses from over-suppression
- Act as watchlist / conviction confirmation

**Validated backtest results (2024 / 2025):**

| Cohort | 2024 | 2025 | Verdict |
|---|---|---|---|
| Upgrade (4+ signals) | 1.50x place lift | 1.49x place lift | LIFT confirmed |
| EW (3+ signals + SP>8) | 1.25x place lift | 1.23x place lift | MARGINAL |

Threshold = 4 is validated. Gate is not disproven.

---

## 4. Where the Playbooks Are

### Current reality
Playbooks are mostly still: tiering logic, suppression logic, chaos routing, action rules. They are not yet the full organism-level archetype system.

### What must exist next
Playbooks must become race archetype operators. Build exactly these 5 archetypes first:

1. **Structure** — strong pace shape, dominant form, expected outcome
2. **Compression** — compressed market, trainer-backed move, class drop
3. **Prep/Release** — explicit horse-state prep signals, deliberate placement
4. **Public Trap** — false favourite, over-bet runner, market distortion
5. **Chaos** — field instability, unexplained market moves, unknown quantity

Each archetype must define:
- Allowed action types
- Suppression behavior
- Promotion rules
- Trap logic
- What state tags matter most

---

## 5. Where RPD/RDPC Tagging Is

RPD/RDPC-style horse tagging is partially present but not fully alive in live decisions. The actual bridge now is the **Horse State Brain**. Do not try to revive old tagging mythology directly. Instead:

1. Make per-horse state explicit
2. Persist it
3. Use it in gates and archetypes
4. Learn from its truth post-race

That is how the tagging layer becomes real.

---

## 6. Current System Status

| Layer | Status |
|---|---|
| SQPE v17 | LIVE |
| Place model | LIVE |
| Market Deception | LIVE |
| Longshot (conditional) | LIVE |
| Scoring + tiering pipeline | LIVE |
| Observability columns (active/excluded) | LIVE — migration applied |
| Horse State Brain | BUILT — not yet wired into live scoring |
| TIE v3 Gate | BUILT — threshold=4 validated — not yet wired |
| SQPE v18 | HOLD — no lift demonstrated |
| TIE v1/v2 | DISABLED |
| Improvement/Release/Comment | DISABLED |
| Race archetypes | NOT BUILT |
| Post-race truth loop | NOT BUILT |

---

## 7. The Rebuild Doctrine

**Rule 1** — No new additive model enters live unless it proves lift against the current proven core.

**Rule 2** — State comes before score. If the system cannot describe the horse's condition/state, it is not yet intelligent.

**Rule 3** — TIE is a gate, not a scorer.

**Rule 4** — Playbooks must reason on archetypes and horse states, not just raw thresholds.

**Rule 5** — Every new layer must have a post-race truth test.

---

## 8. Next Session — Exact Execution Order

### Step 1 — Backtest validated (DONE this session)
`scripts/backtest_tie_v3_gate.py` rewritten. Upgrade cohort 1.50x/1.49x confirmed. EW cohort marginal (1.25x/1.23x). Threshold=4 proven.

### Step 2 — Wire Horse State Brain into scoring
Wire `HorseStateEngine.tag_field()` into `score_race_velo_prime()`:
- After ensemble scoring
- Before final persist
- Before gate/archetype logic

Persist full raw state object per runner in `full_analysis`, compact summary for top/promoted horses.

### Step 3 — Horse-state persistence migration
Add DB columns for compact horse-state observability in `velo_verdicts`. Same migration + graceful fallback pattern as observability columns. Scoring must never block if columns are missing.

### Step 4 — Scaffold the 5 archetypes
Build v1 of: Structure, Compression, Prep/Release, Public Trap, Chaos. Use explicit logic based on horse states, separation, market context, chaos exposure, gate outputs.

### Step 5 — Post-race truth loop
Build a truth audit that records: core miss type, horse-state tag truth, archetype truth, gate truth. This is where the organism starts learning from its own errors.

---

## 9. What VELO Must Become

**Not this:**
- Another additive score pile
- Another weak specialist
- More decorative architecture
- More mythology than measurement

**This — a horse-state decision organism:**
- Proven scoring spine (SQPE + Place + Market Deception)
- Explicit per-horse state brain (Horse State Engine)
- Intent gate as permission logic (TIE v3)
- Race archetype playbooks (5 archetypes)
- Post-race truth loop

---

## 10. Final Directive

> We do not need to throw VELO away. We need to animate the spine we proved.
>
> The spine is: SQPE + Place + Market Deception
>
> The next brain organs are: Horse State Brain → TIE v3 Gate → Archetypes → Truth Loop
>
> No new clutter. No new mythology. No pretending.
> Build the brain above the proven spine.
