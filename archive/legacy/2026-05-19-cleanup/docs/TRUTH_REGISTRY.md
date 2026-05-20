# VÉLØ Oracle Prime — Truth Registry

> **Control document.** Defines what is live operational truth, what is learning truth, what is display-only, and what is dead.
> Last updated: 2026-04-30. Update when tables or field roles change.

---

## 1. Operational Scoring Truth

Fields and tables that directly determine what VÉLØ picks.

| Source | Field / Table | Role |
|---|---|---|
| `velo_verdicts` | `velo_prime_prob`, `top_rank_score` | Primary scoring output — ranking determined here |
| `velo_verdicts` | `decision_tier` (A/B/C/CHAOS) | Strike/Watch/NoBet gate |
| `velo_verdicts` | `full_analysis` (JSONB array) | Full ranked field with all runner scores |
| `velo_prime_ensemble.py` | `_WEIGHTS` dict | Ensemble blending weights — the actual model |
| `models/sqpe_v17_dev/` | SQPE model | Base probability (45% weight) |
| `models/specialist/` | 7 specialist models | Specialist sub-scores (55% weight combined) |
| `src/intelligence/macro_regime/` | `bha_macro_context.py` | Macro dampeners at scoring time (code module, not DB table) |

---

## LIVE SIGNAL TRUTH TABLE — 2026-04-30

The system must not talk as if all sidecars are equal.
Live production probability is still SQPE-dominant.
The most important unresolved signal decision is whether `improvement_score` should remain evidence-only or be tested for live weighting later.

| Signal | Live weighted in ensemble? | Current weight | Stored/logged? | Shadow only? | Operator visible? | Evidence strength | Current operating role |
|---|---:|---:|---:|---:|---:|---|---|
| `sqpe_v17 / VP` | YES | 0.45 | YES | NO | YES | Core engine | Dominant production probability anchor |
| `market_deception_score / MDS` | YES | 0.10 | YES | NO | YES | Strong | Best live sidecar |
| `place_prob` | YES | 0.08 | YES | NO | YES | Positive/supportive | Stability/frame support |
| `longshot_score` | YES, gated | 0.07 | YES | NO | YES | Situational | Only contributes in genuine longshot/SP>=10 context |
| `improvement_score` | NO | declared 0.12 but disabled | YES | evidence/observability | YES | Strong: n=62, SR 43.5%, frame 82.3% | Biggest truth gap; proven signal but not live-weighted |
| `release_day_prob / release_window_score` | NO | declared 0.10 but disabled | YES | observability | YES | Unproven/secondary | Keep calm; not production driver |
| `comment_intel_score` | NO | declared 0.08 but disabled | YES | observability | YES | Unproven/secondary | Keep calm; not production driver |
| `Playbook G shadow` | NO | none live | YES | YES | maybe/operator only | under evaluation | Shadow modifier only, no live probability change |
| `Racing API enrichment shadow` | NO | none live | YES | YES | YES | strong retrospective, leakage risk | Forward-test only; no scoring impact |
| `router_shadow_lane` | NO | none live | YES | YES | YES | evidence routing | Audit/visibility only |
| `candidate_execution_allowed` | NO scoring impact | none | YES | governance gate | YES | execution gate | Controls paper bridge escalation, not probability |
| `POWER_ANCHOR_MODE` | NO scoring impact | none | YES | paper execution | YES | early n=3 | Paper directive only, no live betting |

### Blunt Operating Hierarchy

1. Core engine: `VP / SQPE`
2. Best live sidecar: `MDS`
3. Best support sidecar: `place_prob`
4. Situational live sidecar: `longshot_score`
5. Strong evidence but not live-weighted: `improvement_score`
6. Audit/shadow only: `Playbook G`, `Racing API enrichment`, `router shadow lanes`, `paper execution bridge`

### Forbidden Interpretation

Do not treat `improvement_score`, `Racing API enrichment`, `Playbook G`, or `POWER_ANCHOR_MODE` as live probability drivers.
They are evidence, shadow, or paper layers unless explicitly promoted through gates.

### PHASE FUTURE — Improvement Score Live-Weight Review

Condition before review:
- closed-result evidence confirms `improvement_score` remains positive after dedupe
- matched-subset test completed
- no leakage issue
- shadow/paper evidence supports lift
- no change before formal gate approval

---

## 2. Learning Truth

Fields that actually change what VÉLØ does tomorrow.

### What sigma reads and passes to Playbook G

