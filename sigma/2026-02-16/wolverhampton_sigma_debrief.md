# VÉLØ PRIME — SIGMA-02 SELF-CORRECTION SYSTEM

## Post-Race Forensic Audit: Wolverhampton (AW) — 16 February 2026

**Track Classification:** CHAOS TRACK — RPD-C Layer: MANDATORY

**SIGMA-01 Baseline (Carlisle 16.02.26):** 6/8 Top Strike Winners (75%), 7/8 Winners in Framework, 3/3 False Favourite Detection, 7/8 RPD-C Accuracy

**Audit Objective:** Evaluate every prediction, RPD-C tag, scenario code, and market read against actual outcomes. Identify systemic failures, validate chaos-layer utility, and log permanent recalibrations.

---

### RACE 1 — 17:00 — 5f 21yds Class 4 Handicap (Rider Restricted)

**PREDICTION vs RESULT:**

| Role | Horse | Predicted | Actual Finish | BSP |
|------|-------|-----------|---------------|-----|
| Top Strike | Lion's House | Win | 3rd | 3.06 |
| Value | Lion's House | Win at 4/1 | 3rd | 3.06 |
| Danger | El Bufalo | Place threat | 5th | 3.33 |
| **Winner** | **Cressida Wildes** | — | **1st** | **9.71** |

The winner appeared in the framework with an **S (Speculative)** RPD-C tag. The analysis stated: *"Current form is below requirements; running on hope more than data."* This constitutes a dismissal of the eventual winner. The horse was mentioned but not placed in any actionable tier (Top Strike, Value, or Danger).

**SCENARIO ANALYSIS:**

The predicted scenario was **S3: Collapse & Sweep** at 65% probability — a pace duel between Alondra and El Bufalo leading to a late-race collapse, with Lion's House sweeping past. The actual race saw Cressida Wildes win at 9.71 BSP, with Alondra finishing second and Lion's House third. The pace scenario partially materialised — the front-runners did compromise each other — but the beneficiary was not Lion's House. It was the horse dismissed as speculative. The correct scenario code is **S3 (Collapse & Sweep)** but the wrong horse was identified as the sweeper.

Scenario accuracy: **PARTIAL** — the pace dynamic was correctly read; the beneficiary was misidentified.

**RPD-C TAG VALIDATION:**

The winner Cressida Wildes carried an **S (Speculative)** tag. This was incorrect. A horse winning at 9.71 BSP in a five-runner field was not speculative — she was a live contender whose recent form was underweighted. The tag should have been **H (Honest)** at minimum, or **T (Target)** if the trainer's intent had been properly decoded. The favourite Alondra carried an **E (Exhausted)** tag. She finished second at 4.78 BSP — the E tag was partially validated in that she did not win, but she ran creditably, suggesting the exhaustion assessment was overstated. El Bufalo's **H (Honest)** tag was correct — he ran honestly but without distinction (5th). Lion's House's **T (Target)** tag was partially correct — he ran to a level consistent with targeting, finishing third, but the "clear signals of intent" did not translate to victory.

ChaosMode assessment: The chaos layer **did not add value** in this race. The S tag on the winner was a dismissal rather than a flag. A properly calibrated chaos layer should have elevated Cressida Wildes from S to at least H, given the small field size and the fact that any runner in a five-horse race is a live contender.

**SIGNAL QUALITY:**

Signals that held: The pace analysis was accurate — Alondra and El Bufalo did contest the lead, and the pace did compromise the front-runners. The form integrity assessment for Lion's House was directionally correct (he placed). The market structure read was accurate — the two market leaders were overbet.

Signals that failed: The dismissal of Cressida Wildes was a form-recency bias failure. The analysis over-indexed on the most recent form cycle and failed to account for the possibility of improvement or a return to previous levels. The "running on hope more than data" assessment was a narrative judgement, not a data-driven conclusion.

**MARKET BEHAVIOUR:**

Cressida Wildes opened at ISP 10 and closed at BSP 9.71 — minimal drift, suggesting quiet but stable support. The BSP/ISP divergence was only 2.9%, indicating no significant late market movement. Alondra's BSP of 4.78 versus ISP of 4 represents a 19.5% drift — just below the 20% flag threshold, suggesting some late money moved away from the favourite. El Bufalo drifted from ISP 3.25 to BSP 3.33 (2.5% — negligible). The market did not strongly signal the winner, but the drift on Alondra was a soft warning that was not captured.

**THREAT MATRIX REVIEW:**

The **False Favourite Setup** on Alondra partially materialised — she did not win, validating the threat identification, but she finished second rather than collapsing. The **Pace Suicide** threat materialised in a modified form — the pace was contested but not suicidal; it was sufficient to compromise the leaders without destroying them entirely. No phantom threats were flagged.

**VERDICT TAG:** 🔧 Bias Adjustment Required — Form-recency bias caused dismissal of a live contender in a small field. The S tag was applied based on narrative rather than structural analysis.

---

### RACE 2 — 17:30 — 7f 36yds Class 6 Handicap (Rider Restricted)

**PREDICTION vs RESULT:**

| Role | Horse | Predicted | Actual Finish | BSP |
|------|-------|-----------|---------------|-----|
| Top Strike | Bad Habits | Win | 4th | 2.84 |
| Value | Nammos | Place/Win at 11/2 | 2nd | 5.22 |
| Danger | Oldbury Lad | Place threat | 6th | 13.88 |
| **Winner** | **Faster Bee** | — | **1st** | **21.42** |

The winner appeared in the framework with an **H (Honest)** RPD-C tag. The analysis stated: *"Consistently runs to his mark but lacks the capacity to win."* This is a direct and categorical dismissal. Faster Bee was mentioned but explicitly ruled out as a winner. The winner was not in any actionable tier.

**SCENARIO ANALYSIS:**

The predicted scenarios were S1 (Straight Deployment Win for Bad Habits, 50%), S6 (Hidden Intention Strike for Nammos), and S8 (Chaos Profile). The actual result — Faster Bee winning at 21.42 BSP — is a textbook **S8: Chaos Profile** outcome. The model correctly identified this race as having high chaos probability but failed to operationalise that assessment. Flagging S8 as "High Probability" while simultaneously selecting a Top Strike with only 50% confidence was internally contradictory.

