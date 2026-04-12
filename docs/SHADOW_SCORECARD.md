# VÉLØ Shadow Scorecard
**Purpose:** Weekly measurement spec for shadow-lab branch validation.
**Window:** 2026-04-12 → 2026-05-12 (30 days). Extend to 2026-06-12 if any metric is inconclusive.
**Rule:** Do not promote to live until every GATE column below reads PASS. Do not change model weights while measurement is running.

---

## 1. Tier Fire Rates

Expected healthy distribution based on 500-row baseline. Run weekly.

| Tier | Target range | Current (baseline) | GATE |
|------|-------------|-------------------|------|
| A-STRIKE | 8–14% | 15.9% | WATCH — elevated |
| B-PLAYABLE | 15–25% | 18.0% | PASS |
| C-WATCH | 20–35% | 28.6% | PASS |
| X-CHAOS | 10–20% | 22.4% | PASS |
| D-NO BET | 5–12% | 6.2% | PASS |

A-tier above 14% for two consecutive weeks → investigate gate before promoting.

**Query:**
```sql
SELECT
    decision_tier,
    COUNT(*) AS races,
    ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (), 1) AS pct
FROM velo_verdicts
WHERE generated_at >= '2026-04-12'
GROUP BY decision_tier
ORDER BY races DESC;
```

---

## 2. Hit Rates by Tier (primary signal quality check)

Minimum sample per tier: 20 verified outcomes before reading as reliable.

| Tier | Win% target | Frame% target | GATE condition |
|------|-------------|---------------|---------------|
| A-STRIKE | ≥ 35% | ≥ 60% | FAIL if win% < 28% for ≥ 20 outcomes |
| B-PLAYABLE | ≥ 18% | ≥ 40% | FAIL if win% < 13% for ≥ 30 outcomes |
| C-WATCH | ≥ 12% | ≥ 30% | Informational only |
| X-CHAOS | < 15% (gate is working) | — | FAIL if X wins at > 20% (gate too aggressive) |
| D-NO BET | < 12% | — | Informational only |

Baseline (30-day pre-shadow): A win 43.2%, all-tier win 25%.

**Query:**
```sql
SELECT
    v.decision_tier,
    COUNT(s.race_id)                                                             AS outcomes,
    ROUND(AVG(CASE WHEN s.outcome = 'WIN' THEN 1.0 ELSE 0.0 END) * 100, 1)     AS win_pct,
    ROUND(AVG(CASE WHEN s.outcome IN ('WIN','PLACED') THEN 1.0 ELSE 0.0 END) * 100, 1) AS frame_pct,
    ROUND(AVG(v.velo_prime_prob)::numeric, 4)                                   AS avg_prob
FROM velo_verdicts v
JOIN sigma_audits s USING (race_id)
WHERE v.generated_at >= '2026-04-12'
GROUP BY v.decision_tier
ORDER BY v.decision_tier;
```

---

## 3. Suspect Cohort — A-tier weak-place

**Definition:** `decision_tier = 'A' AND place_prob < 0.75`
**Flag column:** `a_tier_weak_place_flag = TRUE`
**Promoted to gate:** 2026-05-12 if sample ≥ 30 outcomes.

| Metric | Threshold | Action |
|--------|-----------|--------|
| Flagged win% | < 30% | Raise A-gate `prob` floor to 0.35 for `place_prob < 0.75` |
| Flagged win% | ≥ 35% | Keep gate, raise suspect threshold to `place_prob < 0.65` |
| Flagged frame% | < 45% | Same as above — act on both together |
| Clean (place ≥ 0.75) win% drops below 38% | | Re-examine place model — not an A-gate issue |
| Sample < 30 | | Extend to 2026-06-12, do not act |

