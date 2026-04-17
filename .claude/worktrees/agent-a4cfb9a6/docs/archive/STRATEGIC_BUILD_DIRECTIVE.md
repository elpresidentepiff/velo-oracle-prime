# VÉLØ Strategic Intelligence System - Build Directive

**Date**: December 17, 2025  
**Version**: v1.1  
**Status**: Production Implementation Roadmap

---

## 0) Mission Objective

Build VÉLØ as an **Anti-House, Intent-First Oracle** that wins by modeling:

1. **Ability** (performance reality)
2. **Intent** (trainer/jockey objectives + placement logic)
3. **Market warfare** (liquidity anchors, release horses, manipulation patterns)
4. **Structure vs Chaos** (race-type volatility classification)
5. **Empirical learning loop** (updates weights/rules automatically post-race)

### Core Deliverables

**A stable backend** that ingests TheRacingAPI + Betfair Exchange market snapshots.

**A deterministic engine pipeline** that produces:
- Top Strike
- Top-4 chassis
- Value/EW (optional)
- Fade zones (probabilistic, logged)

**A post-race loop** that saves outcomes into:
- Scout Ledger
- ROI Intelligence Archive
- SLE Rule Library (Scientific Law Engine)

---

## 1) Architecture (Minimum Viable Production)

### Recommended Stack

- **API / Orchestrator**: FastAPI (Python) or Node (Hono) — whichever current repo uses consistently
- **DB**: Postgres (preferred) OR Cloudflare D1 (acceptable if batched + optimized)
- **Queue**: Redis/RQ or Cloudflare Queues (depending on deployment)
- **Model inference**: Python service (Torch) behind internal API
- **Market ingestion**: Betfair stream/poll snapshots (odds + traded volume if available)
- **Observability**: structured logs + race_id correlation + "engine_run_id"

> **CRITICAL**: Do NOT rewrite the entire system "because D1 timed out." Fix D1 usage or move DB. Rewrites kill momentum.

---

## 2) Data Ingestion (Non-Negotiable)

### A) Race Card Ingestion

Pull from **TheRacingAPI**: runners, OR/TS/RPR, form, trainer/jockey, race conditions (course/going/dist/class), if available.

Normalize into:
- `races`
- `runners`
- `entries` (race_id + runner_id + declarations)

### B) Market Ingestion (Betfair)

Store repeated snapshots:
- `market_snapshots` (timestamped)
  - best back/lay
  - last traded price
  - traded volume (if available)
  - implied prob
  - drift/steam deltas

> This is how you detect **Liquidity Anchors** vs **Release Horses**.

---

## 3) Engine Pipeline (Execution Order)

For each race, run in this **exact order**:

### 3.1 SQPE (Sub-Quadratic Prediction Engine)

**Goal**: reduce noise, keep signal.

**Inputs**: TS/RPR/OR, stability clusters, recent RPR sequence, pace proxies, course/going/distance stats.

**Outputs**:
- `ability_score`
- `stability_cluster_score` (variance penalty)
- `baseline_rank`

### 3.2 Chaos/Structure Classifier (mandatory)

Classify race volatility:
- field size
- rating spread
- in-form density (how many viable)
- pace uncertainty proxy
- low-grade handicap flags
- track punctuality / chaos tracks rule (you already have this memory)

**Outputs**:
- `chaos_level` (0–1)
- `mode`: STRUCTURE / MIXED / CHAOS
- `policy_overrides` (e.g., "suppress Win bets in CHAOS unless alignment")

### 3.3 SSES v1 + Market Weapon Layer (mandatory)

**Detect**:
- **Liquidity Anchor**: short price, absorbs money, frames but not necessarily wins
- **Release Horse**: mid price, stable profile, wins disproportionately in low-grade chaos

**Also detect**:
- Serial Second Hedger / Pacemaker fade patterns (leaders that trade short then fold)
- Drift Sentinel & Order Hygiene (alerts if entry becomes bad value)

**Outputs**:
- `market_role`: ANCHOR / RELEASE / NOISE
- `manipulation_risk`
- `entry_hygiene_flags`

### 3.4 TIE (Trainer Intention Engine)

Infer "who needs to win":
- class drop / class placement
- recent campaign signals (prep vs target)
- multi-runner stable targeting (yard has 2 runners = coupling signal)
- jockey booking intent
- days since run patterns
- equipment changes & revert (e.g., cheekpieces off after gate fiasco)

**Outputs**:
- `intent_score`
- `target_race_probability`
- `stable_coupling_flag`

### 3.5 HBI (Human Behavior Intelligence)

This is the **psychology layer**: not mystical, measurable proxies.

- trainer patterns (strike rate windows)
- jockey patterns (aggressive rides vs waiting tactics)
- market timing patterns (late steam vs early bait)
- narrative disruption scan (public story vs actual signals)