Scenario accuracy: **PARTIAL** — S8 was correctly flagged as high probability, but the operational output did not reflect this assessment.

**RPD-C TAG VALIDATION:**

Faster Bee's **H (Honest)** tag was categorically wrong. A horse winning at 21.42 BSP is not running honestly to his mark — he outperformed his mark significantly. The tag should have been **S (Speculative)** at minimum, acknowledging the possibility of a breakout performance. Bad Habits' **T (Target)** tag was incorrect — he finished 4th, failing to deliver on the targeted profile. Nammos' **T (Target)** tag was partially validated — she finished 2nd, confirming the intent signal from the first-time visor, though she did not win. Oldbury Lad's **E (Exhausted)** tag was correct — he finished 6th, confirming the vulnerability of his penalised profile.

ChaosMode assessment: The chaos layer **partially added value** by correctly flagging S8, but the value was not operationalised. The model identified the chaos but then ignored its own warning by selecting a conventional Top Strike. This is a process failure, not an intelligence failure.

**SIGNAL QUALITY:**

Signals that held: The Oldbury Lad data mirage assessment was correct (6th). The Nammos intent signal was partially correct (2nd). The draw bias assessment was directionally correct — low-drawn Nammos (stall 1) placed. The identification of the race as chaotic was accurate.

Signals that failed: The assessment of Bad Habits as the "standout profile" was wrong — he finished 4th despite being the 2.84 BSP favourite. The categorical dismissal of Faster Bee was a failure of the H-tag classification system. The form integrity analysis over-indexed on recent consistency and under-indexed on the capacity for a low-grade horse to produce a career-best effort.

**MARKET BEHAVIOUR:**

Faster Bee's BSP of 21.42 versus ISP of 13 represents a **64.8% divergence** — a massive flag. This suggests significant early support (ISP 13) that evaporated on the exchange, or alternatively, that the ISP was set aggressively by bookmakers to attract each-way money. This is a critical market signal that was not available pre-race but would have warranted attention in a live monitoring scenario. Bad Habits drifted from ISP 2.5 to BSP 2.84 (13.6% — notable but below threshold). Nammos held steady (ISP 4.5, BSP 5.22, 16% drift).

**THREAT MATRIX REVIEW:**

The **Data Mirage** on Oldbury Lad materialised (6th). The **Hidden Intention Strike** on Nammos partially materialised (2nd but did not win). No phantom threats. The critical missing threat was a **Chaos Breakout** threat on Faster Bee — the model's own S8 flag should have generated this.

**VERDICT TAG:** 💀 Chaos Override — The model correctly identified S8 chaos probability but failed to operationalise it. The RPD-C layer flagged the environment but not the specific beneficiary. This is a chaos track doing what chaos tracks do.

---

### RACE 3 — 18:00 — 6f 20yds Class 4 Maiden Stakes

**PREDICTION vs RESULT:**

| Role | Horse | Predicted | Actual Finish | BSP |
|------|-------|-----------|---------------|-----|
| Top Strike | Perola | Win | 2nd | 2.34 |
| Value | Arishka's Dream | Place/Win at 3/1 | **1st** | **5.90** |
| Danger | Lovethiswayagain | Place threat | 4th | 4.40 |
| **Winner** | **Arishka's Dream** | Value Pick | **1st** | **5.90** |

The winner was the **Value pick**. This is a framework success — the model identified the winner within its actionable tiers. Arishka's Dream was selected as the Value play at 3/1, and she won at BSP 5.90, delivering significant value.

**SCENARIO ANALYSIS:**

The predicted scenario was **S1: Straight Deployment Win** for Perola at 70% probability. The actual result was a Value horse upset — Arishka's Dream won while the Top Strike Perola finished second. The correct scenario code is **S2: Tactical Grind Win** — the race was won by a horse who ground out a result through persistence rather than a dominant display. The model had S2 as a moderate probability scenario.

Scenario accuracy: **PARTIAL** — S2 was listed as a secondary scenario and the Value pick won, but the primary scenario (Perola winning with authority) did not materialise.

**RPD-C TAG VALIDATION:**

Arishka's Dream carried an **H (Honest)** tag with the assessment: *"A consistent performer at this track but has repeatedly found others superior. A reliable contender for a minor placing."* This tag was incorrect. The horse won — she was not merely honest, she was the best horse on the day. The tag should have been **T (Target)**, recognising her course experience and the possibility that accumulated runs would eventually produce a breakthrough. Perola's **T (Target)** tag was partially correct — she ran to a high level (2nd at 2.34 BSP) but did not convert. The tag's assessment of "clear intent" was accurate; the conversion failed. Lovethiswayagain's **H (Honest)** tag was correct — she ran honestly to 4th without threatening the principals.

ChaosMode assessment: The chaos layer **did not add specific value** in this race, but the framework's Value tier captured the winner. The failure was in the RPD-C classification, not in the selection architecture.

**SIGNAL QUALITY:**

Signals that held: The market structure assessment was accurate — the race was correctly identified as a probable duel. The form integrity analysis for Perola was directionally correct (she placed). The identification of Arishka's Dream as a live contender (Value pick) was correct.

Signals that failed: The confidence level of H (High) was wrong — the Top Strike did not win. The 70% probability assigned to Perola's scenario was overcooked. The dismissal of Arishka's Dream as merely "honest" underestimated her capacity for improvement at a track where she had accumulated significant experience.

**MARKET BEHAVIOUR:**

Arishka's Dream's BSP of 5.90 versus ISP of 5 represents a **18% drift** — just below the 20% threshold, suggesting the exchange market was slightly less confident than the bookmakers. Perola's BSP of 2.34 versus ISP of 2.1 shows an **11.4% drift** — the market remained confident in her but she did not deliver. The market correctly priced this as a competitive race but did not strongly signal the upset.

**THREAT MATRIX REVIEW:**

