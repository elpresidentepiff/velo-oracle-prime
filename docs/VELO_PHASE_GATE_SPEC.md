# VÉLØ Phase Gate Specification
**Version**: 1.0
**Date**: 2026-03-22
**Owner**: Whoever merges structural changes to scoring, learning, governance, or persistence
**Update trigger**: Every structural merge affecting those four domains
**Review cadence**: Weekly in morning cockpit

---

## Current Active Phase

| Field | Value |
|---|---|
| Bridge mode | Phase 1 / `audit_only` |
| Next gate target | Phase 1 → 2A |
| Clean runs required | 5 consecutive |
| Current clean count | 0 / 5 |
| Last updated | 2026-03-22 |

---

## Purpose

This document defines the formal criteria for advancing VÉLØ through operational phases.
It exists to prevent "temporary caution" from becoming permanent limbo, and to prevent regression from being papered over.

Every gate is **pass/fail with a concrete verification method**. No prose judgements.

---

## Current Phase

**Phase 1 — Audit-Only Bridge**
`modifier_mode = audit_only`
Sentient fields present in verdicts. No probability movement. No rank movement.

---

## Tier 1 Reliability Gates

These must be continuously true. If any regresses after passing, see **Freeze Conditions** below.

### T1.1 — Service B Scoring Truth

| Check | Verification | Pass Condition |
|---|---|---|
| Pipeline ran today | `pipeline_runs` table, `service = 'service_b'`, today's date | Row exists, `status = 'complete'` or `partial_failure` |
| Races attempted vs persisted | `pipeline_runs.races_attempted` vs `pipeline_runs.races_persisted` | Difference < 10% of attempted |
| No stale `running` sentinel | `pipeline_runs` WHERE `status = 'running'` AND `started_at < now() - interval '4 hours'` | Zero rows |
| `velo_verdicts` written today | `velo_verdicts` WHERE `created_at::date = today` | Row count > 0 |
| Pipeline closed in `finally` | Code review: `workers/daily_pipeline.py` | `pipeline_runs` status always updated even on exception |

### T1.2 — Sentient Audit Fields in Production

| Check | Verification | Pass Condition |
|---|---|---|
| 6 sentient fields present | `velo_verdicts.full_analysis` JSON keys | `sentient_audit`, `modifier_mode`, `g_state_snapshot`, `g_applied`, `g_modifier`, `g_audit_reason` all present |
| `modifier_mode` correct | Value in `full_analysis.modifier_mode` | `= 'audit_only'` (Phase 1) |
| No probability drift | Compare `velo_verdicts.probability` with SQPE raw output | Delta < 0.001 |
| No rank drift | Compare verdict rank order with pre-sentient rank order | Identical |
| Fields from fresh build | Check deploy ID matches Railway latest deploy | Same build that was pushed |

### T1.3 — Result Ingestion Reliability

| Check | Verification | Pass Condition |
|---|---|---|
| All scored races have results | LEFT JOIN `velo_verdicts` → `race_results` on `race_id`, today - 1 | Zero unmatched verdicts older than 24h post-race |
| No partial result writes | `runner_results` count per race = runner count in `runners` | Match for all closed races |
| Results written on time | `race_results.created_at` vs race `off_time` | Within 2 hours of race off |
| Sigma closures complete | `pipeline_runs` WHERE `service = 'service_c'`, today | Status = `complete`, no duplicates |
| `velo_post_race_reviews` written | Count WHERE `created_at::date = today - 1` | Row count = scored races from yesterday |

### T1.4 — Playbook G State Integrity

| Check | Verification | Pass Condition |
|---|---|---|
| `total_races_observed` increments | Compare today's `SENTIENT_STATE_BACKUP` vs yesterday's | Increased by correct race count |
| State survives redeploy | Run `scripts/proof_playbook_g_persistence.py` | All assertions pass |
| Restore works after restart | `SENTIENT_STATE_BACKUP` row exists in `learned_patterns` | Row present, `updated_at` = today |
| No fallback-to-default | `g_state_snapshot.source` in verdicts | `= 'restored'` or `= 'live'`, never `= 'default'` after first run |

### T1.5 — Service C Reliability

| Check | Verification | Pass Condition |
|---|---|---|
| No duplicate sigma runs | `pipeline_runs` WHERE `service = 'service_c'` AND date = today | Exactly 1 row |
| No stale running state | Same stale sentinel check as T1.1 | Zero rows |
| Correct build deployed | Railway deploy ID matches latest push | Same ID |

