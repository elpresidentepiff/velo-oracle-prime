# VELO Control Doctrine V1

**Status:** ACTIVE_CONTROL_REGISTER  
**Generated:** 2026-06-04T22:24:14-07:00  
**Purpose:** Consolidate VELO runtime authority into one operator-readable doctrine.

This document does not create new scoring authority. It consolidates existing governance into a single control register so every rail has a visible authority state before it can influence live decisions.

## 1. Core Doctrine

VELO is a governed racing intelligence cockpit, not a sovereign autopilot.

Rails may discover, rank, explain, warn, and accumulate evidence. They may not silently promote themselves, alter live scoring, mutate doctrine, place bets, or send betting-language Telegram outputs without explicit operator authority and a documented rollback path.

## 2. Authority States

| State | Meaning |
|---|---|
| `LIVE_AUTHORITY` | May affect official production verdicts or official operator-facing live outputs. Requires source truth, evidence basis, rollback path, and operator-approved governance. |
| `LIVE_CONTEXT` | May appear in live context or explanation, but may not independently override official verdicts. |
| `PAPER_ONLY` | May produce current-day reads or paper ledgers. No live staking, no Betfair orders, no production-table mutation unless specifically part of paper evidence logging. |
| `SHADOW_ONLY` | May run beside production and write to shadow/evidence ledgers only. No live effect. |
| `CANDIDATE_ONLY` | Research/mined/proposed pattern. Requires forward evidence and human review before shadow or paper escalation. |
| `BLOCKED` | Must not be used until the named blocker is resolved and operator approval is recorded. |

## 3. Non-Negotiable Rules

- No hidden auto-promotion.
- No self-editing scoring policy.
- No model replaces the operator.
- No single score without rail/source breakdown.
- No dashboard panel without source truth.
- No "AI says" output without an evidence trace.
- No same-race SP, BSP, final position, result, finish, won, or future-known field in morning models.
- No New Build model input from RPR unless a future operator policy explicitly allows it.
- No Newspaper Form, tips, comments, or industry selections blended into Passport/core model features.
- No Telegram betting language, staking directive, or Betfair execution without explicit operator approval.
- No live learning/state mutation from Playbook G or sentient loops.
- No scoring-code change without an approved audit and rollback plan.

## 4. Safety Case Checklist

Before any rail moves upward in authority, the safety case must state:

| Field | Required Answer |
|---|---|
| Purpose | What decision the rail supports. |
| Source data | Exact source files/tables/APIs used. |
| Authority state | Current state and requested state. |
| Live impact | Whether it touches scoring, dashboard, Telegram, Supabase, staking, or Betfair. |
| Leakage audit | Evidence that future-known or prohibited fields are absent. |
| Stale-data risk | How stale/missing/degraded data is detected. |
| Failure mode | What can go wrong and how it is surfaced. |
| Evidence base | Sample size, date range, prospective/retrospective split, and comparison baseline. |
| Promotion gate | Minimum n, time window, lift requirement, and operator review requirement. |
| Rollback path | Exact config/file/commit rollback and verification command. |
| Owner artifact | Report, ledger, or policy file that records the decision. |

## 5. Rail Authority Register