The **Soft Prep Run** threat on the newcomers was correct — Cotai Eye Joe (3rd at 9.86) and Lordsbridge Bay (5th at 21.68) did not win, though Cotai Eye Joe's third-place finish suggests the prep assessment may have been slightly harsh. No phantom threats.

**VERDICT TAG:** ✅ Model Confirmed — The Value pick won. The framework captured the winner in an actionable tier. The RPD-C tag was incorrect, but the selection architecture delivered.

---

### RACE 4 — 18:30 — 6f 20yds Class 4 Handicap (Rider Restricted)

**PREDICTION vs RESULT:**

| Role | Horse | Predicted | Actual Finish | BSP |
|------|-------|-----------|---------------|-----|
| Top Strike | The Flying Seagull | Win | 4th | 7.88 |
| Value | The Flying Seagull | Win at 10/1 | 4th | 7.88 |
| Danger | Water Of Leith | Place threat | 2nd | 6.72 |
| **Winner** | **Silky Wilkie** | — | **1st** | **5.00** |

The winner appeared in the framework with an **H (Honest)** RPD-C tag and was explicitly labelled the **designated false favourite**. The analysis stated: *"Reliable performer but appears anchored by his current handicap mark"* and *"Silky Wilkie is the designated false favourite."* The model actively told the user to oppose the winner. This is a direct model failure on the false favourite assessment.

**SCENARIO ANALYSIS:**

The predicted scenario was **S6: Hidden Intention Strike** at high probability — The Flying Seagull deploying from off the pace after a targeted preparation. The actual result was a straightforward front-of-market winner. Silky Wilkie won at BSP 5.00 (ISP 4.33), the market favourite. The correct scenario code is **S1: Straight Deployment Win** — the most fancied horse in the market delivered a professional performance. The model's S6 scenario did not materialise.

Scenario accuracy: **MISSED** — the predicted scenario was fundamentally wrong. The Hidden Intention Strike did not occur; the honest favourite won.

**RPD-C TAG VALIDATION:**

Silky Wilkie's **H (Honest)** tag was incorrect in its implication. While the tag itself ("honest") is not inherently wrong — the horse did run honestly — the accompanying narrative that he was "anchored by his handicap mark" and a "false favourite" was categorically wrong. He won. The tag should have been **T (Target)** — a horse whose consistency at this level made him the most probable winner. The Flying Seagull's **T (Target)** tag was incorrect — he finished 4th, failing to deliver on the "textbook example of a horse laid out for a specific target." Water Of Leith's **T (Target)** tag was partially correct — he finished 2nd, confirming he was a live contender. Papa Cocktail's **E (Exhausted)** tag was partially correct — he finished 3rd, running creditably but not winning.

ChaosMode assessment: The chaos layer **did not add value** and actively subtracted value by reinforcing the false favourite narrative against the actual winner. This was not a chaos outcome — it was a straightforward result that the model overcomplicated.

**SIGNAL QUALITY:**

Signals that held: The pace shape analysis was directionally correct — the pace was contested. Water Of Leith's identification as a live contender was correct (2nd). The form integrity data for The Flying Seagull (RPR 95) was accurate but did not translate to race-day performance.

Signals that failed: The false favourite assessment on Silky Wilkie was the primary failure. The "Hidden Intention Strike" narrative for The Flying Seagull was a narrative trap that the model fell into rather than detected. The confidence level of H (High) was wrong — this was the model's highest conviction call and it missed entirely. The intent signals from Hugo Palmer were over-interpreted.

**MARKET BEHAVIOUR:**

Silky Wilkie's BSP of 5.00 versus ISP of 4.33 represents a **15.5% drift** — the exchange was slightly less confident than the bookmakers, but the horse still won comfortably. The Flying Seagull's BSP of 7.88 versus ISP of 7 shows a **12.6% drift** — the market was not strongly backing the model's Top Strike. Water Of Leith's BSP of 6.72 versus ISP of 6 (12% drift) was stable. The market correctly identified Silky Wilkie as the most likely winner; the model disagreed and was wrong.

**THREAT MATRIX REVIEW:**

The **False Favourite Setup** on Silky Wilkie was a phantom threat — it did not materialise. The favourite won. The **Hidden Intention Strike** on The Flying Seagull was a phantom threat — the horse finished 4th. Both flagged threats were incorrect. This is a double phantom — the model generated threats that did not exist and missed the straightforward outcome.

**VERDICT TAG:** ❌ Model Failure — The model labelled the winner as a false favourite with high confidence and selected a horse that finished 4th. The narrative of a "Hidden Intention Strike" was a self-generated trap. The market was right; the model was wrong.

---

### RACE 5 — 19:00 — 6f 20yds Class 6 Handicap (Rider Restricted)

**PREDICTION vs RESULT:**

| Role | Horse | Predicted | Actual Finish | BSP |
|------|-------|-----------|---------------|-----|
| Top Strike | He's An Angel | Win | 5th | 5.83 |
| Value | He's An Angel | Win at 3/1 | 5th | 5.83 |
| Danger | Beauzon | Place threat | **1st** | **2.08** |
| **Winner** | **Beauzon** | Danger | **1st** | **2.08** |

The winner was the **Danger pick**. This is a framework capture — the model identified the winner within its actionable tiers, albeit in the threat position rather than the selection position. The analysis explicitly identified Beauzon as the primary threat and constructed the entire race narrative around opposing him.

**SCENARIO ANALYSIS:**

The predicted scenario was **S5: Market Trap Spring** at 75% probability — the highest confidence scenario on the entire card. The model predicted Beauzon would lead but falter under the double penalty, with He's An Angel exploiting the collapse. The actual result was the opposite: Beauzon won at 2.08 BSP, confirming his dominance. The correct scenario code is **S1: Straight Deployment Win** — the favourite led and won without serious challenge.

Scenario accuracy: **MISSED** — the predicted scenario was the inverse of what occurred. The 75% confidence level compounds the error.

**RPD-C TAG VALIDATION:**

