# 300-RUNNER REVIEW PACKET — 2026-05-20

**Triggered:** runner_prediction_snapshots crossed n=300 (now 538 rows)
**Gate date:** 2026-05-20 | **Source:** RP_MERGED | **Run IDs:** 2 (latest: `2026_05_20_32cc27f9_1779275802075`)
**Snapshot coverage:** 33 races / 269 runners (latest run)

---

## VERDICT SUMMARY

| Metric | Value | Baseline |
|---|---|---|
| Strike rate | **6.2%** | 20% |
| Frame rate | **25.0%** | 48.4% |
| Wins | 2 (Earthsong GOW 7.50, Allibaba WAR 4.30) | — |
| Placed | 6 | — |
| Misses | 24 | — |
| No result | 1 (GOW 8.20 abandoned) | — |

**Below baseline. Not a fluke. Structural.**

---

## FINDING #1 — SCORING COLLAPSE IN RP_MERGED RACES

This is the primary finding. The runner_prediction_snapshots expose a systematic failure.

### VP Score Uniformity by Race

| Race | Runners | Unique VP Groups | Largest Tied Group | Max VP |
|---|---|---|---|---|
| rp_AYR_20260520_1.42 | 4 | **1 (fully uniform)** | 4/4 | 0.2500 |
| rp_AYR_20260520_2.12 | 8 | 3 | 6/8 | 0.1590 |
| rp_AYR_20260520_2.42 | 12 | **1 (fully uniform)** | 12/12 | 0.0833 |
| rp_AYR_20260520_3.12 | 8 | 2 | 7/8 | 0.1379 |
| rp_AYR_20260520_3.42 | 12 | **1 (fully uniform)** | 12/12 | 0.0833 |
| rp_AYR_20260520_4.12 | 9 | 3 | 7/9 | 0.1376 |
| rp_AYR_20260520_4.42 | 9 | **1 (fully uniform)** | 9/9 | 0.1111 |
| rp_AYR_20260520_5.15 | 8 | **1 (fully uniform)** | 8/8 | 0.1250 |
| rp_FFO_20260520_2.50 | 6 | 2 | 5/6 | 0.1960 |
| **rp_FFO_20260520_3.20** | 5 | **5 (fully individualized)** | 1/5 | **0.5479** |
| rp_FFO_20260520_3.50 | 8 | 2 | 6/8 | 0.1612 |
| rp_FFO_20260520_4.20 | 4 | 2 | 3/4 | 0.3185 |
| rp_FFO_20260520_4.50 | 7 | 3 | 3/7 | 0.2809 |
| rp_FFO_20260520_5.22 | 8 | 3 | 4/8 | 0.2250 |
| rp_GOW_20260520_5.10 | 10 | 6 | 3/10 | 0.1520 |
| rp_GOW_20260520_5.45 | 9 | 5 | 5/9 | 0.1437 |
| rp_GOW_20260520_6.20 | 15 | 6 | 7/15 | 0.2148 |
| rp_GOW_20260520_6.50 | 10 | 3 | 7/10 | 0.1372 |
| rp_GOW_20260520_7.20 | 4 | **1 (fully uniform)** | 4/4 | 0.2500 |
| rp_GOW_20260520_7.50 | 9 | 3 | 4/9 | 0.1980 |
| rp_WAR_20260520_2.30 | 9 | 2 | 8/9 | 0.1234 |
| rp_WAR_20260520_3.00 | 7 | 2 | 6/7 | 0.1639 |
| rp_WAR_20260520_3.30 | 4 | 2 | 3/4 | 0.2744 |
| rp_WAR_20260520_4.00 | 7 | 4 | 3/7 | 0.2376 |
| rp_WAR_20260520_4.30 | 7 | 2 | 6/7 | 0.1639 |
| rp_WAR_20260520_5.00 | 9 | 3 | 7/9 | 0.1319 |
| rp_YAR_20260520_5.35 | 11 | 5 | 5/11 | 0.2917 |
| rp_YAR_20260520_6.10 | 8 | 2 | 7/8 | 0.1262 |
| rp_YAR_20260520_6.40 | 8 | 3 | 6/8 | 0.1614 |
| rp_YAR_20260520_7.10 | 5 | 2 | 4/5 | 0.2438 |
| rp_YAR_20260520_7.40 | 8 | 4 | 5/8 | 0.1847 |
| rp_YAR_20260520_8.10 | 9 | 7 | 2/9 | 0.4871 |

**6 races had fully uniform VP (1/n each — random selection).**
**20 additional races had the majority of runners tied at the top VP group.**
**Only 1 race (FFO 3.20, Kenobi) was fully individualized.**

