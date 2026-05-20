# NAMED SIGNAL LANE OPERATIONALIZATION V1

**Classification:** ADVISORY_TRACKING_ONLY | NO_SCORING_CHANGE | NAMED_LANES_ACTIVE
**Built:** 2026-05-17
**Commit:** c53e34f (lanes built) + current session (operationalization)
**Evidence base:** SIGMA_2K_SAFE_TRAINING_SLICE_V1 — 1310 training-safe rows

---

## What Named Lanes Are

Named lanes are evidence-based regime filters applied to VÉLØ prediction outputs.
They do not change scoring, routing, staking, or model weights. They add a layer
of regime awareness: *which evidence category does this selection belong to?*

Before lanes:
```
"What does VÉLØ like today?"
```

After lanes:
```
"Which VÉLØ regime is each horse in today?"
```

This is the operational difference. The answer changes how an operator reads the card.

---

## Lane Definitions

| Lane | Definition | Historical SR | Status |
|---|---|---|---|
| **MDS_HIGH_LANE** | VP≥0.30 AND MDS>0.50 | **69.2%** (n=39) | PROVEN — crown jewel |
| **IMPROVER_LANE** | VP≥0.30 AND improvement_score>0.40 | **42.1%** (n=38) | PROVEN — small-n |
| **VP40_TIER_A_LANE** | VP≥0.40 AND tier A | **44.7%** (n=132) | PROVEN |
| **VP40_LANE** | VP≥0.40 | **45.3%** (n=150) | PROVEN |
| **SHORTFAV_VP30** | SP<3.0 AND VP≥0.30 | **52.2%** (n=186) | PROVEN |
| **MIDPRICE_ROUTER_QUAL** | SP 3.0–8.5 AND router V1/V2/V6 | **33.3%** (n=18) | INSUFFICIENT_SAMPLE |
| **MIDPRICE_SUPPRESS** | SP 3.0–8.5 AND no router | **16.0%** (n=545) | SUPPRESS_CONFIRMED |
| **LONGSHOT_SUPPRESS** | SP>8.5 | **6.3%** (n=413) | SUPPRESS_CONFIRMED |

---

## Action Labels

Each horse receives an action label based on its highest-priority lane:

| Action | Lanes | Meaning |
|---|---|---|
| **PRIORITY_WATCH** | MDS_HIGH, IMPROVER, VP40+TierA | High-conviction regime. Operator priority. |
| **WATCH** | VP40, SHORTFAV_VP30, MIDPRICE_ROUTER_QUAL | Proven or promising regime. Track normally. |
| **SUPPRESS_ADVISORY** | MIDPRICE no-router, LONGSHOT | Confirmed weak zone. Advisory suppress. |
| **HOLD_MORE_DATA** | No lane qualified | Cannot classify with current evidence. |

Action labels are advisory. They do not suppress scoring. They do not trigger orders.
They inform the operator's morning read.

---

## Crown Jewel: MDS_HIGH_LANE

```
SR: 69.2% at n=39
Definition: VP≥0.30 AND market_deception_score > 0.50
Status: PROVEN (n<50 sample warning — holds across all checks so far)
```

When VÉLØ fires MDS_HIGH, the market is exposed. The model has high conviction AND the
market deception engine sees unusual signal. These are the rarest selections — on many
days there will be zero — but historically they have been the most explosive.

**How to read MDS_HIGH candidates:**
- Prioritise operator attention immediately
- Check RP convergence: if RP also supports, this is the strongest possible read
- Check CASHRUN class: if CASHRUN_WATCH overlaps, it is multi-engine convergence
- SP band: if mid-price (3.0–8.5), router qualification is key

**Warning:** n=39. This signal has held through 1310 rows but is not immune to regression.
Signal collapse gate: SR drops >5pp from 69.2% at n≥50 → trigger council review.

---

## Proven Small-n: IMPROVER_LANE

```
SR: 42.1% at n=38
Definition: VP≥0.30 AND improvement_score > 0.40
Status: PROVEN (n<50 sample warning)
```

VÉLØ is detecting genuine forward motion before the market prices it. These selections
often sit in mid-price ranges where the market underestimates the pace of improvement.

**How to read IMPROVER_LANE candidates:**
- Treat as priority alongside MDS_HIGH when the two overlap
- If IMPROVER_LANE AND MIDPRICE_ROUTER_QUAL → double confirmed mid-price edge
- Watch for RP support/conflict: RP backing an improver is convergence signal

---

## Suppression Confirmed Lanes