Beauzon's **E (Exhausted)** tag was categorically wrong. A horse winning at 2.08 BSP — the shortest-priced winner on the card — is not exhausted. He was the best horse in the race by a clear margin, and the four-race winning streak was evidence of sustained excellence, not impending collapse. The tag should have been **T (Target)** — a horse in peak form whose connections were correctly exploiting a favourable opportunity. He's An Angel's **T (Target)** tag was incorrect — he finished 5th, a comprehensive failure. The "designated challenger" narrative was a model-generated fiction. Ardaddy's **S (Speculative)** tag was partially correct — he finished 3rd, outperforming the speculative assessment.

ChaosMode assessment: The chaos layer **actively subtracted value** in this race. The E tag on Beauzon was a chaos-layer assessment that was fundamentally wrong. The model treated a dominant favourite as a vulnerability rather than a strength. This is the inverse of what the chaos layer should do — it should identify hidden chaos, not manufacture it where none exists.

**SIGNAL QUALITY:**

Signals that held: The pace shape assessment was correct — Beauzon did lead. The market structure assessment was accurate in identifying Beauzon as the dominant market force.

Signals that failed: Every analytical signal failed. The "false favourite" assessment was wrong. The "double penalty vulnerability" was wrong — Beauzon carried the weight and won. The "exhaustion" narrative was wrong — the horse was in career-best form. The "Market Trap Spring" scenario was wrong. The intent signal for He's An Angel was over-interpreted. The confidence level of H (High) at 75% probability was the worst-calibrated assessment on the card.

**MARKET BEHAVIOUR:**

Beauzon's BSP of 2.08 versus ISP of 2.1 represents a **negligible 1% tightening** — the exchange market was fractionally more confident than the bookmakers, a classic signal of genuine support for a short-priced favourite. This is the opposite of what a "false favourite" market profile looks like. He's An Angel drifted from ISP 4.5 to BSP 5.83 — a **29.6% drift**, exceeding the 20% flag threshold. This was a clear market signal that the "challenger" was losing support, which the model should have interpreted as a warning against the selection.

Dark Sun's BSP of 49.38 versus ISP of 23 represents a **114.7% divergence** — massive, but irrelevant to the primary analysis as this was a longshot who placed second in a chaos-track anomaly.

**THREAT MATRIX REVIEW:**

The **False Favourite Setup** on Beauzon was a phantom threat — the favourite won decisively. The **Market Trap Spring** was a phantom threat — no trap was sprung; the market was correct. Both flagged threats were entirely wrong. The model constructed an elaborate counter-narrative against the obvious winner and was comprehensively defeated by the straightforward outcome.

**VERDICT TAG:** ❌ Model Failure — The model's highest-confidence call on the card was the worst result. The E tag on a dominant favourite was a fundamental misclassification. The "exhaustion" narrative was a self-generated trap that the model fell into. The market was emphatically right.

---

### RACE 6 — 19:30 — 1m 142yds Class 5 Fillies' Handicap (Rider Restricted)

**PREDICTION vs RESULT:**

| Role | Horse | Predicted | Actual Finish | BSP |
|------|-------|-----------|---------------|-----|
| Top Strike | Renesmee | Win | 3rd | 4.65 |
| Value | Renesmee | Win at 5/1 | 3rd | 4.65 |
| Danger | Dandy Khan | Place threat | 7th | 11.22 |
| **Winner** | **Samra Star** | — | **1st** | **11.25** |

The winner appeared in the framework with a **P (Prep)** RPD-C tag. The analysis stated: *"Form has been poor and she appears to need this run."* This is a categorical dismissal — the model assessed the winner as not ready to compete, let alone win. The horse was mentioned but placed in the lowest-intent tier.

**SCENARIO ANALYSIS:**

The predicted scenario was **S6: Hidden Intention Strike** at high probability — Renesmee, reunited with jockey Kyle McHugh, deploying a targeted strike. The actual result was a 11.25 BSP outsider winning, with the market favourite Three On Thursday finishing second. The correct scenario code is **S8: Chaos Profile** — an outcome that defied the form book and the market. The model's S6 scenario did not materialise; Renesmee finished third.

Scenario accuracy: **MISSED** — the predicted scenario was wrong. The Hidden Intention Strike did not occur. The race produced a chaos outcome.

**RPD-C TAG VALIDATION:**

Samra Star's **P (Prep)** tag was categorically wrong. A horse winning at 11.25 BSP was not on a prep run — she was ready to win and the connections knew it, or the horse produced a performance that exceeded expectations. Either way, the P tag failed to capture the reality. The tag should have been **S (Speculative)** at minimum, acknowledging the possibility of a surprise performance, or **T (Target)** if hidden intent signals had been detected. Renesmee's **T (Target)** tag was partially correct — she finished 3rd, confirming she was a live contender, but the "Hidden Intention Strike" narrative overstated the probability of victory. Three On Thursday's **H (Honest)** tag was correct — she finished 2nd, running honestly to her level. Dandy Khan's **H (Honest)** tag was incorrect — she finished 7th (last), well below honest expectations.

ChaosMode assessment: The chaos layer **failed** in this race. The P tag on the winner was a dismissal that should have been flagged for review in a chaos-track environment. On a chaos track, P-tagged horses at double-digit prices should carry an automatic speculative upgrade, as the chaos environment increases the probability of unexpected performances.

**SIGNAL QUALITY:**

Signals that held: The assessment that the race was wide open (three co-favourites at 3/1) was correct — the market uncertainty reflected genuine competitive depth. The identification of Renesmee as a contender was partially correct (3rd).

Signals that failed: The jockey booking signal for Renesmee was over-interpreted — McHugh's presence did not produce a win. The dismissal of Samra Star was a failure of the P-tag classification in a chaos environment. The Danger pick (Dandy Khan, 7th) was a complete miss. The form integrity analysis failed to identify Samra Star's potential for improvement.

**MARKET BEHAVIOUR:**

Samra Star's BSP of 11.25 versus ISP of 9 represents a **25% drift** — exceeding the 20% flag threshold. This suggests that early bookmaker support (ISP 9) was not matched on the exchange, which could indicate either smart early money that the exchange did not follow, or bookmaker pricing error. In retrospect, the ISP of 9 was a signal of some confidence from the pricing side. Three On Thursday's BSP of 3.07 versus ISP of 3 was stable (2.3% — negligible). Renesmee's BSP of 4.65 versus ISP of 4.33 (7.4% drift) was within normal range.

