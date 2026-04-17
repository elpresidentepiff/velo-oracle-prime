# VELO WAR MODE DIRECTIVE v2.0

**Strategic Intelligence Pack v2 - Implementation Complete**

---

## MISSION

Transform VELO from a prediction model into a strategic intelligence system that:

1. **Does NOT "learn" from low-signal / manipulated races**
2. **Models racing as a strategic game**: trainers/jockeys as agents, market as opponent
3. **Produces stable profits** by anchoring Top-4 chassis in chaos races, only taking Win overlays when engine + market align
4. **Explains why races are "programmed"**: class bands, conditions, entry choices, multi-runner stable tactics, market shape

---

## REALITY MODEL: How Races Are "Engineered"

### Who "Programs" a Race?

**Race conditions** are written by racing authority/racecourse (weights, class band, distance, age/sex restrictions, penalties). This creates target profiles: the kind of horse/trainer that will benefit.

**Trainers choose entries strategically:**
- Placing to win vs placing as prep
- Protecting handicap marks
- Exploiting class/conditions
- Using "education runs"
- Using stablemates to shape pace

**Owners/trainers know private variables we don't:**
- Fitness, minor issues, schooling progress, how the horse is moving
- Whether the day is a "go" day
- Tactical plan (front-run / hold-up)
- Whether a run is to "get a mark" or "drop a mark"

**Engineering lever**: It's not fixed. It's a system where intent + incentives control the output.

---

## STRATEGIC INTELLIGENCE PACK V2 (IMPLEMENTED)

### 1. ADLG - Activity-Dependent Learning Gate

**Problem**: Engine updates from noise and gets "trained into losing."

**Fix**: VELO only commits learning when ALL gate conditions pass:

1. Signal convergence: SQPE + SSES + TIE + Stability Cluster above thresholds
2. Manipulation state not "High" (or commit only to quarantine)
3. Ablation robustness: decision survives feature-family silencing
4. Outcome verified and post-race critique completed
5. No integrity red flags

**Implementation**: `app/ml/learning_gate.py`

### 2. AAT - Ablation / Silencing Tests

**Purpose**: If removing one feature family flips the selection, the decision was fragile and should NOT train.

**Run 5 ablations:**
1. Remove market features
2. Remove trainer/jockey intent
3. Remove form/stability
4. Remove pace geometry
5. Remove course/going bias

**Compute:**
- `flip_count`: How many ablations changed top selection
- `prob_delta_max`: Maximum probability change
- `rank_delta_max`: Maximum rank change

**Rules**: If `flip_count >= 2` or `prob_delta_max > ε` → quarantine learning

**Implementation**: `app/ml/ablation_tests.py`

### 3. GTI - Game Theory Intelligence (Opponent Models)

**Stop treating the market as "information." Treat it as an agent.**

**Opponent/Agent modules:**
- **Trainer Agent**: objective = win vs place vs conditioning vs handicap manipulation
- **Market Agent**: objective = balance book / trap liquidity / move price
- **Stable Agent**: multi-runner tactics (one sets pace, one finishes)

**Outputs:**
- `intent_class`: {Win, Place, Prep, Mark-Adjust, Unknown}
- `market_role`: {Liquidity_Anchor, Release_Horse, Spoiler, Steam, Drift_Bait}
- `stable_tactic`: {Pace_Setter, Cover, Finisher, Decoy}

**Implementation**: `app/ml/opponent_models.py`

### 4. CTF - Cognitive Trap Firewall

**Protects VELO from human biases and cognitive traps.**

**Explicit bias detectors:**
1. **Anchoring effect**: favourite/short price overweighted → downweight win confidence unless release signal present
2. **Recency bias**: last-run over-influence → stability cluster must confirm
3. **Narrative trap**: "big stable/jockey therefore win" → require intent markers
4. **Sunk cost/tilt**: if user is chasing losses → default to conservative chassis (Top-4) and reduce stake suggestions

