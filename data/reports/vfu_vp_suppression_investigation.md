# VFU-09 — Kakirra / VP Suppression Investigation

**Generated**: 2026-06-14T22:29:41Z
**Investigation version**: VFU_09_VP_SUPPRESSION_INVESTIGATION_V1
**Canonical Passport mutated**: NO
**Live scoring changed**: NO
**Supabase written**: NO

> **Core doctrine**: VP is valid as a population signal. VP is not valid as a hard individual horse disqualifier. Identity-confirmed Passport evidence may reveal improving horses before VP crosses threshold.

---

## 1. Scale Finding — This Is Not a Niche Problem

| Metric | Value |
|---|---|
| Current-era wins with VP available | 307 |
| Wins with VP < 0.40 | **202** |
| Wins with VP ≥ 0.40 | 105 |
| % wins below VP threshold | **65.8%** |

> 202/307 (65.8%) of current-era wins had VP < 0.4. VP undercounting is the DOMINANT pattern, not a niche exception.

---

## 2. Kakirra — Deep Investigation

| Field | Value |
|---|---|
| Horse ID | RP_UID 8866972 (canonical) |
| VFU appearances | 3 |
| VFU wins | 3 |
| VFU strike rate | 100% |
| VP range | 0.175–0.343 |
| Avg VP | 0.265 |
| VP trend | FALLING |
| Courses | Bath, Newbury, Wolverhampton |
| All wins below VP threshold | **YES** |
| Passport win rate | 60% |
| Passport win rate last 3 | 100% |
| SP trajectory | SHORTENING |
| Position trend | IMPROVING |
| Margin trend | IMPROVING |
| AW specialist | True |
| OR | 60 |

### Per-run detail

| Date | Course | VP | Below 0.40 | Outcome | Tier |
|---|---|---|---|---|---|
| 2026-05-13 | Bath | 0.343 | **YES** | **WIN** | TIER_B_GOOD_NO_PICK_SP |
| 2026-05-15 | Newbury | 0.175 | **YES** | **WIN** | TIER_B_GOOD_NO_PICK_SP |
| 2026-06-02 | Wolverhampton | 0.277 | **YES** | **WIN** | TIER_B_GOOD_NO_PICK_SP |

### What Passport Knew (that VP missed)

- High career win rate (60%)
- SP trajectory shortening (market ahead of model)
- Position trend improving
- Margin trend improving
- AW specialist
- Win rate last 3: 100%

### VP Suppression Reasons

- `LOW_FEATURE_COVERAGE_SUPPRESSED_VP`
- `SOURCE_LAYER_SUPPRESSED_VP`
- `AW_SPECIALIST_UNDERCOUNTED`
- `SP_SHORTENING_UNDERWEIGHTED`
- `PASSPORT_IMPROVEMENT_AHEAD_OF_VP`
- `REPEAT_WINNER_UNDERCOUNTED`

### What VP Likely Missed

- No pick_sp on TIER_B rows → market signal absent → VP suppressed
- AW specialist pattern: model may not weight surface specialization
- Market shortening SP not reflected in VP at time of score
- Repeated winning pattern: improvement signal didn't accumulate within current era
- Horse improving faster than VP model recognised from available features

---

## 3. Man Is King — Deep Investigation

| Field | Value |
|---|---|
| Horse ID | RP_UID 3839266 (canonical) |
| VFU appearances | 2 |
| VFU wins | 2 |
| VFU strike rate | 100% |
| VP range | 0.180–0.279 |
| Avg VP | 0.230 |
| VP trend | RISING |
| Courses | Bath |
| All wins below VP threshold | **YES** |
| Passport win rate | 40% |
| Passport win rate last 3 | 67% |
| SP trajectory | SHORTENING |
| Position trend | IMPROVING |
| Margin trend | DECLINING |
| OR trajectory | FALLING |
| Class movement | DOWN |
| OR change last 3 | -11 |
| Setup run candidate | True |

### Per-run detail

| Date | Course | VP | Below 0.40 | Outcome | Tier |
|---|---|---|---|---|---|
| 2026-05-13 | Bath | 0.180 | **YES** | **WIN** | TIER_B_GOOD_NO_PICK_SP |
| 2026-06-05 | Bath | 0.279 | **YES** | **WIN** | TIER_C_LIMITED_IDENTITY |

### What Passport Knew

- High career win rate (40%)
- SP trajectory shortening (market ahead of model)
- Position trend improving
- Win rate last 3: 67%
- Setup run candidate flag

### VP Suppression Reasons

- `LOW_FEATURE_COVERAGE_SUPPRESSED_VP`
- `SOURCE_LAYER_SUPPRESSED_VP`
- `SP_SHORTENING_UNDERWEIGHTED`
- `PASSPORT_IMPROVEMENT_AHEAD_OF_VP`
- `REPEAT_WINNER_UNDERCOUNTED`
- `OR_FALLING_CLASS_DROP_PATTERN`