---

## Phase 1 → Phase 2A Activation Gate

**All of the following must be true simultaneously:**

### Criterion 1 — Five Consecutive Clean Live Runs

- [ ] T1.2 passed on 5 consecutive scoring days (no gaps)
- [ ] `modifier_mode = 'audit_only'` confirmed in all 5
- [ ] Zero probability drift in all 5
- [ ] Zero rank drift in all 5

### Criterion 2 — Five Consecutive Clean Sigma Closures

- [ ] T1.3 passed on 5 consecutive days
- [ ] T1.5 passed on 5 consecutive days (no Service C duplicates)
- [ ] `velo_post_race_reviews` written for all scored races in those 5 days

### Criterion 3 — Doctrine State Integrity Confirmed

- [ ] T1.4 passed on all 5 days
- [ ] `total_races_observed` trajectory is monotonically increasing
- [ ] Restore test passes fresh (run `scripts/proof_playbook_g_persistence.py` clean)

### Criterion 4 — Result Ingestion Confirmed Clean

- [ ] T1.3 passed on all 5 days
- [ ] Zero unmatched verdicts in any of the 5 days
- [ ] No late result writes (>2h post-race) in any of the 5 days

### Criterion 5 — Operator Sign-Off

- [ ] Operator has reviewed morning cockpit for all 5 days
- [ ] Operator explicitly approves Phase 2A activation in writing (commit message or doc edit)
- [ ] No open incidents in `docs/VELO_INCIDENT_LOG.md` affecting scoring or learning

**When all 5 criteria are checked: activate Phase 2A.**

---

## Phase 2A Definition

**Annotations only. No probability movement. No rank movement.**

Changes from Phase 1:
- `modifier_mode` changes from `audit_only` to `annotation_only`
- Sentient audit fields may include narrative annotations in `full_analysis`
- VOX may reference G's state in outputs
- No numeric output from G touches scoring path

Phase 2A → Phase 2B gate: defined separately after Phase 2A is proven.

---

## Freeze Conditions

If any Tier 1 gate **regresses after passing**, the following applies immediately — no operator decision required:

| Regression | Automatic Action |
|---|---|
| T1.2 fails (sentient fields missing or drift detected) | Bridge stays at `audit_only`. Alert in morning cockpit. Do not advance. |
| T1.3 fails (result ingestion gap) | Service C runs suspended until gap is diagnosed. G does not learn from that day's closures. |
| T1.4 fails (G state falls back to default) | Investigate restore path before next scoring run. Flag in incident log. |
| T1.5 fails (Service C duplicate) | Deduplicate manually. Do not count that day toward the 5-consecutive requirement. |
| Any T1 gate fails during Phase 2A | Revert `modifier_mode` to `audit_only`. Re-run 5-day clean gate from zero. |

**Scoring continues during any freeze. Learning and bridge state do not advance.**

---

## Morning Cockpit Checklist (Required Weekly Minimum)

Run every morning after 09:30 UTC when racing was the previous day:

```
[ ] T1.1 — pipeline_runs: complete row exists for Service B
[ ] T1.2 — velo_verdicts: sentient fields present, modifier_mode = audit_only
[ ] T1.3 — race_results: all scored races closed, velo_post_race_reviews written
[ ] T1.4 — SENTIENT_STATE_BACKUP: updated, total_races_observed incremented
[ ] T1.5 — Service C: exactly 1 run, no duplicates
[ ] Rank/prob drift: zero
[ ] Open incidents: none blocking
```

If all 7 boxes checked: mark day as **CLEAN** in cockpit log.
Consecutive CLEAN days count toward Phase 2A gate.

---

## Truth Registry Integration

This spec is a living document.
When structural changes are merged that affect scoring, learning, governance, or persistence:

1. Update the relevant gate criteria if the change adds new verification points
2. Reset consecutive-clean counters if the change touches the sentient bridge path
3. Note the change in `docs/VELO_INCIDENT_LOG.md` under a structural change entry

**A frozen Phase Gate Spec is institutional fiction. Keep it alive.**

---

## Sign-Off Log

| Date | Phase | Action | Operator |
|---|---|---|---|
| 2026-03-22 | Phase 1 | Spec created. Audit-only bridge live. Tier 1 gates defined. | — |