**Query:**
```sql
SELECT
    v.a_tier_weak_place_flag,
    COUNT(s.race_id)                                                             AS outcomes,
    ROUND(AVG(CASE WHEN s.outcome = 'WIN' THEN 1.0 ELSE 0.0 END) * 100, 1)     AS win_pct,
    ROUND(AVG(CASE WHEN s.outcome IN ('WIN','PLACED') THEN 1.0 ELSE 0.0 END) * 100, 1) AS frame_pct,
    ROUND(AVG(v.velo_prime_prob)::numeric, 4)                                   AS avg_prob,
    ROUND(AVG(v.place_prob)::numeric, 4)                                        AS avg_place,
    ROUND(AVG(v.market_deception_score)::numeric, 4)                            AS avg_mkt_dec
FROM velo_verdicts v
JOIN sigma_audits s USING (race_id)
WHERE v.decision_tier = 'A'
  AND v.generated_at >= '2026-04-12'
GROUP BY v.a_tier_weak_place_flag
ORDER BY v.a_tier_weak_place_flag;
```

---

## 4. strong_escape Cohort Performance

**Definition:** Rows where `prob >= 0.18 AND place >= 0.35` escaped X-CHAOS.
These horses would have been suppressed under the old gate — now they get a tier.
This cohort validates whether `strong_escape` is rescuing real horses or noise.

| Metric | GATE |
|--------|------|
| strong_escape win% ≥ X-CHAOS baseline (< 15%) | PASS — escape is worthwhile |
| strong_escape win% < 10% | FAIL — escape is noise, tighten conditions |
| strong_escape tier distribution | Should land mostly B/C, not A |

Note: `strong_escape` is computed in `synthesize_decision()` but not yet stored as a column.
Add `top["strong_escape_fired"]` flag in `run_prime_today.py` when this cohort exceeds 50 rows.

---

## 5. Blocker Validation

**Blockers:** `horse_state_failed`, `macro_context_failed`, `single_runner`.
These force X-CHAOS — track whether they suppress winners or protect from bad calls.

| Metric | GATE |
|--------|------|
| Blocker fire rate | Expected: < 5% of races. If > 10%: infra issue, not model issue |
| Blocked-race outcome (when results available) | Win% should be < 20%. If > 30%: blocker is wrong |
| `horse_state_failed` rate | Should trend toward 0% as Horse State Brain stabilises |

**Query (fire rate):**
```sql
SELECT
    DATE_TRUNC('week', generated_at)                  AS week,
    COUNT(*)                                           AS total_races,
    COUNT(CASE WHEN decision_tier = 'X'
               AND macro_chaos_mode IS NULL THEN 1 END) AS macro_blocked,
    ROUND(COUNT(CASE WHEN decision_tier = 'X'
                     AND macro_chaos_mode IS NULL THEN 1 END)
          * 100.0 / COUNT(*), 1)                       AS macro_block_pct
FROM velo_verdicts
WHERE generated_at >= '2026-04-12'
GROUP BY week
ORDER BY week;
```

---

## 6. TIE v3 Gate — Help/Hurt

**Definition:** Races where `tie_gate_fires = TRUE` (tier upgraded or EW flag set).
Track whether upgrades produce better outcomes than the original tier.

| Metric | GATE |
|--------|------|
| Upgrade win% vs original-tier win% | Upgrade should win at ≥ original tier rate |
| EW-flagged horse place rate | Should be ≥ 40% (each-way target) |
| TIE gate fire rate | Expected: 8–15% of scored races |

**Query:**
```sql
SELECT
    v.tie_gate_fires,
    v.tie_gate_tier_upgrade,
    COUNT(s.race_id)                                                              AS outcomes,
    ROUND(AVG(CASE WHEN s.outcome = 'WIN' THEN 1.0 ELSE 0.0 END) * 100, 1)      AS win_pct,
    ROUND(AVG(CASE WHEN s.outcome IN ('WIN','PLACED') THEN 1.0 ELSE 0.0 END) * 100, 1) AS frame_pct
FROM velo_verdicts v
JOIN sigma_audits s USING (race_id)
WHERE v.generated_at >= '2026-04-12'
  AND v.tie_gate_fires = TRUE
GROUP BY v.tie_gate_fires, v.tie_gate_tier_upgrade
ORDER BY outcomes DESC;
```

---

## 7. Archetype Performance