### Key difference from Kakirra

Man is King has OR_FALLING + MARGIN_DECLINING — signals the VP model likely penalises.
Despite these 'negative' signals, class_movement=DOWN and win_rate_last3=67% drove wins.
This is a different suppression mechanism to Kakirra: **OR_FALLING_CLASS_DROP_PATTERN**.

---

## 4. Control Group Comparison

| Passport Field | A: VP<0.40 Winners | B: VP≥0.40 Winners | C: VP<0.40 Non-winners |
|---|---|---|---|
| n | 102 | 55 | 220 |
| avg_win_rate | **26.7%** | 10.6% | 9.5% |
| avg_win_rate_last3 | **35.0%** | 15.2% | 8.0% |
| sp_shortening_rate | **52.9%** | 41.8% | 37.7% |
| position_improving_rate | **53.9%** | 36.4% | 30.0% |
| aw_specialist_rate | 7.8% | 5.5% | 11.8% |

### Key Findings

- VP_UNDERCOUNTING winners have HIGHER avg win rate (26.7%) than high-VP winners (10.6%). Model systematically misses horses with strong career records.
- VP_UNDERCOUNTING winners show MORE SP shortening (52.9%) than high-VP winners (41.8%). Market is ahead of model on these horses.
- VP_UNDERCOUNTING winners more likely to have improving position trend (53.9% vs 36.4%). Passport improvement signal predates VP recognition.
- Within VP < 0.40 group: winners avg_win_rate=26.7% vs non-winners avg_win_rate=9.5%. Passport win_rate strongly discriminates within low-VP population.
- SP shortening separates VP<0.40 winners (52.9%) from VP<0.40 non-winners (37.7%). Passport SP field is predictive within the low-VP cohort.

---

## 5. Suppression Reason Taxonomy

| Reason | Count (across cases) |
|---|---|
| `LOW_FEATURE_COVERAGE_SUPPRESSED_VP` | 2 |
| `SOURCE_LAYER_SUPPRESSED_VP` | 2 |
| `SP_SHORTENING_UNDERWEIGHTED` | 2 |
| `PASSPORT_IMPROVEMENT_AHEAD_OF_VP` | 2 |
| `REPEAT_WINNER_UNDERCOUNTED` | 2 |
| `AW_SPECIALIST_UNDERCOUNTED` | 1 |
| `OR_FALLING_CLASS_DROP_PATTERN` | 1 |

---

## 6. Passport Override Watchlist

**2 entries** — DRY-RUN ONLY. No live use. No Passport mutation.

| Horse | RP_UID | Wins | Avg VP | Confidence | Suggested Label |
|---|---|---|---|---|---|
| Kakirra | 8866972 | 3 | 0.265 | HIGH | `VP_UNDERCOUNTING_AW_SPECIALIST` |
| Man Is King | 3839266 | 2 | 0.230 | HIGH | `VP_UNDERCOUNTING_IMPROVING_PATTERN` |

---

## 7. Required Answers — Summary

### Q1: Why did Kakirra beat VP?

Kakirra is a confirmed AW specialist (Passport: aw_specialist=True) who won 3/3 with VP 0.175–0.343. Suppression causes: (1) All 3 races were TIER_B — no pick_sp, meaning the market signal that tracks SP shortening was absent from VP calculation. (2) The VP ensemble (SQPE_IMPROVEMENT_MDS_V1) does not capture AW surface specialization as a positive discriminator when a horse runs on turf. (3) VP actually FELL from 0.343 to 0.175 as Kakirra kept winning — the model was not learning from the horse's improving Passport trajectory within the current era. Passport knew: 60% career win rate, SP shortening, improving position and margin. VP missed: market signal (no pick_sp), surface specialization, repeat winner pattern.

### Q2: Did Man is King show same structure?

Partially. Man is King (RP_UID 3839266) won 2/2 with VP 0.180/0.279, both below threshold. Shared features with Kakirra: SP shortening, improving position, TIER_B tier for first win. Differences: Man is King has OR_FALLING and MARGIN_DECLINING trends which may have actively suppressed VP (model saw declining horse). However, win_rate_last3=66.7% and class_movement=DOWN — falling class with recent form is a known win trigger. Passport knew: strong recent win rate (67% last 3), SP shortening. VP likely penalised: falling OR, declining margins, course switching, jockey changes.

### Q3: VP failure, Passport success, or both?

Both, but asymmetrically. VP is functioning correctly as a population signal — VP>=0.40 SR=43.2% is valid and holds. The failure is VP as an individual disqualifier for identity-confirmed improving horses. Passport success: career win rate, SP shortening, and position trend all predict VP<0.40 wins better than they predict VP<0.40 non-wins (win_rate: 26.7% vs 9.5%, SP shortening: 52.9% vs 37.7%). VP sees raw race-level features. Passport accumulates career trajectory. These are complementary, not competing signals.