**Implementation**: `app/ml/cognitive_trap_firewall.py`

### 5. Race Engineering Features

**Features that reflect how races are CONSTRUCTED and TARGETED, not just horse form.**

**4.1 Condition Targeting Index (CTI)**
- Match to race conditions (age/sex/class/distance/going/band/penalties)
- Prior evidence of trainer using similar conditions
- Pattern: "horse often runs in this exact template when ready"

**4.2 Entry Intent Markers (EIM)**
- Travel distance, quick turnaround vs long gap
- First-time headgear, switch in jockey, notable booking
- Class move + distance move + surface move combination
- Stable form (hot/cold) + "needs a win" context

**4.3 Multi-Runner Stable Coupling (MSC)**
- If same trainer has 2+ runners:
  * Detect complementary roles (pace + finisher)
  * Detect "protect the fav" patterns
  * Detect "one is the plot" with market shape divergence

**4.4 Handicap Mark Strategy (HMS)**
- UK/IRE angle: trainers manage marks
- `mark_pressure`: horse running from career-high OR dropping to a "floor"
- `drop_program`: multiple runs with declining effort to drop mark
- "Today is the go" when conditions finally match + market indicates

**Implementation**: `app/ml/race_engineering_features.py`

### 6. Decision Policy (Anti-House Chassis)

**Hard rules:**

**In Chaos races**: default = Top-4 chassis. Win only when:
- Release Horse + Intent Win + market not manipulated + ablation stable

**In Structure races**: allow win overlays if:
- stability + pace geometry + intent converge

**Outputs:**
- `top_strike_selection`
- `top_4_structure`
- `fade_zone_runners` (probabilistic)
- `market_roles` per runner
- `learning_gate_status`

**Implementation**: `app/strategy/decision_policy.py`

### 7. Post-Race Self-Critique Loop

**Mandatory post-race analysis:**

When result arrives:
1. Assign market roles retrospectively
2. Evaluate gate decision correctness
3. Update quarantine promotion counters
4. Write a "why we lost/won" record
5. Adjust thresholds

**Implementation**: `app/learning/post_race_critique.py`

---

## ACCEPTANCE TESTS

**FAIL conditions:**
- ❌ If a race is flagged "High manipulation" and VELO still commits learning
- ❌ If ablation flips the selection and we still commit learning
- ❌ If multi-runner stable has winner + another in top-4 and we didn't flag coupling
- ❌ If favourite acts as liquidity anchor and we treated it as win default in chaos

---

## IMPLEMENTATION STATUS

✅ **ADLG** - Activity-Dependent Learning Gate  
✅ **AAT** - Ablation / Silencing Tests  
✅ **GTI** - Opponent Models (Trainer/Market/Stable)  
✅ **CTF** - Cognitive Trap Firewall  
✅ **Race Engineering Features** - CTI/EIM/MSC/HMS  
✅ **Decision Policy** - Anti-House Chassis  
✅ **Post-Race Critique Loop** - Self-learning system  

---

## NEXT STEPS

1. **Wire into engine pipeline**: V12FeatureEngineer → SQPE → Chaos → SSES → TIE → HBI → GTI → CTF → DecisionPolicy → ADLG → Store
2. **Add DB schema**: learning_events, market_snapshots, stable_entries, race_conditions
3. **Backtest War Mode**: Run on historical data and measure improvement
4. **Production deployment**: Integrate with live race card ingestion

---

## FINAL NOTE

VELO doesn't need more clever narratives. It needs control systems:
- Learning gate
- Robustness checks
- Opponent models
- Trap firewall
- Race engineering features

**Build those, and the "secret info" problem becomes irrelevant because we stop needing perfect information — we exploit structural incentives and market behaviour.**

---

**Version**: 2.0 (War Mode)  
**Date**: December 17, 2025  
**Status**: IMPLEMENTATION COMPLETE