| Rail / Component | Current Authority | Live Impact | Control Verdict |
|---|---|---:|---|
| Old VELO SQPE / active production ensemble | `LIVE_AUTHORITY` | Yes | Existing official lane. Keep under leakage debt watch because old docs flag legacy SP/RPR exposure. |
| Market Deception Score (MDS) | `LIVE_CONTEXT` / existing live sidecar if already weighted | Possible | Treat as a strong live-context/sidecar signal, not a sovereign override. Any weight change requires prospective evidence and operator approval. |
| Improvement Score | `LIVE_CONTEXT` if current active profile includes it; otherwise `SHADOW_ONLY` | Possible | Conflicting older/current docs exist. Do not make new claims without runtime confirmation. No new promotion from this doctrine. |
| Place Probability | `LIVE_CONTEXT` | Possible | Support/frame context only unless the active ensemble already weights it. No independent authority. |
| Longshot Score | `LIVE_CONTEXT` if already active; otherwise `BLOCKED_FOR_NEW_WEIGHT` | Possible | Gated/situational only. No expansion until ROI/evidence review is complete. |
| New Build Core / Passport lane | `PAPER_ONLY` | No | Safe current-day read lane. No live verdict replacement and no production promotion. |
| New Build Intent / Challenger lane | `PAPER_ONLY` / `BLOCKED_FOR_LIVE` | No | May report paper reads. Live promotion blocked until current-card coverage, leakage audit, and forward validation clear. |
| New Build Decision Policy V1 | `PAPER_ONLY` | No | Tactical lane labels may be reported for evidence; not live staking authority. |
| Sigma / results reconciliation | `LIVE_AUTHORITY` for truth/reconciliation | Yes, audit only | Official outcome honesty layer. Does not mutate scoring weights by itself. |
| Sigma KNN / Bayesian / explanation overlays | `SHADOW_ONLY` | No | Evidence and explanation only. No live weighting. |
| Doctrine Miner / pattern miner | `CANDIDATE_ONLY` | No | Generates hypotheses only. Requires human review and forward validation before shadow/paper escalation. |
| Newspaper / industry selection league | `SHADOW_ONLY` | No | Comparison and market-intent study only. Must not feed Passport/core features. |
| Acca rail | `SHADOW_ONLY` | No | No staking authority. May track portfolio logic only in shadow/paper evidence. |
| Handicap plot rail | `CANDIDATE_ONLY` | No | Candidate intelligence layer until a clean evidence ledger exists. |
| AW Tier A forward watch | `CANDIDATE_ONLY` | No | Watchlist/research only until prospective sample and audit pass. |
| Racing API enrichment | `SHADOW_ONLY` | No | Read-only enrichment and forward ledger. Leakage risk remains a promotion blocker. |
| Playbook G / sentient loop | `SHADOW_ONLY` | No | No live mutation. Shadow state only. |
| Shadow VELO / analog / council loops | `SHADOW_ONLY` | No | Critics propose; operator decides. No auto-apply. |
| Betfair execution | `BLOCKED` | No | Live mode must remain hard-gated unless operator explicitly unlocks it with risk controls. |
| Telegram betting directives | `BLOCKED` | No | Informational summaries only unless operator explicitly approves betting language and delivery rules. |
| Staking / execution bridge live mode | `BLOCKED` | No | Paper-only until operator approval, evidence gate, and bankroll/risk policy exist. |

## 6. Promotion Gates

Minimum gates are inherited from `MODEL_PROMOTION_GOVERNANCE.md`:

- General promotion: `n >= 300 races` or `n >= 500 runners`.
- Policy lane promotion: `n >= 150 top-pick lane decisions`.
- High-confidence policy proof: `n >= 50 HIGH confidence outcomes`.
- Clean operation: 30 days without runtime error, NaN, stale-source deception, or audit failure.
- Lift requirement: challenger or rail must beat the relevant champion/baseline by a material, documented margin.
- Safety guard: forbidden import/leakage checks must pass.
- Approval: explicit operator review required.
- Rollback: reversible within 15 minutes.

## 7. Source Documents

This doctrine consolidates, but does not supersede, the following source documents:

- `docs/architecture/PHASE_3_GOVERNANCE_PIPELINE.md`
- `docs/stabilization/MODEL_PROMOTION_GOVERNANCE.md`
- `docs/engineering/VELO_SYSTEM_FREEZE_V1.md`
- `docs/engineering/VELO_LEAKAGE_GOVERNANCE_V1.md`
- `docs/engineering/VELO_PROCESS_CONTROL.md`
- `docs/engineering/VELO_CONNECTION_TRUTH_PAPER_V1.md`
- `docs/stabilization/LEARNING_AND_PROMOTION_MAP.md`
- `docs/evidence/VELO_OPERATING_TRUTH_BOARD_V1.md`
- `docs/live_state/MASTER_STATE.md`
- `docs/runtime/DECISION_POLICY_V1.md`

## 8. Operating Interpretation

When documents conflict, use the stricter authority state until runtime evidence and operator approval settle the conflict. In practice: if one document says live and another says shadow/blocked, treat the rail as live only if the current runtime proves it is already active; otherwise freeze it at the safer state.

This doctrine is a control surface. It is not a permission slip.