### MIDPRICE_SUPPRESS
```
SR: 16.0% at n=545
Definition: SP 3.0–8.5 AND no router qualification
```
The mid-price zone without router backing is confirmed as the main leak zone. These horses
look right but do not have structural confirmation. Advisory suppress.

The frame gate (not yet cleared) is the only blocker on full suppression promotion.
One more cycle with positive frame delta clears it.

### LONGSHOT_SUPPRESS
```
SR: 6.3% at n=413
Definition: SP>8.5
```
VÉLØ produces longshot candidates but they are consistently dead money at the portfolio level.
Unless overridden by a PROVEN lane (e.g. MDS_HIGH fires on a SP 9.0 horse), this is suppress.

---

## Allowed Use

```
✅ Read the operator card each morning
✅ Use lane labels to prioritise manual attention
✅ Use action labels to inform monitoring decisions
✅ Run weekly tracker to see n growth and SR stability
✅ Flag MDS_HIGH / IMPROVER candidates for closer watch
✅ Use suppress advisory lanes to deprioritise manual review
```

---

## Forbidden Use

```
❌ No automatic selection based on lane label alone
❌ No staking change triggered by lane classification
❌ No router rule change based on lane SR
❌ No model weight change before n≥200 sustained evidence
❌ No Playbook G promotion based on lane SR
❌ No Telegram output change
❌ No live state mutation
```

---

## Promotion Gates

Gate promotions are operator decisions. Nothing promotes automatically.

| Lane | Current Status | Next Gate | Gate Condition |
|---|---|---|---|
| MDS_HIGH_LANE | PROVEN | Shadow policy discussion | n≥100, SR sustained ≥60% |
| IMPROVER_LANE | PROVEN | Shadow policy discussion | n≥100, SR sustained ≥40% |
| VP40_LANE | PROVEN | Model weight discussion | n≥300, SR sustained ≥+20pp over 20+ days |
| MIDPRICE_ROUTER_QUAL | INSUFFICIENT_SAMPLE | Advisory promotion | n≥50, SR≥30% |
| MIDPRICE_SUPPRESS | SUPPRESS_CONFIRMED | Full suppress rule | Frame gate cleared (one cycle) |

---

## Weekly Cadence

Run every Sunday or after 100+ new training-safe rows:

```bash
# 1. Rebuild training dataset
PYTHONPATH=. python scripts/build_sigma_training_dataset.py

# 2. Named lane stats + today's candidates
PYTHONPATH=. python scripts/build_named_signal_lanes.py --date YYYY-MM-DD

# 3. Operator war board (today's candidate cards)
PYTHONPATH=. python scripts/build_named_lane_operator_card.py --date YYYY-MM-DD

# 4. Weekly tracker (delta vs last snapshot)
PYTHONPATH=. python scripts/run_weekly_signal_lane_tracker.py --date YYYY-MM-DD
```

Read:
- `data/reports/named_lane_operator_card_latest.md` — daily war board
- `data/reports/weekly_signal_lane_tracker_latest.md` — weekly delta tracker
- `data/reports/named_signal_lanes_latest.md` — full lane stats

---

## Stop Conditions

Weekly tracking stops or triggers a council review if:

1. MDS_HIGH SR drops below 64% at n≥50 (>5pp collapse from 69.2% reference)
2. IMPROVER SR drops below 37% at n≥50 (>5pp collapse from 42.1% reference)
3. VP40_LANE SR drops below 40% at n≥200
4. MIDPRICE_SUPPRESS SR rises above 22% at n≥600 (suppression may need review)
5. Any PROVEN lane loses PROVEN status at meaningful n without clear explanation

---

## Daily Script Addition

Add to the daily EOD pipeline after sigma + results:

```bash
# After run_results_sigma.py:
PYTHONPATH=. python scripts/build_named_lane_operator_card.py --date YYYY-MM-DD
```

Add to Mission Control run (already wired via velo_mission_control.py):
- Named lane candidates shown in console output
- Corpus 2K progress shown in console output

---

## Governance

```
NO_SCORING_CHANGE
NO_MODEL_CHANGE
NO_ROUTER_CHANGE
NO_STAKING_CHANGE
NO_TELEGRAM_CHANGE
NO_PLAYBOOK_G_PROMOTION
NO_LIVE_STATE_MUTATION
ADVISORY_TRACKING_ONLY
```

---

*NAMED_SIGNAL_LANE_OPERATIONALIZATION_V1 — 2026-05-17*
*Evidence base: SIGMA_2K_SAFE_TRAINING_SLICE_V1 (1310 rows)*
*Next review: when any lane crosses its promotion gate or collapse threshold*