### The Uniform VP Signature

In fully uniform races, every runner receives `VP = 1/field_size`:

| Uniform race | Field | VP each |
|---|---|---|
| AYR 1.42 | 4 | 0.2500 |
| AYR 2.42 | 12 | 0.0833 |
| AYR 3.42 | 12 | 0.0833 |
| AYR 4.42 | 9 | 0.1111 |
| AYR 5.15 | 8 | 0.1250 |
| GOW 7.20 | 4 | 0.2500 |

**This is the ensemble outputting equal probability = 1/n for every runner.** It is not scoring. It is assigning flat weights to an undifferentiated field. The top pick then becomes whoever appears first in the stored list — effectively random.

---

## FINDING #2 — MDS AND IMPROVEMENT ALSO UNIFORM

In all 6 fully uniform races — and in most tied-group races — **MDS and improvement_score are also identical across all runners in the top group.** For example:

```
AYR 5.15 all 8 runners:
  VP=0.1250  MDS=0.0110  IMP=0.0872  PLACE=0.3382  (all identical)

WAR 5.00 top 7 runners:
  VP=0.1319  MDS=0.0109  IMP=0.0872  PLACE=0.3108  (all identical)
```

The sidecar models are also not differentiating. This means the feature input pipeline is producing near-identical feature vectors for runners in the same race when RP_MERGED is the source.

**The #73 finding is confirmed in live data:** RP intelligence exists in the building but is not flowing into the scoring contracts.

---

## FINDING #3 — MID-PRICE WINNER ANALYSIS (16 CASES)

| Question | Answer |
|---|---|
| Winner visible in snapshots | 15/16 (94%) |
| Winner beat top pick on MDS | 0/16 |
| Winner beat top pick on improvement | 0/16 |
| Winner beat top pick on VP | 0/16 |
| Winner beat top pick on place_prob | 0/16 |
| Avg winner SP | 5.46 |

### Winner Rank Distribution (mid-price misses)

| Winner rank | Count | Meaning |
|---|---|---|
| 1 | 5 | 2nd in VELO's scoring list |
| 2 | 2 | 3rd in VELO's scoring list |
| 4 | 5 | 5th in VELO's scoring list |
| 5 | 1 | 6th in VELO's scoring list |
| 6 | 2 | 7th in VELO's scoring list |
| None | 1 | Not in snapshots |

**5 out of 16 mid-price winners were ranked 2nd by VELO.** The system was almost right in 31% of cases. The winner was right there — one position below the top pick, with identical or near-identical scores.

### Per-Race Detail (16 mid-price misses)

| Race | Course | Top Pick | Winner | SP | Winner Rank | delta_VP | delta_MDS | delta_IMP |
|---|---|---|---|---|---|---|---|---|
| rp_AYR_20260520_2.12 | Ayr | A Lady Forever | Jet Warrior | 7.5 | 4 | 0.0 | 0.0 | 0.0 |
| rp_AYR_20260520_3.12 | Ayr | Classy Al | Military Girl | 3.25 | 4 | 0.0 | 0.0 | 0.0 |
| rp_AYR_20260520_4.42 | Ayr | Golden Valour | Native Honey | 5.0 | 4 | 0.0 | 0.0 | 0.0 |
| rp_AYR_20260520_5.15 | Ayr | Evelyn'S Phoenix | Glorious Kitty | 5.5 | 1 | 0.0 | 0.0 | 0.0 |
| rp_FFO_20260520_4.50 | Ffos Las | Bridget Mary | Lynsey Larue | 10.0 | 1 | 0.0 | 0.0 | 0.0 |
| rp_FFO_20260520_5.22 | Ffos Las | Barafundle Bay | Kates Choice | 5.0 | 6 | -0.202 | 0.0 | 0.0 |
| rp_GOW_20260520_5.10 | Gowran | Independent Expert | Gloriously Glam | 5.5 | 6 | -0.067 | 0.0 | 0.0 |
| rp_GOW_20260520_6.50 | Gowran | Alto Sax | Ballymagreehan | 5.0 | 1 | 0.0 | 0.0 | 0.0 |
| rp_WAR_20260520_3.00 | Warwick | Edgewell | Yes And Yes | 5.0 | 5 | 0.0 | 0.0 | 0.0 |
| rp_WAR_20260520_3.30 | Warwick | Full Force Gale | Rangatira Jack | 3.25 | 2 | 0.0 | 0.0 | 0.0 |
| rp_WAR_20260520_4.00 | Warwick | Crest Of Stars | Il Va De Soi | 4.0 | 1 | 0.0 | 0.0 | 0.0 |
| rp_WAR_20260520_5.00 | Warwick | Bluegrass | Brendas Asking | 5.5 | 1 | 0.0 | 0.0 | 0.0 |
| rp_YAR_20260520_6.10 | Yarmouth | Ardad Steve | Peaceful Warrior | 6.5 | 4 | 0.0 | 0.0 | 0.0 |
| rp_YAR_20260520_6.40 | Yarmouth | Dream Pirate | Jack Sparowe | 10.0 | 2 | 0.0 | 0.0 | 0.0 |
| rp_YAR_20260520_7.40 | Yarmouth | Charming Fellow | Tilani | 3.12 | 4 | 0.0 | 0.0 | 0.0 |
| rp_YAR_20260520_8.10 | Yarmouth | Tennessee Gold | Berry Clever | 3.25 | None | — | — | — |