**Outputs**:
- `behavioral_edge_score`
- `public_narrative_conflict`

### 3.6 GTI (Game Theory Intent) — NEW

Treat the race as a **strategic interaction** (not independent outcomes). Model:
- **players**: trainers/owners, book/exchange liquidity providers, crowd
- **objective mismatch**: "place for money" vs "win for badge" vs "prep run"
- **multi-runner tactics**: one sets pace, one finishes
- **equilibrium signals**: odds shape that "makes sense" vs "designed"

**Outputs**:
- `gti_equilibrium_type`: FAIR / BAIT / TRAP / RELEASE_WINDOW
- `gti_race_script`: FRONT-LOADED / LATE-BURST / SPLIT-STABLE / CHAOS-SCATTER

### 3.7 SLE (Scientific Law Engine) — NEW

Hard rule library learned empirically (Bayesian updated). If high-confidence rule triggers, it can override.

**Outputs**:
- `sle_applicable_rules[]`
- `sle_confidence`
- `sle_override_actions[]`

### 3.8 Red-Team Stress Test — NEW

Adversarially attempt to defeat your own selection. If 2+ credible defeat routes → suppress Win; keep Top-4 only.

**Outputs**:
- `redteam_failure_modes[]`
- `risk_score`
- `win_suppressed`: bool

### 3.9 Decision Policy (final)

**Default chassis**:
- Top-4 structure always
- Win only as overlay when alignment happens:
  - SQPE + TIE + Market Role + SLE + RedTeam OK