| Field | Source | Consumed by | Effect |
|---|---|---|---|
| `improvement_score`, `market_deception_score`, `place_prob`, `longshot_prob`, `release_day_prob`, `comment_intel_score`, `draw_bias_score` | `full_analysis` runner blocks | `_attribute_miss_signals()` | Miss attribution → doctrine EMA |
| `rpd_tag` | `full_analysis` runner blocks | Sigma RPD-C enrichment | Doctrine RPD-C layer |
| `track_chaos_rating` | `full_analysis` runner blocks | Playbook G `chaos_bloom` proxy | Emotion engine |
| `track_pace_bias` | `full_analysis` runner blocks | Playbook G `narrative_disruption` proxy | Emotion engine |
| `sp_dec` (winner) | `runner_results` table | Playbook G `mpi` proxy | Emotion engine |
| `decision_tier` | `velo_verdicts` top-level | Sigma tier accuracy EMA | Doctrine gating |
| `velo_prime_prob` | `velo_verdicts` top-level | Outcome derivation (WIN/MISS/PLACED) | All doctrine |
| `confidence_level` | `velo_verdicts` top-level | HIGH-confidence miss path gate | Miss classification (weak signal — pure threshold on velo_prime_prob) |

### Where G state lives

| Table | Pattern name | Purpose |
|---|---|---|
| `learned_patterns` | `SENTIENT_STATE_BACKUP` | Full G state (doctrine_strengths, appetite, emotion laws) — survives Railway restarts |
| `learned_patterns` | `playbook_g_fed_{date}` | Dedup marker — prevents double-ingestion |
| `learned_patterns` | tier/signal patterns | Sigma accuracy records by tier and signal |
| `velo_post_race_reviews` | — | Sigma per-race review output. Written by Service C. Not yet consumed downstream. |

---

## 3. Governance Truth

Exists for audit and versioning. Not read by scoring or sigma.

| Table / File | Status |
|---|---|
| `doctrine_versions` | Governance audit trail. Never read by scoring or sigma. |
| `permanent_principles` | Empty. Schema only. |
| `sigma_audits` | Partial write (10 rows). Key learning fields null. Not a reliable source. |

---

## 4. Display-Only Fields

**These look authoritative. They are not consumed by scoring, sigma, or Playbook G.**
Do not wire them into learning paths without explicit design decision.

### Top-level `velo_verdicts` columns

| Field | Written by | Read downstream | Status |
|---|---|---|---|
| `macro_regime_label` | scorer | nothing | **display-only** |
| `macro_chaos_mode` | scorer | nothing | **display-only** |
| `favourite_trap_risk` | scorer | nothing | **display-only** |
| `engine_version`, `doctrine_version`, `ensemble_version` | scorer | nothing | **audit metadata** |

### Inside `full_analysis` runner blocks

| Field | Written by | Read by sigma | Status |
|---|---|---|---|
| `track_draw_bias` | track context enrichment | nothing | **display-only** |
| `track_key_characteristics` | track context enrichment | nothing | **display-only** |
| `horse_recent_runs_90d` | warehouse enrichment | nothing | **display-only** |
| `horse_recent_avg_pos` | warehouse enrichment | nothing | **display-only** |
| `horse_course_runs` | warehouse enrichment | nothing | **display-only** |
| `horse_distance_runs` | warehouse enrichment | nothing | **display-only** |
| `horse_avg_pos_all` | warehouse enrichment | nothing | **display-only** |
| `trainer_course_runners`, `trainer_course_1st`, `trainer_course_ae`, `trainer_course_win_pct` | warehouse enrichment | nothing | **display-only** |
| `trainer_dist_runners`, `trainer_dist_1st`, `trainer_dist_ae` | warehouse enrichment | nothing | **display-only** |
| `confidence_level` (runner-level) | ensemble | nothing (top-level version is read) | **display-only** |
| `regime_override`, `verdict_flags` | ensemble | nothing | **display-only** |
| `sentient_state_loaded`, `sentient_state_source`, `sentient_races_observed`, `sentient_aggression_level`, `sentient_modifier_applied`, `sentient_modifier_mode` | Phase 1 sentient bridge | nothing yet (by design — Phase 1 audit only) | **audit-only (Phase 1)** |

> **Warning: The 9 warehouse enrichment fields are the primary false-confidence trap.**
> They look like live intelligence in the full_analysis blob. They are decorative.
> Do not assume a field in full_analysis is consumed just because it exists.

---

## 5. Monitoring

| Table | Written by | Reliability | Notes |
|---|---|---|---|
| `pipeline_runs` | Service B + C | Partial | Service B writes open+close. Crash before close = row stays `in_progress`. No Supabase creds = no record at all. |
| `velo_post_race_reviews` | Service C (sigma) | Reliable | Full review_outcome JSONB. This is where real sigma intelligence lives. |