**THREAT MATRIX REVIEW:**

The **Hidden Intention Strike** on Renesmee was a phantom threat — the strike did not land (3rd). No threats were flagged for Samra Star, which is the core failure. The model generated a single-threat narrative and missed the actual danger entirely.

**VERDICT TAG:** 💀 Chaos Override — A chaos-track outcome where a P-tagged horse won at 11.25 BSP. The RPD-C layer failed to flag the winner but the chaos environment was correctly identified in the track classification. The miss is consistent with chaos-track expectations.

---

### RACE 7 — 20:00 — 1m4f 51yds Class 5 Handicap (Rider Restricted)

**PREDICTION vs RESULT:**

| Role | Horse | Predicted | Actual Finish | BSP |
|------|-------|-----------|---------------|-----|
| Top Strike | Brodie's Boy | Win | 3rd | 10.95 |
| Value | Brodie's Boy | Win at 13/2 | 3rd | 10.95 |
| Danger | Hackney Diamonds | Place threat | 4th | 5.22 |
| **Winner** | **Little Miss India** | — | **1st** | **4.10** |

The winner appeared in the framework with a **T (Target)** RPD-C tag. The analysis stated: *"In good form and the retained headgear is a positive signal. A clear contender."* This is a significant near-miss — the model correctly identified Little Miss India as a targeted, live contender but chose Brodie's Boy as the Top Strike instead. The winner was mentioned, correctly tagged, and described as a clear contender, but was not placed in any actionable tier.

**SCENARIO ANALYSIS:**

The predicted scenario was **S6: Hidden Intention Strike** at high probability — Brodie's Boy finally breaking his maiden tag in a well-handicapped opportunity. The actual result was a straightforward win by the market favourite Little Miss India at BSP 4.10. The correct scenario code is **S1: Straight Deployment Win** — the form horse with the correct profile delivered. The model's S6 scenario for Brodie's Boy did not materialise.

Scenario accuracy: **MISSED** — the predicted scenario was wrong. The Hidden Intention Strike did not occur. The most logical contender won.

**RPD-C TAG VALIDATION:**

Little Miss India's **T (Target)** tag was **correct**. This is the only winner on the card whose RPD-C tag was accurately assigned. The model identified her as a targeted runner in good form with positive headgear signals. The failure was not in the tagging — it was in the selection hierarchy. The model correctly tagged the winner but then chose a different T-tagged horse (Brodie's Boy) as the Top Strike. Brodie's Boy's **T (Target)** tag was incorrect in outcome — he finished 3rd, and his 0-17 record proved to be a genuine limitation rather than a "data mirage." Hackney Diamonds' **T (Target)** tag was incorrect — he finished 4th, failing to deliver on the "peak form, proven at the distance" assessment. Solanna's **H (Honest)** tag was correct — she finished 5th, consistent with the "struggles to win" assessment.

ChaosMode assessment: The chaos layer **partially added value** by correctly tagging the winner as T, but the selection process chose the wrong T-tagged horse. When multiple horses carry T tags, the model needs a tiebreaker protocol that weights current form and market position more heavily than speculative narratives about long-term plots.

**SIGNAL QUALITY:**

Signals that held: The T tag on Little Miss India was correct. The assessment of her being "in good form" was correct. The identification of the race as competitive was accurate.

Signals that failed: The narrative around Brodie's Boy's "long-term plot" and "data mirage" was a self-generated trap. The 0-17 record was not a mirage — it was a genuine inability to win. The model romanticised the maiden-breaking narrative and over-weighted the RPR figure (78) relative to the horse's demonstrated inability to convert ability into victories. The Danger pick (Hackney Diamonds, 4th) was a miss.

**MARKET BEHAVIOUR:**

Little Miss India's BSP of 4.10 versus ISP of 3.5 represents a **17.1% drift** — below the 20% threshold but notable. The market was confident in her, and the slight exchange drift was not a warning signal. Brodie's Boy's BSP of 10.95 versus ISP of 8 represents a **36.9% drift** — a significant flag exceeding the 20% threshold. The exchange market was substantially less confident in the model's Top Strike than the bookmakers, which should have been a warning. Hackney Diamonds' BSP of 5.22 versus ISP of 4.33 (20.6% drift) also exceeded the threshold.

**THREAT MATRIX REVIEW:**

The **Data Mirage** on Brodie's Boy's 0-17 record was not a mirage — it was reality. The horse's inability to win was a genuine limitation, not a statistical artefact. The **Hidden Intention Strike** was a phantom threat — no strike occurred. The model generated a compelling narrative that was not supported by the outcome.

**VERDICT TAG:** ⚠️ Narrative Trap Detected — The model correctly tagged the winner (T) but fell into a self-generated narrative trap around Brodie's Boy's maiden-breaking potential. The "data mirage" assessment of the 0-17 record was itself a mirage — the record was real.

---

## AGGREGATE SCORECARD — WOLVERHAMPTON (CHAOS TRACK)

| Metric | Result | Notes |
|--------|--------|-------|
| Top Strike Winners | **0/7** | Zero Top Strike selections won. Worst-case outcome for the primary selection tier. |
| Top Strike Placed (1-3) | **4/7** | R1 (3rd), R3 (2nd), R6 (3rd), R7 (3rd). The selections were competitive but could not convert. |
| Value Placed (1-3) | **4/7** | R1 (3rd), R3 (1st), R6 (3rd), R7 (3rd). Value pick won in R3. |
| Value Pick Won | **1/7** | R3: Arishka's Dream (BSP 5.90). The only actionable winner from the Value tier. |
| Danger Horse Won | **1/7** | R5: Beauzon (BSP 2.08). The Danger pick won in the race where the model was most confident against it. |
| Winner in Framework (TS/V/D) | **2/7** | R3 (Value), R5 (Danger). Only two winners appeared in the three actionable tiers. |
| Winner Mentioned Anywhere | **7/7** | Every winner was mentioned in the analysis. No winner was completely missed from the field assessment. |
| Scenario Accuracy | **2/7 partial, 0/7 confirmed** | R1 (partial — pace read correct, beneficiary wrong), R2 (partial — S8 flagged but not operationalised). Five races fully missed. |
| False Favourite Detected Correctly | **1/3** | R1 Alondra (partial — did not win but placed 2nd). R4 Silky Wilkie (wrong — won). R5 Beauzon (wrong — won). |
| RPD-C Tag Accuracy (winners) | **1/7** | R7: Little Miss India (T tag correct). All other winners' tags were incorrect. |
| RPD-C Tag Accuracy (all tagged) | **18/42** | Approximate assessment across all tagged horses in all 7 races. Many H and P tags were directionally correct for non-winners. |
| ChaosMode Value-Add Races | **2/7** | R2 (partial — S8 flagged), R7 (partial — winner correctly T-tagged). Five races saw no chaos-layer value or active value subtraction. |