**Outputs**:
- `top_strike_selection`
- `top4_structure[]`
- `value_ew[]` (optional)
- `fade_zone[]` (soft/hard probabilistic)
- `stake_policy` (if you're coding staking, else leave as "recommendation only")

---

## 4) Strategic Intelligence Pack v1.1 (What You Must Implement)

### 4.1 Scientific Law Engine (SLE)

A rule system with evidence tracking. Bayesian updates per race.

**Table**: `sle_rules`
- `id` uuid
- `name`
- `conditions_json` (course/dist/going bucket/field size/pace proxy)
- `effect_json` (upgrade/downgrade logic)
- `alpha`, `beta` (Beta distribution)
- `evidence_count`
- `last_updated`

**Rule confidence**: `alpha/(alpha+beta)`

If confidence > threshold (e.g., 0.70) and contradicts Win pick → Win suppressed.

### 4.2 Empirical Research Cycle (ERC)

Store hypotheses, score them post-race, update weights/rules.

**Tables**:

`hypotheses`
- `race_id`
- `hypothesis_type` (ABILITY / INTENT / CHAOS)
- `statement`
- `predicted_market_role_map`
- `result_score`

`redteam_findings`
- `race_id`
- `candidate`
- `failure_modes[]`
- `risk_score`
- `win_suppressed`

### 4.3 Cognitive Trap Firewall (CTF)

Prevent autopilot thinking:
- Anchoring effect detection → "favorite bias penalty"
- Familiarity pattern interrupt → force 3-hypothesis evaluation
- Narrative bias penalty unless backed by proxies

> This should be **code**, not advice.

---

## 5) Minimum DB Schema (Practical)

### Core:
- `races` (id, course, datetime, class, going, dist, surface, field_size)
- `runners` (id, name, age, sex, sire/dam if available)
- `entries` (race_id, runner_id, draw, weight, OR, TS, RPR, trainer, jockey, claims)
- `runner_form` (runner_id, race_date, course, dist, going, pos, rpr, ts)
- `market_snapshots` (race_id, runner_id, ts, best_back, best_lay, ltp, vol, implied_prob)

### Engine outputs:
- `engine_runs` (engine_run_id, race_id, timestamp, mode, chaos_level)
- `engine_runner_scores` (engine_run_id, runner_id, ability, intent, market_role, sle_hits, redteam_risk, final_score)
- `engine_verdicts` (engine_run_id, top_strike, top4_json, fades_json, notes_json)

### Learning:
- `race_results` (race_id, winner_id, placed_ids, sp, bfsp if available)
- `sle_rules` / `hypotheses` / `redteam_findings`
- `roi_archive_nodes` (trainer/jockey/sire/owner profitability nodes)
- `scout_ledger` (freeform but structured: signals + outcome + deltas)

---

## 6) Code Modules to Create (Directory-Level)

Create these modules cleanly:

```
velo/engine/pipeline.py (orchestrates order)
velo/engine/sqpe.py
velo/engine/chaos_classifier.py
velo/engine/sses_market_weapon.py
velo/engine/tie_intent.py
velo/engine/hbi_behavior.py
velo/strategy/gti_game_theory.py  ✅ new
velo/strategy/sle_engine.py        ✅ new
velo/strategy/redteam.py           ✅ new
velo/strategy/erc_loop.py          ✅ new
velo/storage/repositories.py
velo/api/routes.py
```

---

## 7) Concrete Skeleton Code (Drop-In)

### SLE engine (Bayesian rules)

```python
# velo/strategy/sle_engine.py
from dataclasses import dataclass

@dataclass
class SLERuleHit:
    rule_id: str
    name: str
    confidence: float
    effect: dict

class ScientificLawEngine:
    def __init__(self, rules_repo):
        self.rules_repo = rules_repo

    def evaluate(self, race_ctx) -> list[SLERuleHit]:
        hits = []
        for rule in self.rules_repo.active_rules():
            if self._matches(race_ctx, rule.conditions_json):
                conf = rule.alpha / (rule.alpha + rule.beta)
                hits.append(SLERuleHit(rule.id, rule.name, conf, rule.effect_json))
        return hits

    def update_post_race(self, race_ctx, outcome, baseline_eval):
        # baseline_eval(rule, outcome) -> did rule improve decision quality?
        for rule in self.rules_repo.rules_triggered_for_race(race_ctx.race_id):
            improved = baseline_eval(rule, outcome)
            if improved:
                rule.alpha += 1
            else:
                rule.beta += 1
            rule.evidence_count += 1
            self.rules_repo.save(rule)

    def _matches(self, race_ctx, conditions_json) -> bool:
        # implement course/dist/going bucket + field_size + surface + pace proxy matching
        return True
```

### Red-team stress test (win suppression)

```python
# velo/strategy/redteam.py
def red_team(race_ctx, candidates, market_view, model_view):
    findings = []
    for c in candidates:
        failure_modes = []
        if market_view.is_liquidity_anchor(c): failure_modes.append("LIQUIDITY_ANCHOR")
        if race_ctx.chaos_level > 0.65: failure_modes.append("CHAOS_VARIANCE")
        if model_view.pace_uncertain: failure_modes.append("PACE_UNCERTAINTY")
        if model_view.trip_risk_high(c): failure_modes.append("TRIP_RISK")
        risk = len(failure_modes)
        findings.append({"candidate": c, "failure_modes": failure_modes, "risk": risk})
    return findings
```

### Decision policy (overlay logic)

```python
def decide(verdict_view):
    win_allowed = (
        verdict_view.alignment.sqpe and
        verdict_view.alignment.intent and
        verdict_view.alignment.market_release and
        verdict_view.alignment.sle_ok and
        verdict_view.redteam_risk < 2
    )
    return {"win_allowed": win_allowed}
```

---

## 8) Slurm + Nemotron (Where They Fit)

### Slurm (open source)

Use Slurm if you are:
- training models on multiple GPUs/servers
- running backtests at scale
- scheduling nightly experiments without chaos

**Use case**: "Exploration Mode" batch jobs:
- Train/validate models
- Recompute ROI maps
- Re-evaluate SLE rules
- Run hyperparameter sweeps

### Nemotron (NVIDIA)

Nemotron is relevant if you want:
- a strong open-ish LLM for local inference (summarization, reasoning, explanation)
- to reduce reliance on paid APIs for text reasoning

**Use case inside VÉLØ**:
- convert raw race data into structured hypotheses (ERC)
- generate red-team failure modes
- produce readable "Oracle Execution Reports" without leaking structure

> **Important**: LLM is not the predictor. It's the strategic reasoning copilot. Predictive layer stays numeric.

---

## 9) Cloudflare D1 Timeouts (Why It Happens + Fix)

If you are on D1:
- You must batch writes (transaction-like behavior)
- Avoid chatty per-runner inserts per request
- Use prepared statements and bulk operations
- Use queues for ingestion writes (don't write inside hot request path)
- Store large JSON once per engine_run_id, not repeated rows

> If D1 still unstable at load → move DB to Postgres. Do not rewrite the whole app.

---

## 10) Output Format Requirements (Important)

VÉLØ must support:
- Raw long-form race data output (as requested)
- Structured JSON execution report for app use

So:
- Store structured JSON in DB.
- Render "raw message" at the very end from stored objects.

---

## 11) Implementation Plan (Sequence)

1. **Lock DB schema + repositories**
2. **Build ingestion** (RacingAPI + Betfair snapshots)
3. **Implement pipeline modules in order** (SQPE → Chaos → SSES → TIE → HBI → GTI → SLE → RedTeam → Decision)
4. **Persist**:
   - engine_run + runner scores + verdict
5. **Post-race**:
   - update SLE alpha/beta
   - log hypotheses scoring
   - update ROI nodes
6. **Add Drift Sentinel & Order Hygiene**
7. **Only then**: UI polish / extra outputs

---

## Conclusion

This is the full upgrade path in one message. It's a **system**, not a tipster.

If Manus implements this exactly, VÉLØ stops "guessing winners" and starts **extracting intent + exploiting market structure** with a learning spine that hardens over time.

---

**End of Strategic Build Directive v1.1**