---

## 6. Dead / Legacy / Empty

Tables with schema but no live role in the current prediction or learning path.

| Table | Rows | Status |
|---|---|---|
| `predictions` | 0 | Legacy schema. Not used. |
| `race_results` | 0 | Legacy schema. Not used. |
| `runner_derived_features` | 0 | Written by `persist_runner_derived_features()` which is not called in Railway path. |
| `betting_ledger` | 0 | Schema only. Not written. |
| `selections` | 0 | Schema only. Not written. |
| `velo_anomaly_flags` | 0 | Schema only. Not written. |
| `manipulation_alerts` | 0 | Schema only. Not written. |
| `horses`, `trainers`, `jockeys` | 0 | Legacy registries. Not in live path. |
| `archive/legacy_v11/` | — | NaiveBayes/KMeans v11 engines. Confirmed dead. Moved to archive 2026-03-22. |

---

## 7. VOX Intelligence Only

Tables used by VOX for briefings. Not in scoring or sigma path.

| Table | Purpose |
|---|---|
| `runner_race_facts` | Historical run data for horse/trainer profiles |
| `horse_comments` | NLP spotlight flags |
| `gear_medical_events` | Gear change history |
| `trainer_profiles`, `jockey_profiles`, `horse_profiles` | Entity profiles for briefings |

---

## Morning Cockpit — 5 Truth Queries

```sql
-- Q1. Did Service B run?
SELECT date, status, races_scored, runners_scored, error_message
FROM pipeline_runs WHERE service_name = 'velo-prime-scoring'
ORDER BY started_at DESC LIMIT 3;

-- Q2. What was picked?
SELECT race_id, decision_tier, confidence_level, velo_prime_prob, generated_at
FROM velo_verdicts ORDER BY generated_at DESC LIMIT 20;

-- Q3. What did sigma close?
SELECT race_id, outcome, miss_reason, verdict_confidence, decision_tier
FROM velo_post_race_reviews ORDER BY created_at DESC LIMIT 20;

-- Q4. What did G learn?
SELECT pattern_name, occurrences, confidence_level, last_observed
FROM learned_patterns WHERE last_observed > NOW() - INTERVAL '48 hours'
ORDER BY last_observed DESC;

-- Q5. How did doctrine move?
SELECT conditions->>'aggression_level' as aggression,
       conditions->>'total_races_observed' as total_races,
       last_observed
FROM learned_patterns WHERE pattern_name = 'SENTIENT_STATE_BACKUP';
```

---

## 8. Permanent Agent Inventory (Phase 6A audit — 2026-04-30)

Complete classification of every agent and execution file. Read before touching any of these.

| File | Classes | Label | Risk | Decision |
|---|---|---|---|---|
| `app/agents/betfair_execution_agent.py` | `BetfairExecutionAgent`, `BankrollManager` | `EXECUTION_BETTING_NOT_ACTIVE` | **HIGH** | ARCHIVE — contains `place_order()`. Never import in live path. |
| `app/agents/betting_agents.py` | `BettingAgent` ABC, 5 strategy agents | `LEGACY_AGENT` | MEDIUM | DOCUMENT ONLY — old era, inserts to `betting_ledger` table, not wired |
| `app/agents/betfair_trading_agents.py` | `BetfairTradingAgent`, `EarlyBackerAgent`, `LayOffAgent`, `TradingOrchestrator` | `EXECUTION_BETTING_NOT_ACTIVE` | **HIGH** | ARCHIVE — contains `place_bet()` (back + lay). All sub-engines are placeholder stubs. |
| `app/agents/odds_movement_predictor.py` | `OddsMovementPredictor`, `IntentEngine`, `NarrativeAnalyzer`, `BehavioralIntelligence`, `MarketManipulationRadar` | `STALE_PLACEHOLDER` | LOW | DOCUMENT ONLY — all sub-engines hardcoded/placeholder, no real intelligence |
| `app/integrations/betfair_client.py` | `BetfairClient`, `BetfairMode` | `EXECUTION_BETTING_NOT_ACTIVE` | MEDIUM | KEEP ISOLATED — safe default SIM mode, LIVE path untested |
| `src/velo/execution_bridge.py` | `VeloExecutionBridge`, `ExecutionDirective` | `PAPER_EXECUTION` | LOW | ACTIVE PAPER — hard RuntimeError on LIVE, simulation_only=True always |