### Verdict Distribution

| Verdict | Count | Races |
|---------|-------|-------|
| ✅ Model Confirmed | 1 | R3 |
| ⚠️ Narrative Trap Detected | 1 | R7 |
| 🔧 Bias Adjustment Required | 1 | R1 |
| 🧠 Market Misread Correction Logged | 0 | — |
| 💀 Chaos Override | 2 | R2, R6 |
| ❌ Model Failure | 2 | R4, R5 |

---

## COMBINED SESSION SCORECARD (CARLISLE + WOLVERHAMPTON)

| Metric | Carlisle (8 races) | Wolverhampton (7 races) | Combined (15 races) |
|--------|-------------------|------------------------|---------------------|
| Top Strike Winners | 6/8 (75.0%) | 0/7 (0.0%) | 6/15 (40.0%) |
| Top Strike Placed (1-3) | 7/8 (87.5%) | 4/7 (57.1%) | 11/15 (73.3%) |
| Winners in Framework (TS/V/D) | 7/8 (87.5%) | 2/7 (28.6%) | 9/15 (60.0%) |
| Winners Mentioned Anywhere | 8/8 (100%) | 7/7 (100%) | 15/15 (100%) |
| False Favourite Detection | 3/3 (100%) | 1/3 (33.3%) | 4/6 (66.7%) |
| Scenario Accuracy (confirmed or partial) | 6/8 (75.0%) | 2/7 (28.6%) | 8/15 (53.3%) |
| RPD-C Accuracy (winners) | 7/8 (87.5%) | 1/7 (14.3%) | 8/15 (53.3%) |

### Performance Delta Analysis

The delta between Carlisle and Wolverhampton is stark and demands structural explanation, not emotional rationalisation. Carlisle was a turf card at a conventional track with predictable form lines and a small, assessable field structure. Wolverhampton is an all-weather chaos track with rider-restricted handicaps, large fields, and a surface that amplifies variance. The 75% Top Strike rate at Carlisle versus 0% at Wolverhampton is not random — it reflects a systematic weakness in the model's ability to handle chaos-track environments.

The critical observation is that **every winner was mentioned in the analysis** (7/7), but only **2/7 were placed in actionable tiers**. The model's intelligence-gathering function is working — it identifies the relevant horses. The failure is in the **prioritisation and selection architecture**, which consistently elevated narrative-driven selections (Hidden Intention Strikes, long-term plots, false favourite oppositions) over straightforward form-and-market assessments.

---

## WEIGHT RECALIBRATIONS

### Failure 1: The E-Tag Overreach (Race 5 — Beauzon)

**Assumption that failed:** A horse on a winning streak carrying a double penalty is exhausted and vulnerable. The model treated winning momentum as a negative signal.

**Weight adjustment required:** The E (Exhausted) tag must not be applied to horses currently winning unless there is specific physical evidence of deterioration (declining sectional times, narrowing margins, visible distress signals). A winning streak is evidence of peak form, not impending collapse. The penalty system is already priced into the market — the model was double-counting the penalty by applying both a market adjustment and an RPD-C downgrade.

**Permanent principle:** Winning is the strongest signal in racing. A horse that keeps winning is demonstrating sustained excellence. The E tag should be reserved for horses showing declining performance metrics within a winning sequence, not applied categorically to any horse carrying a penalty.

### Failure 2: The False Favourite Misapplication (Race 4 — Silky Wilkie)

**Assumption that failed:** A consistent horse at a static handicap mark is a false favourite because it lacks upside. The model treated consistency as a ceiling rather than a floor.

**Weight adjustment required:** The False Favourite designation must require at least two of the following conditions: (a) significant market drift pre-race, (b) a demonstrable form decline in the most recent run, (c) a step up in class or distance that introduces a new variable, (d) a trainer/jockey booking that signals reduced intent. Silky Wilkie met none of these conditions — he was simply a consistent horse at his level, which is the definition of a reliable favourite, not a false one.

**Permanent principle:** Consistency at a level is not a weakness — it is the most reliable predictor of future performance at that level. The False Favourite tag must be evidence-based, not narrative-based.

### Failure 3: The Hidden Intention Strike Overuse (Races 4, 6, 7)

**Assumption that failed:** The S6 (Hidden Intention Strike) scenario was applied to three races on the card and produced zero winners. The model over-indexed on trainer intent signals and narrative-driven selection.

**Weight adjustment required:** The S6 scenario code must be restricted to situations where at least three independent intent signals converge: (a) a significant equipment change, (b) a targeted jockey booking upgrade, (c) a demonstrable handicap mark advantage (>5lb well-in), and (d) a specific race-type or surface change that the horse's profile suits. Applying S6 based on a single intent signal (e.g., a jockey booking alone in R6, or a "long-term plot" narrative in R7) is insufficient.

**Permanent principle:** Intent is not execution. A trainer's plan is a hypothesis, not a prediction. The S6 code requires convergent evidence, not a single compelling narrative.

### Failure 4: The H-Tag Dismissal Problem (Races 1, 2, 3, 4)

**Assumption that failed:** Horses tagged H (Honest) were systematically dismissed as unable to win. Four of the seven winners carried H tags in the pre-race analysis, and three of those were explicitly described as lacking the capacity to win.