**delta_VP=0.0 in 14/16 cases means the winner and the top pick had exactly the same VP score.** The system cannot distinguish them. Selection within tied VP groups is effectively arbitrary.

---

## FINDING #4 — SHORT-FAV ANALYSIS (6 CASES)

| Race | Top Pick | Winner | Winner SP | Winner Rank |
|---|---|---|---|---|
| rp_AYR_20260520_1.42 | Crystal Queen | Ruler's Pride | 1.30 | 2 |
| rp_FFO_20260520_3.20 | Kenobi | The Flaggy Shore | 2.50 | 1 |
| rp_FFO_20260520_4.20 | Hell Hound | Loki's Mischief | 2.75 | 2 |
| rp_GOW_20260520_7.20 | Lady Mairen | Sparan Nua | 3.00 | 2 |
| rp_WAR_20260520_2.30 | Alex The Great | Rebel Tribesman | 1.33 | 5 |
| rp_YAR_20260520_7.10 | Golden Garden | Iwantmytimewithyou | 2.62 | 1 |

4/6 short-fav winners were ranked 1 or 2 by VELO. Market was right where VELO was not. **This is the SP gate failure zone** — short-price horses (SP<3.0) that VELO deprioritises because SP data is unavailable from RP_MERGED source.

Note: FFO 3.20 (Kenobi, VP=0.5479) is the fully differentiated race. The winner (The Flaggy Shore) was ranked 1st in VELO's scoring — but Kenobi had VP=0.5479 vs The Flaggy Shore's lower VP. VELO's top pick was the wrong horse despite good differentiation. SP gate would have caught Kenobi: `sp_dec=None → SP_MISSING → UNAUTHORISED_SELECTION`. Execution was already blocked; display was the failure, now fixed by PR #84.

---

## FINDING #5 — WIN RACE PROFILE

Both wins came from horses with VP < 0.20. This is telling.

| Race | Horse | VP | MDS | IMP | PLACE | Tier |
|---|---|---|---|---|---|---|
| GOW 7.50 | Earthsong | 0.198 | 0.011 | 0.087 | 0.311 | — |
| WAR 4.30 | Allibaba | 0.164 | 0.013 | 0.087 | 0.407 | — |

In both WIN races, the top-group VP tied multiple runners at the same value. VELO selected the right horse arbitrarily (by list order, not signal differentiation). **These were correct selections achieved without real scoring signal.** They are not evidence of the model working; they are evidence of lucky coin-flips within tied groups.

---

## FINDING #6 — THE SINGLE WORKING RACE: FFO 3.20 (KENOBI)

This was the only race where VELO produced true per-runner differentiation:

| Runner | VP | MDS | IMP | PLACE |
|---|---|---|---|---|
| Kenobi (rank 0) | 0.5479 | 0.016 | 0.100 | 0.600 |
| (Runner 2) | ~0.28 | — | — | — |
| (Runner 3–5) | <0.15 | — | — | — |

Kenobi's VP=0.5479 is exceptional relative to the field. The RP features **did flow into scoring here** — this is what a correctly-scored race looks like.

Outcome: MISS (The Flaggy Shore won at SP 2.50). The prediction was scorable and discriminating. It was simply wrong.

**This race is the target state for all races.** Today only 1/33 achieved it.

---

## ROOT CAUSE: WHY RP_MERGED FAILS TO DIFFERENTIATE

The uniform VP = 1/n pattern shows that SQPE is receiving **the same feature vector for all runners** in a race. Possible causes:

1. **Form features not extracted per-runner from RP PDFs** — the colour card (F_0012) and postdata (F_0011) contain form strings, OR ratings, TS ratings, jockey claim, but the feature engineering step does not consume them into per-runner feature vectors.