### Q4: Which Passport fields were predictive?

- win_rate (VP<0.40 winners: avg 26.7% vs non-winners: 9.5%)
- sp_trajectory=SHORTENING (winners: 52.9% vs non-winners: 37.7%)
- position_trend=IMPROVING (winners: 53.9% vs non-winners: 30.0%)
- win_rate_last3 > 0.40 — very strong recent form not captured by VP
- For Kakirra specifically: aw_specialist=True (model doesn't weight AW form positively on turf)

### Q5: What did VP likely miss?

- No pick_sp on TIER_B rows: market signal (SP shortening) absent from VP at score time
- Career win rate: SQPE uses recent form features, not career win rate directly
- AW specialist pattern: model may penalise turf runs for AW specialist or vice versa
- Repeat winner accumulation: VP is race-by-race, not horse-trajectory-aware
- Class drop + falling OR = VP penalises, but it's a winning pattern for some horses
- Setup run candidate: Passport flags this, VP doesn't have this signal

### Q6: Enough evidence for Override Watchlist?

Yes — sufficient evidence for a DRY-RUN watchlist only. Quantitative case: 202/307 (65.8%) of current-era wins had VP<0.40. Among RP_UID horses with VP<0.40, win_rate discriminates winners from non-winners (26.7% vs 9.5%, delta +17.2pp). SP shortening and position trend also discriminate. Kakirra (3/3 wins, RP_UID confirmed) and Man is King (2/2 wins, RP_UID confirmed) are sufficient for watchlist entry. NOT sufficient for live doctrine.

### Q7: Enough evidence for live doctrine?

No. Current evidence: 2 horses, 5 VFU wins total. Need: minimum 20+ identity-confirmed VP_UNDERCOUNTING winners with RP_UID, prospective validation (not retrospective current-era), and operator gate at each threshold. The 202 VP<0.40 win count includes name-only matches — not usable for live doctrine without identity confirmation.

### Q8: Should VP threshold remain unchanged?

Yes. VP threshold (0.40) remains valid. The population signal holds: VP>=0.40 SR=43.2% vs baseline 26.4%. Changing the threshold would broaden the gate without improving signal quality. The correct response is a Passport Override layer ABOVE the VP gate, not a threshold change.

### Q9: Should Passport override remain dry-run?

Yes, dry-run only. Watchlist has 2 entries (Kakirra, Man is King). Architecture: VP Gatekeeper + Passport Override Watchlist + Course/price/context filter. No live use until: n>=20 identity-confirmed VP_UNDERCOUNTING winners, prospective validation, operator decision at each gate.

### Q10: What must VFU-10 focus on?

VFU-10: Expand VP_UNDERCOUNTING population. Identify all 202 VP<0.40 WIN rows with RP_UID, score them against Passport profiles, build a priority ranking of override candidates. Specifically: (1) Which of the 102 RP_UID VP<0.40 wins show the Kakirra/Man-is-King pattern? (2) Is win_rate > 0.25 + SP_SHORTENING a reliable watchlist filter? (3) How many prospective candidates qualify? Do NOT: change live scoring, merge Passports, promote doctrine.

---

## 8. Hard Rule Confirmations

| Check | Status |
|---|---|
| VP threshold unchanged | CONFIRMED |
| Live doctrine NOT promoted | CONFIRMED |
| Passport Override DRY-RUN only | CONFIRMED |
| Canonical Horse Passport NOT mutated | CONFIRMED |
| No Supabase writes | CONFIRMED |
| No live scoring change | CONFIRMED |
| No model promotion | CONFIRMED |
| No Telegram send | CONFIRMED |
| No Racing API restoration | CONFIRMED |
| No Mar–Apr extraction | CONFIRMED |

## Final Classifications

- `VFU_09_VP_SUPPRESSION_INVESTIGATION_COMPLETE`
- `VFU_08_VERDICT_DISTRIBUTION_RECONCILED`
- `KAKIRRA_VP_UNDERCOUNTING_CONFIRMED`
- `MAN_IS_KING_VP_UNDERCOUNTING_REVIEWED`
- `PASSPORT_OVERRIDE_WATCHLIST_CREATED`
- `VP_REMAINS_POPULATION_SIGNAL_NOT_HARD_DISQUALIFIER`
- `NO_VP_THRESHOLD_CHANGE`
- `NO_LIVE_DOCTRINE_PROMOTION`
- `PASSPORT_OVERRIDE_DRY_RUN_ONLY`
- `CANONICAL_HORSE_PASSPORT_NOT_MUTATED`
- `NO_MAR_APR_EXTRACTION`
- `NO_LIVE_SCORING_CHANGE`
- `NO_SUPABASE_WRITES`
- `NO_MODEL_PROMOTION`
- `NO_TELEGRAM_SEND`
- `NO_RACING_API_RESTORATION`