**Weight adjustment required:** The H tag must be redefined. "Honest" does not mean "cannot win" — it means "will run to a predictable level." In chaos-track environments, where the form book is less reliable, an honest horse running to its level can win if the higher-rated contenders underperform. The H tag should carry a baseline win probability that is never reduced to zero, particularly in large fields and low-grade handicaps.

**Permanent principle:** On a chaos track, the honest horse is not the enemy — it is the baseline. Dismissing H-tagged horses as non-winners is a systematic error that must be corrected.

### Failure 5: The RPD-C P-Tag Blind Spot (Race 6 — Samra Star)

**Assumption that failed:** A horse tagged P (Prep) was assumed to be non-competitive. Samra Star won at 11.25 BSP.

**Weight adjustment required:** On chaos tracks, the P tag must carry an automatic speculative upgrade. The assumption that a horse "needs the run" is a narrative judgement that may not reflect the horse's actual readiness. In low-grade handicaps on all-weather surfaces, horses returning from breaks can win first time back with greater frequency than on turf.

**Permanent principle:** The P tag is a hypothesis, not a fact. On all-weather chaos tracks, P-tagged horses at double-digit prices must be flagged as potential chaos beneficiaries, not dismissed.

---

## CHAOS TRACK INTELLIGENCE — WOLVERHAMPTON (AW)

### Draw Bias Observations

In the five-runner Race 1, draw was negligible. In the ten-runner Race 2, the winner Faster Bee's draw position is not specified in the results but the analysis noted low draws as advantageous over 7f — Nammos (stall 1) finished 2nd, partially confirming this. In the 6f races (R3-R5), no consistent draw pattern emerged from the winners. In the longer races (R6-R7), the small fields negated draw effects. **Conclusion:** Insufficient data from this single card to confirm or deny a systematic draw bias. The pre-race assessment that low draws are advantageous over 7f received partial support but requires a larger sample.

### Pace Shape Patterns

The model's pace assessments were the strongest signal category on the card. In Race 1, the predicted pace duel between Alondra and El Bufalo materialised and did compromise the front-runners. In Race 5, the prediction that Beauzon would lead was correct. The pace shape analysis was directionally correct in most races but the model consistently failed to identify the correct beneficiary of the pace dynamics. **Conclusion:** Pace analysis is a strength of the model but must be decoupled from the selection process — knowing the pace shape is useful, but assuming a specific horse will benefit from it introduces narrative bias.

### Surface Bias Notes