2. **Features derived from Racing API profiles** (trainer/jockey stats, course records) are not available under RP_MERGED source → all runners fall back to default/mean feature values.

3. **The `or_compression_score` and `postdata_score`** are stored in the snapshot (columns present) but are effectively 0 for RP_MERGED races without enrichment.

The evidence from the #73 field-to-decision audit:
- `postdata_score` = STORED_ONLY (not live-weighted)
- `or_compression_score` = FEATURE_DICT_ONLY
- `spotlight_score` = SHADOW_ONLY

These represent RP intelligence that exists in the pipeline but does not flow into SQPE's scoring weights. Under Racing API source, runner-specific features (SP history, trainer form) would differentiate the field. Under RP_MERGED without enrichment, runners appear identical to the model.

---

## DETERMINATIONS

### Was the mid-price winner ranked 2 or 3?
**Yes — 5/16 were ranked 2nd (rank=1), 2/16 ranked 3rd (rank=2).** In 44% of mid-price misses the winner was in VELO's top 3. The selection was wrong but the shortlist was partially right.

### Did winner MDS beat top-pick MDS?
**No — 0/16.** MDS did not distinguish winner from top pick because MDS scores were identical (uniform feature inputs).

### Did winner improvement beat top-pick improvement?
**No — 0/16.** Same reason.

### Did winner VP beat top-pick VP?
**No — 0/16.** By definition the top pick has the highest VP; winner tied or was lower.

### Did winner place_prob beat top-pick place_prob?
**No — 0/16.** Same reason.

### Did top pick trigger MIDPRICE_SUPPRESS_TOP?
Cannot determine without running midprice_hunter analysis on today's data. Score is stored (`mark_compression_score` present in schema) but review needed.

### Was the winner visible but suppressed?
**15/16 were visible in snapshots.** They were not suppressed — they were **scored identically to the top pick and lost the arbitrary tie-break.** The suppression is not a routing decision; it is a scoring collapse.

### Was the winner invisible because RP fields were not consumed?
**Partially.** The winner was present in the snapshot but scored identically to the competition. The RP-sourced per-runner differentiation that would distinguish them (OR rating compression, form trajectory, jockey stats) was not consumed into scoring.

---

## COUNCIL ORDERS — CONFIRMED

| Order | Status |
|---|---|
| NO live scoring changes | HOLD |
| NO panic weight changes | HOLD |
| NO execution changes | HOLD |
| 300-runner review triggered | DONE — this document |
| PR #84 merged | **MERGED** (main, 2026-05-20) |
| Scrape results from SL | **DONE** — `scripts/ops/scrape_results_sl.py` permanent |

---

## NEXT ENGINEERING ORDERS (PRIORITY ORDER)

### Order 1 — RP Feature Enrichment (HIGH PRIORITY)
Wire `postdata_score`, `or_compression_score`, and `spotlight_score` into live SQPE feature input. Until this is done, RP_MERGED races will continue to produce near-random selections.

Target: every race reaches FFO 3.20 differentiation standard (unique VP per runner).

### Order 2 — Uniform VP Detection + Suppression
When all runners in a race share VP = 1/n (uniform), the race should be flagged `SCORING_COLLAPSED`. Operator sees this. No execution allowed under this flag.

Detection: `if len(set(vps)) == 1: flag = SCORING_COLLAPSED`

### Order 3 — Tie-Break Improvement
For races with the top group tied at the same VP, implement secondary tie-breaking using available RP signals: postdata_score → spotlight_score → or_compression_score → alphabetical (current fallback).

This will not fix the problem but will make tie-breaking less arbitrary.

### Order 4 — Mid-Price Hunter (#78) — Activate Monitoring Mode
With 538 snapshots now available, begin monitoring for the MIDPRICE_SUPPRESS_TOP pattern. The hunter should flag races where:
- Our top pick VP is in the 0.15–0.35 band
- AND a competitor has comparable or higher postdata/OR signals
- AND winner SP falls in 3.0–8.5 zone

This is watchlist-only, no execution changes.

### Order 5 — Sigma Results — Wire Sporting Life Fallback
`scripts/ops/scrape_results_sl.py` now exists. Wire as automatic fallback in sigma when Racing API `/results` returns 401/403. Cache-first logic already in place.

---

## SECURITY NOTE

Multiple operational tables including `runner_prediction_snapshots` have RLS disabled. Do NOT flip RLS during this review — it will break reads/writes without policies. Schedule as separate hardening issue (Issue #85 or similar) after current sprint closes.

---

*Document generated: 2026-05-20 | Evidence basis: 538 runner_prediction_snapshots, scraped Sporting Life results, sigma audit n=32*