### Existing Permanent-Agent Framework Assessment

**NO ETCSLV-style permanent-agent framework exists.** What exists:
- `BetfairExecutionAgent`: monolithic agent with hardcoded order logic, not wired to VÉLØ scoring
- `BettingAgent` ABC: 5-agent base class, old era, not connected to VeloPrime
- `VeloExecutionBridge`: directive-generation only (paper), closest to permanent-agent pattern but intentionally not autonomous

**Decision (2026-04-30):** Build permanent agents from scratch using VeloExecutionBridge as safety template. Do NOT refactor `BetfairExecutionAgent` or `betting_agents.py` — they are different eras and contain unsafe order logic.

---

## 9. Execution Bridge — Paper Execution Truth

Fields and files that govern the paper execution layer. Not in scoring or sigma path.

| Source | Field / File | Role | Status |
|---|---|---|---|
| `data/velo_execution_bridge_paper_ledger.csv` | Full paper ledger | Append-only directive record with outcomes | ACTIVE — paper only |
| `src/velo/execution_bridge.py` | `VeloExecutionBridge._map_verdict()` | Directive mapping logic | PAPER_ONLY |
| `data/racing_api_shadow_forward_ledger.csv` | `candidate_execution_allowed` | Gate injection into directives | SHADOW — leakage risk flagged |
| `ExecutionDirective.simulation_only` | Hard field = True always | Prevents any live execution | PERMANENT GATE |
| `ExecutionDirective.suggested_stake` | Hard field = None always | No staking permitted | PERMANENT GATE |

**Hard rules (never touch):** VELO_EXECUTION_MODE=LIVE → RuntimeError. BETFAIR_MODE=LIVE → RuntimeError.

---

## 9. Racing API Shadow Enrichment — Leakage-Flagged Truth

| Source | Status | Notes |
|---|---|---|
| `data/racing_api_shadow_forward_ledger.csv` | RETROSPECTIVE_SIGNAL_TEST_WITH_LEAKAGE_RISK | 374,639 rows, 6 tables. Production weight changes blocked. |
| `racing_api_*_shadow_score` fields | SHADOW — not in production scoring | Injected into directives only via `enrich_from_shadow_ledger()` |

---

## 10. Place Signal Classifier — Operator Visibility Layer

Added 2026-05-01. Commit `58ed2a1`.

Place Signal Classifier added as operator-visibility layer. Classifies each VP30+ verdict into a place-market stack (ELITE → STRONG_PLUS → STRONG → IMPROVE_WATCH → PLACE_SUPPORT → BASE_TRUST → SUPPRESS → BELOW_VP30) based on place economics audit evidence (n=28–380, frame=70–100%, E/W 1/4 ROI +52%–+170%).

**Safety:** No live scoring impact. No VP change. No SQPE change. No router change. No staking. Read-only from `velo_verdicts`.

**Telegram:** `VELO_ENABLE_PLACE_SIGNAL_TELEGRAM` gate (default OFF, set to ON 2026-05-01).

**Full wiring documentation:** `docs/engineering/VELO_PROCESS_WIRING_MAP_V1.md` Section 1.

| Field | Status |
|---|---|
| `place_stack_label` | display/operator only |
| `place_stack_status` | display/operator only |
| `min_place_odds` | operator reference only — verify actual odds before any action |
| All `evidence_*` fields | audit reference — from 2026-05-01 place economics audit |

**Not in:** scoring pipeline, sigma learning, Playbook G, ensemble weights, router.

---

## Change Log

| Date | Change |
|---|---|
| 2026-03-22 | Initial registry filed. Truth audit complete. |
| 2026-03-22 | Phase 1 sentient bridge wired (audit-only). |
| 2026-03-22 | partial pipeline_run status added to Service B. |
| 2026-04-29 | Phase 5: Racing API shadow enrichment (bfe983a). 374,639 rows. Leakage risk classified. No weight changes. |
| 2026-04-29 | Phase 6: VeloExecutionBridge (c1353ff). Paper ledger live. Hard gates verified. Classification: PAPER_EXECUTION_LEDGER_ACTIVE. |
| 2026-04-29 | Phase 6A: --audit-results (3f65b1c). First paper close: POWER_ANCHOR 2/2 wins, P&L=+1.16. Gate delta +83.3pp. |
| 2026-04-30 | Section 8 (Execution Bridge) and Section 9 (Racing API enrichment) added to registry. |
| 2026-05-01 | Section 10: Place Signal Classifier added (58ed2a1). OPERATOR_VISIBILITY_ONLY. Telegram gate ON. No scoring impact. |