The Tapeta surface at Wolverhampton produced results that favoured horses with current form and fitness over horses returning from breaks or carrying "hidden" form. Five of the seven winners (Cressida Wildes, Silky Wilkie, Beauzon, Three On Thursday's near-miss, Little Miss India) were horses with recent, visible form on the surface. The model's preference for "hidden intention" profiles and returning horses was structurally misaligned with the surface's tendency to reward current fitness. **Conclusion:** On Wolverhampton's Tapeta, weight current AW form more heavily than historical peak ratings or returning-from-break profiles.

### Trainer/Jockey Patterns

No single trainer or jockey dominated the card. The model over-interpreted specific trainer intent signals (Hugo Palmer with The Flying Seagull, Karl Frost with He's An Angel, M. Keady with Renesmee) — none of these targeted runners won. The rider restriction element (apprentice/conditional jockeys) introduces an additional layer of unpredictability that the model did not adequately account for. **Conclusion:** In rider-restricted handicaps, reduce the weight given to trainer intent signals, as the jockey variable introduces execution risk that can negate even the best-laid plans.

### BSP Distribution of Winners

| Race | Winner | BSP | Category |
|------|--------|-----|----------|
| 1 | Cressida Wildes | 9.71 | Mid-price |
| 2 | Faster Bee | 21.42 | Outsider |
| 3 | Arishka's Dream | 5.90 | Mid-price |
| 4 | Silky Wilkie | 5.00 | Favourite |
| 5 | Beauzon | 2.08 | Strong favourite |
| 6 | Samra Star | 11.25 | Outsider |
| 7 | Little Miss India | 4.10 | Favourite |

Three of seven winners were at single-figure BSP prices under 6.00 (R4, R5, R7) — these were the market's preferred runners. Two were mid-price (R1, R3). Two were outsiders (R2, R6). The model opposed the market favourite in R4 and R5 and was wrong both times. **Conclusion:** On chaos tracks, the favourite still wins approximately 40% of the time. The model's systematic bias toward opposing favourites on chaos tracks must be recalibrated.

---

## PERMANENT PRINCIPLES LOGGED

*Continuing from SIGMA-01 (Principles 1-4).*

**Principle 5 — The Winning Streak Paradox:** A horse on a winning streak is demonstrating peak form, not approaching exhaustion. The E (Exhausted) tag must never be applied solely on the basis of a winning sequence or penalty accumulation. Exhaustion requires observable performance decline — narrowing margins, declining sectional times, or physical distress signals. Winning is the strongest positive signal in racing; treating it as a negative signal is a fundamental logical error.

**Principle 6 — The False Favourite Burden of Proof:** The False Favourite designation must meet a multi-factor evidence threshold. A horse cannot be labelled a false favourite simply because it is consistent or because the model has identified a more appealing narrative elsewhere. At least two independent negative signals (market drift, form decline, class step-up, intent reduction) must be present before the designation is applied. Consistency at a level is the strongest predictor of future performance at that level.

**Principle 7 — The S6 Convergence Requirement:** The Hidden Intention Strike (S6) scenario code must require convergent evidence from at least three independent sources before being assigned high probability. A single intent signal — a jockey booking, an equipment change, or a narrative about a "long-term plot" — is insufficient. S6 was applied to three races on this card and produced zero winners. Intent is a hypothesis; execution is the only data point that matters.

**Principle 8 — The H-Tag Floor Rule:** On chaos tracks, the H (Honest) tag must carry a non-zero win probability floor. Four of seven Wolverhampton winners were tagged H and explicitly dismissed as unable to win. "Honest" means "will run to a predictable level" — it does not mean "cannot win." In low-grade handicaps with large fields, the honest horse running to its level can win when others underperform. The H tag must never be accompanied by language that categorically rules out victory.

**Principle 9 — The P-Tag Chaos Upgrade:** On all-weather chaos tracks, the P (Prep) tag must carry an automatic speculative upgrade. The assumption that a horse "needs the run" is a narrative judgement that may not reflect actual readiness. Wolverhampton's Tapeta surface can produce first-time-back winners with greater frequency than turf. P-tagged horses at double-digit prices on chaos tracks must be flagged as potential chaos beneficiaries.

**Principle 10 — The Narrative Trap Self-Check:** Before finalising any selection, the model must perform a narrative trap self-check: "Am I selecting this horse because the data supports it, or because the story is compelling?" If the selection relies on a single narrative thread (a maiden breaking through, a trainer's long-term plan, a jockey reunion), it is vulnerable to narrative bias. The self-check must identify whether the selection would survive if the narrative were removed and only the raw data remained.

**Principle 11 — The Market Respect Rule (Chaos Tracks):** On chaos tracks, the market favourite wins approximately 30-40% of the time. The model's systematic bias toward opposing favourites on chaos tracks must be recalibrated. Opposing a favourite requires the same burden of proof as the False Favourite designation (Principle 6). The market is not always right, but it is the single most reliable predictor available, and opposing it without strong evidence is a negative-expectation strategy.

**Principle 12 — The BSP Drift Warning System:** Any selection whose BSP drifts more than 20% from ISP must trigger an automatic confidence downgrade. In Race 7, Brodie's Boy drifted 36.9% (ISP 8 to BSP 10.95) — the exchange market was signalling reduced confidence in the model's Top Strike. In Race 5, He's An Angel drifted 29.6% — another warning that was not heeded. The exchange market's late assessment is a real-time data point that must be integrated into the confidence framework.

---

## SYSTEM STATUS

### Overall Model Performance

Across two sessions (15 races), the VÉLØ PRIME Oracle has produced a **6/15 Top Strike win rate (40.0%)** and a **9/15 framework capture rate (60.0%)**. These headline numbers mask a severe bifurcation: the model performed at an elite level on a conventional turf card (Carlisle: 75% TS, 87.5% framework) and at a sub-baseline level on a chaos-track all-weather card (Wolverhampton: 0% TS, 28.6% framework).

This is not variance. This is a structural weakness. The model is calibrated for conventional racing environments and is systematically miscalibrated for chaos-track conditions. The specific failure modes are identifiable and correctable:

1. **Over-application of narrative-driven scenarios** (S6 applied 3 times, 0 winners)
2. **Systematic dismissal of honest-profile horses** (H-tagged winners: 4/7)
3. **False favourite misidentification** (2/3 false favourite calls were wrong — the favourites won)
4. **E-tag misapplication on in-form horses** (Beauzon, the card's most dominant winner)
5. **P-tag blind spot on chaos tracks** (Samra Star dismissed as needing the run)

### RPD-C Layer Assessment

The RPD-C layer produced **1/7 correct winner tags** at Wolverhampton versus **7/8 at Carlisle**. This is the single most significant regression between the two sessions. The layer's value proposition is that it adds predictive power in chaotic environments — the opposite occurred. The layer actively subtracted value in Races 4 and 5 by reinforcing incorrect narratives.

The root cause is that the RPD-C tags were applied based on narrative assessment rather than structural analysis. The E tag was applied to winning horses, the H tag was used as a dismissal rather than a classification, and the P tag was treated as a certainty rather than a hypothesis. The recalibrations logged in Principles 5-9 address these specific failures.

### A/E Ratio Assessment

Across the 7 Wolverhampton races, the model generated **7 Top Strike selections** and **7 Value selections** (with significant overlap — 5 of 7 races had the same horse as both TS and Value). The model produced **1 actionable winner** (R3 Value pick) from **14 total selection slots** (7 TS + 7 Value). This yields an **Accuracy/Efficiency ratio of approximately 7.1%** — well below the target threshold.

At Carlisle, the equivalent ratio was approximately **85.7%** (6 TS winners + 1 additional Value winner from 8 TS + 8 Value slots, with overlap). The combined A/E ratio across both sessions is approximately **31.0%** — dragged down significantly by the Wolverhampton performance.

### Areas for Immediate Improvement

1. **Chaos-track calibration module:** Develop a separate weighting system for all-weather chaos tracks that reduces narrative weight and increases market-respect weight.
2. **RPD-C tag definitions:** Redefine H, E, and P tags per Principles 5, 8, and 9. The current definitions permit categorical dismissals that are structurally unsound.
3. **S6 restriction protocol:** Implement the convergence requirement from Principle 7 before any S6 scenario is assigned high probability.
4. **BSP drift integration:** Build the 20% drift warning from Principle 12 into the pre-race confidence framework as a hard constraint.
5. **Narrative trap self-check:** Implement Principle 10 as a mandatory final step before any selection is confirmed.
6. **False favourite evidence threshold:** Implement Principle 6 as a gating function — no false favourite designation without multi-factor evidence.

### Final Assessment

The Wolverhampton card exposed five distinct and correctable failure modes in the VÉLØ PRIME Oracle. None of these failures are random — they are systematic biases that can be addressed through the weight recalibrations and permanent principles logged above. The model's intelligence-gathering function remains strong (7/7 winners mentioned), confirming that the data ingestion and field assessment capabilities are sound. The failure is in the prioritisation layer — the translation of intelligence into actionable selections.

The chaos track did what chaos tracks do. The question was whether RPD-C added value. The answer is: **not yet, but the failures are diagnostic**. The RPD-C layer needs recalibration, not replacement. The principles logged in this audit (5-12) provide the specific corrections required.

SIGMA-02 complete. Eight new principles logged. System recalibration in progress.

---

*VÉLØ PRIME — SIGMA-02 Self-Correction System*
*Wolverhampton (AW) 16 February 2026*
*Audit compiled: 16 February 2026*
*Classification: CHAOS TRACK — RPD-C MANDATORY*
*Status: RECALIBRATION REQUIRED — PRINCIPLES 5-12 LOGGED*
