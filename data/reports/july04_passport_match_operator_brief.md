# July 4 2026 — Passport Identity Match Repair — Operator Brief
Generated: 2026-07-04 | REPORT_ONLY | local analysis only, no Supabase, no scoring

---

## Correction to the mission's working assumption

The premise was that "some of the 243 misses will be spelling/normalisation failures" and coverage could plausibly reach 60-75%. After running a proper identity-confidence pass, that isn't what the data shows: **the repair only recovers 2 additional runners (239 → 241, 49.6% → 50.0%)**. The remaining 239 misses are not spelling variants — they are names that genuinely do not appear anywhere in the 6,221-horse passport bank, most likely because those horses have no prior race history captured in the passport backfill (new/rarely-run horses, or courses/regions the backfill didn't cover as deeply — Bellewstown and Naas are Irish tracks, worth checking separately whether the passport bank's Irish coverage is systematically thinner).

One thing worth flagging: my first pass of this analysis produced 4 "high-confidence" fuzzy matches, but manual inspection caught that 2 of them were **false-positive risks, not real repairs** — "Beagle Bay" matched to "Eagle Bay" (0.947 similarity) and "He'S Waliim" matched to "Yes Waliim" (0.90 similarity) are very likely two different real horses that happen to share most letters, not the same horse with a data-entry variant. I tightened the acceptance rule to only auto-count matches explainable by punctuation, accent, spacing, or a leading "A"/"The" article — genuine formatting differences, not generic character similarity — and re-ran. Both of those candidates are now held in `FUZZY_AMBIGUOUS_BLOCKED` for manual review, not silently counted. This matches your explicit instruction that ambiguous matches must stay blocked.

## 1. Total runners?

482, across 8 venues (Bellewstown 104, Beverley 49, Carlisle 42, Leicester 55, Naas 64, Newmarket 60, Nottingham 46, Sandown 62), 56 races.

## 2. Exact matches?

239 (case/whitespace-insensitive exact name match).

## 3. Normalized matches?

2 — both were the leading-article pattern: "Daughters Love" → "A Daughters Love" (Leicester 3:20) and "Boy Named Susie" → "A Boy Named Susie" (Sandown 3:35). Both of these already had their "A "-prefixed exact form present elsewhere in the same race's runner list too, confirming this is genuinely how RP sometimes truncates the article on one PDF type but not another.

## 4. Fuzzy high-confidence matches?

**0.** After tightening the rule to exclude generic character-similarity acceptance, nothing qualified. This is the correct, conservative outcome — better 0 than 2 false identity merges.

## 5. Ambiguous blocked?

2 — "Beagle Bay" (Sandown 2:25) and "He'S Waliim" (Sandown 4:10). Both are held for your/Steven's manual judgment, not auto-resolved either way.

## 6. No passport found?

239.

## 7. Final usable passport coverage count and percentage

**241 / 482 = 50.0%.**

## 8. Is matching still name-only?

Yes — unchanged from the initial assessment. No `horse_id`/RP UID exists anywhere in today's ingested racecards.

## 9. Is horse_id/RP UID still missing?

Yes, confirmed still absent across all 482 runners in all 8 venue files.

## 10. Is the card safe for scoring?

**No — not for a full live/promotion-grade `--verdicts-only` run.** Coverage sits at 50.0%, below your stated 60% floor for anything better than HIGH identity risk, and matching remains name-only (no RP UID cross-check available as a second signal).

## 11. If safe, what scoring mode is allowed?

N/A given the above — see readiness gate. If you want to proceed anyway, the safest option (not recommended without explicit sign-off) would be a `--verdicts-only` run with the operator's explicit understanding that roughly half the field is scoring without passport-derived features (career runs, win/place rate, layoff, class movement, etc. — the `pp_*` feature block would be null for those runners), not that the run itself is unsafe to execute mechanically.

## 12. If not safe, what source is still missing?

- A racecard source that carries `horse_id`/RP UID (the standard RP racecard/API feed, not these 6 PDF types), which would let passport lookup use the reliable UID path instead of name-only.
- Passport bank depth for whatever population of horses the 239 no-match runners represent — worth checking whether they cluster by course/region (e.g., Irish tracks) before assuming it's random gap noise.

---

## Required Classifications
- JULY04_PASSPORT_MATCH_REPAIR_COMPLETE
- NAME_ONLY_IDENTITY_MATCHING_DISCLOSED
- PASSPORT_COVERAGE_RECALCULATED — 241/482 = 50.0% (up from 239/482 = 49.6%)
- FALSE_POSITIVE_RISK_CAUGHT_AND_CORRECTED — 2 candidates initially auto-accepted, then reclassified to blocked after manual inspection
- READY_TO_SCORE_GATE_UPDATED
- NO_SUPABASE_WRITES
- NO_SCORING_RUN
- NO_SIGMA_RUN
- NO_RUNNER_SNAPSHOT_WRITE
- NO_TELEGRAM_SEND
- NO_MODEL_TRAINING
- REPORT_ONLY
