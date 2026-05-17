# VÉLØ 2K Sigma Training Plan V1

**Classification:** SIGMA_2K_TRAINING_PLAN_READY
**Created:** 2026-05-17
**Status:** ACTIVE — build in progress

---

## 1. What 2K Sigma Means

VÉLØ has accumulated approximately 2,000 sigma audit rows across 67+ race days. Each row represents one scored race where:
- VÉLØ produced a pre-race verdict (tier, VP, MDS, improvement score, router lane, etc.)
- A post-race result was confirmed (winner, SP, position)
- The prediction and result were reconciled through the sigma audit pipeline

At 2,000 rows, this is not test data. It is not scraped data. It is not synthetic.

**This is VÉLØ's own prediction history, closed and labelled by reality.**

That makes it the first genuine VÉLØ-owned internal training corpus.

---

## 2. Why This Is Internal VÉLØ-Owned Training Truth

Most ML training data is:
- Historical race form (public)
- Scraped odds and results (public)
- Racing Post ratings (licensed, external)

The 2K Sigma corpus is different. It contains:
- VÉLØ's own probability estimates at prediction time
- The signal stack active on the day (VP, MDS, improvement, SQPE, router)
- The actual outcome, confirmed through the scrape+sigma reconciliation pipeline
- The miss class — why VÉLØ got it wrong when it did

This corpus captures **VÉLØ's own prediction behaviour, not just race outcomes**. It can answer questions no external dataset can:
- Where is VÉLØ's model reliably calibrated?
- Where does it consistently over-estimate?
- Which signal combinations produce the most reliable outcomes?
- Where is the model blind despite confident-looking output?

This is forensic self-knowledge. Not retraining for excitement.

---

## 3. Leakage Rules

**Absolute prohibition on post-race leakage into prediction features:**

| Column Type | Allowed as Feature | Allowed as Label |
|---|---|---|
| VP, MDS, improvement score, SQPE | YES — pre-race | NO |
| SP, result_position, won, placed | NO | YES |
| actual_winner, actual_winner_sp | NO | YES |
| router lane (pre-race flag) | YES | NO |
| sigma_status, miss_class | NO | YES (diagnostic only) |
| cashrun class (pre-race) | YES | NO |

**The feature/label boundary is the race start.** Anything VÉLØ knew before the off is a valid feature. Anything that only became known after the off is a label.

Violation of this rule invalidates the entire audit. Every training dataset artifact must include a `leakage_confirmed_false` field set to `true` to be used.

---

## 4. Train/Test Split Rules

The 2K corpus is **NOT split for model retraining** at this stage.

The corpus is used for:
- Regime audit (signal zone performance)
- Feature ablation audit (which signal families help/hurt)
- Advisory policy testing (shadow only)

When and if model retraining is approved:
- Minimum 1,500 row training set
- Minimum 500 row held-out test set
- Test set must be from most recent dates (time-ordered, not random split)
- No leakage across split

**Current rule:** No model retraining from this corpus until a separate `SIGMA_RETRAINING_APPROVAL_V1` governance doc is created and reviewed.

---

## 5. Shadow-Only Rule

Any policy derived from the 2K corpus analysis must:
1. Be implemented as a shadow flag (advisory, not scoring)
2. Run for a minimum of 20 qualifying results before review
3. Pass explicit promotion gates before any live effect

Shadow policy candidates from this corpus:
- `midprice_router_suppression_advisory` (current: advisory, gates 3/4 passed)
- `MDS_HIGH_LANE` (pending: needs dedicated tracking infra)
- `IMPROVER_LANE` (pending: needs dedicated tracking infra)
- `COMPRESSION_SUPPRESS` (advisory confirmed, no scoring change)

**No direct scoring changes from this analysis.**

---

## 6. No Scoring Change Rule

The following files must not be modified as a result of 2K corpus analysis:

```
src/intelligence/velo_prime_ensemble.py    — ensemble weights
src/intelligence/sqpe.py                   — SQPE model
models/sqpe_v17/                           — model weights
models/improvement_model/                  — sidecar weights
scripts/run_prime_today.py                 — live scoring
app/engine/uma.py                          — UMA scoring
```

Any analysis that suggests a scoring change is a finding to document, not an action to take. Document the finding in the recommendation packet. Do not act on it.

---

## 7. Promotion Gates

For any shadow policy to move from advisory to active suppression or reporting change:

| Gate | Threshold |
|---|---|
| SR improvement | ≥ +1.5pp |
| Frame delta | ≥ -1.0pp (no material degradation) |
| ROI improvement | Positive |
| Loser:winner ratio | ≥ 4:1 in suppressed group |
| Sample size | n ≥ 50 suppressed |
| Operator review | Required — no automatic promotion |

For any shadow policy to move from active advisory to model-weight review discussion:

| Gate | Threshold |
|---|---|
| n (qualifying results) | ≥ 200 |
| SR improvement | ≥ +3.0pp sustained over 20+ days |
| Multiple regime consistency | Effect confirmed across ≥ 3 VP/MDS/SP regime partitions |
| No contradicting evidence | Zero contradicting findings in ablation audit |
| Separate governance doc | Required before any weight change discussion |

---

## 8. Required Reports

The following reports are required before the 2K corpus is considered complete:

| Report | Script | Status |
|---|---|---|
| Frozen training dataset | `build_sigma_training_dataset.py` | BUILD |
| Dataset manifest | (output of above) | BUILD |
| Regime audit | `sigma_2k_regime_audit.py` | BUILD |
| Feature ablation audit | `sigma_2k_feature_ablation_audit.py` | BUILD |
| Midprice suppression audit | `midprice_router_suppression_audit.py` | DONE |
| Recommendation packet | `VELO_2K_SIGMA_TRAINING_RECOMMENDATION_PACKET.md` | BUILD |

---

## 9. Stop Conditions

**Stop and do not proceed if any of the following occur:**

1. Dataset includes post-race fields as prediction features (leakage)
2. Row count does not reconcile with sigma evidence corpus (data integrity)
3. `consumed_live` is non-zero in any learning summary
4. Live state hash changes during the build process
5. Any script attempts DB mutation without explicit approval
6. Any scoring, model, router, or staking file is modified
7. Telegram is called without explicit operator approval
8. Any finding is interpreted as immediate live promotion
9. Git commit touches files outside the approved scope

**On any stop condition: halt, document the condition, and wait for operator review.**

---

*VELO_2K_SIGMA_TRAINING_PLAN_V1 — locked 2026-05-17*