Which archetypes are earning and which are decorative.
Minimum 10 outcomes per archetype before reading as signal.

| Archetype | Expected behaviour |
|-----------|-------------------|
| PACE_SETTER | High win%, lower place% |
| GRIND | Lower win%, higher frame% |
| TRAP | Should rarely appear in A/B |
| LONE_LEADER | High win% if available |

**Query:**
```sql
SELECT
    v.race_archetype,
    v.decision_tier,
    COUNT(s.race_id)                                                              AS outcomes,
    ROUND(AVG(CASE WHEN s.outcome = 'WIN' THEN 1.0 ELSE 0.0 END) * 100, 1)      AS win_pct,
    ROUND(AVG(CASE WHEN s.outcome IN ('WIN','PLACED') THEN 1.0 ELSE 0.0 END) * 100, 1) AS frame_pct,
    ROUND(AVG(v.velo_prime_prob)::numeric, 4)                                    AS avg_prob
FROM velo_verdicts v
JOIN sigma_audits s USING (race_id)
WHERE v.generated_at >= '2026-04-12'
  AND v.race_archetype IS NOT NULL
GROUP BY v.race_archetype, v.decision_tier
HAVING COUNT(s.race_id) >= 5
ORDER BY v.race_archetype, win_pct DESC;
```

---

## 8. Horse State Performance

Whether `readiness_state` and `market_state` tags predict outcome direction.

| State tag | Hypothesis |
|-----------|-----------|
| readiness = PRIMED | Win% above cohort average |
| readiness = FLAT | Win% below cohort average |
| market_state = shortening | Win% above cohort average |
| market_state = drifting | Win% below cohort average |

**Query:**
```sql
SELECT
    v.top_horse_readiness_state,
    v.top_horse_market_state,
    COUNT(s.race_id)                                                              AS outcomes,
    ROUND(AVG(CASE WHEN s.outcome = 'WIN' THEN 1.0 ELSE 0.0 END) * 100, 1)      AS win_pct,
    ROUND(AVG(CASE WHEN s.outcome IN ('WIN','PLACED') THEN 1.0 ELSE 0.0 END) * 100, 1) AS frame_pct
FROM velo_verdicts v
JOIN sigma_audits s USING (race_id)
WHERE v.generated_at >= '2026-04-12'
  AND v.top_horse_readiness_state IS NOT NULL
GROUP BY v.top_horse_readiness_state, v.top_horse_market_state
HAVING COUNT(s.race_id) >= 5
ORDER BY win_pct DESC;
```

---

## 9. Confidence Label Integrity (post-split)

Verify `confidence_level_effective` is now tracking tier behaviour correctly.
If `eff=high` rows are not winning at > 40%, the effective boundary (0.45) may be too low.

```sql
SELECT
    v.confidence_level_effective,
    v.decision_tier,
    COUNT(s.race_id)                                                              AS outcomes,
    ROUND(AVG(CASE WHEN s.outcome = 'WIN' THEN 1.0 ELSE 0.0 END) * 100, 1)      AS win_pct
FROM velo_verdicts v
JOIN sigma_audits s USING (race_id)
WHERE v.generated_at >= '2026-04-12'
  AND v.confidence_level_effective IS NOT NULL
GROUP BY v.confidence_level_effective, v.decision_tier
ORDER BY v.confidence_level_effective, v.decision_tier;
```

---

## 10. Operational Integrity

A good model with sloppy operations still lies. These metrics gate the validity of everything above.
If operational integrity is broken, the scorecard numbers are noise.

| Metric | Target | GATE |
|--------|--------|------|
| Scoring runs attempted per week | 7/7 days | FAIL if < 5/7 two weeks running |
| Scoring runs succeeded (pipeline_runs status=PASS) | ≥ 95% of attempts | FAIL if < 90% |
| Schema verification pass at startup | 100% | FAIL on any RuntimeError at startup |
| sigma_audits rows written same day as scoring | ≥ 90% of scored races | FAIL if < 80% |
| position completeness on new sigma rows | pos_note=null < 5% | FAIL until close_sigma_loops runs daily |
| Duplicate verdict posts (same race_id, same day) | 0 | FAIL if any found |
| truth-loop completion (race_truth_audits rows / sigma_audits rows) | ≥ 80% within 24h | WATCH until truth loop is fully wired |

**Query — scoring run health:**
```sql
SELECT
    DATE_TRUNC('week', started_at) AS week,
    COUNT(*)                        AS attempts,
    COUNT(CASE WHEN status = 'PASS' THEN 1 END) AS passed,
    ROUND(COUNT(CASE WHEN status = 'PASS' THEN 1 END) * 100.0 / COUNT(*), 1) AS pass_pct
FROM pipeline_runs
WHERE started_at >= '2026-04-12'
GROUP BY week
ORDER BY week;
```

**Query — duplicate verdicts (should always return 0 rows):**
```sql
SELECT race_id, DATE(generated_at) AS score_date, COUNT(*) AS dupes
FROM velo_verdicts
WHERE generated_at >= '2026-04-12'
GROUP BY race_id, DATE(generated_at)
HAVING COUNT(*) > 1
ORDER BY score_date DESC;
```

**Query — position completeness on new sigma rows:**
```sql
SELECT
    DATE_TRUNC('week', created_at) AS week,
    COUNT(*)                        AS sigma_rows,
    COUNT(top_pick_position)        AS with_position,
    ROUND(COUNT(top_pick_position) * 100.0 / COUNT(*), 1) AS position_pct
FROM sigma_audits
WHERE created_at >= '2026-04-12'
GROUP BY week
ORDER BY week;
```

---

## Weekly Checkpoint Log

Run all 9 scorecards + operational integrity every week. Log the headline numbers here.
Do not wait until 2026-05-12 blind — catch drift early.

| Week | A fire% | A win% | Suspect cohort win% | Blocker fire% | Pos complete% | Ops pass% | Gate status |
|------|---------|--------|---------------------|---------------|---------------|-----------|-------------|
| W1 (Apr 12–18) | — | — | — | — | — | — | pending |
| W2 (Apr 19–25) | — | — | — | — | — | — | pending |
| W3 (Apr 26–May 2) | — | — | — | — | — | — | pending |
| W4 (May 3–9) | — | — | — | — | — | — | pending |
| Final (May 12) | — | — | — | — | — | — | **PROMOTE / EXTEND / TIGHTEN** |

Fill this table each week. If any column shows two consecutive degrading weeks, investigate before continuing.

---

## Doctrine Freeze

**In effect from 2026-04-12 until 2026-05-12.**

During this window:
- No weight changes to the ensemble
- No A/B/C/X gate surgery
- No blocker threshold changes
- No new layers added to the scoring path
- No changes to `synthesize_decision()` logic

Exceptions permitted:
- Bug fixes that prevent scoring from running at all
- Infrastructure fixes (position join, schema, startup)
- Adding new passive monitoring flags (no scoring impact)

Any exception must be noted in the weekly checkpoint log with reason.

---

## Promotion Gates — Summary

All of the following must be true before promoting shadow-lab to live-control:

| # | Gate | Condition |
|---|------|-----------|
| 1 | A-tier fire rate | ≤ 14% for two consecutive weeks |
| 2 | A-tier win rate | ≥ 35% on ≥ 30 verified outcomes |
| 3 | Suspect cohort decision | Made (tighten or clear) — not deferred |
| 4 | Blocker fire rate | < 5% and trending down |
| 5 | Position completeness | pos_note=null < 5% on new sigma rows |
| 6 | Confidence split | `eff` and `raw` diverge on < 30% of rows (otherwise raw is already correct) |
| 7 | TIE gate upgrades | Not actively hurting (upgrade win% ≥ original tier baseline) |
| 8 | No open FAIL metrics | All GATE columns above in PASS or WATCH state |

**Do not promote if any gate is FAIL. Do not promote based on subjective feel.**

---

*Last updated: 2026-04-12. Review date: 2026-05-12.*
