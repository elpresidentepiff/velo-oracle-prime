# J30-FOR — Forensic Operator Brief — 2026-06-30
**Generated:** 2026-06-30T23:29:55.261243+00:00  
**Mission:** J30-FOR — June 30 Full Forensic Pack With Exotics

---
## Loop Integrity
- Races: 46 | Matched: 46 | Parse retries: 3
- Identity failures: 0 | Missing winner SP: 0
- Full finish order: 46/46 races
- No-RPR available: 0/46 | New Build available: 46/46
- Note: **SINGLE_TOP_PICK_ONLY — only top-1 available per model; no ranked 2nd/3rd from any model**

---
## Answers to Operator Questions

**Q1 Day quality:** AVERAGE — Old VELO SR 23.9% vs historic avg ~25.7%
**Q2 RPR led:** VERDICT=RPR_HELPED | RPR gap interpretation=RPR_BOOSTS_WINNERS_MORE_THAN_MISSES | RPR boosts score in 38/46 races
**Q3 No-RPR vs Old:** No-RPR SR=n/a vs Old VELO SR=23.9% | Agreement=n/a | No-RPR better in 0 races
**Q4 New Build:** VERDICT=NEEDS_PROSPECTIVE_VALIDATION | NB SR=19.6% top-pick but in-actual-top3=50.0%
**Q5 NB long-price:** Long-price horses in NB actual-top3: 5 races
**Q6 EW signal:** EW: 83.3% place rate (n=6) — status=PARTIAL_EW_SIGNAL_NOT_PROFIT_PROOF — not changed by n=6 sample
**Q7 Exacta:** Consensus exacta box hits: 1/46 = 2.2% | EXOTICS_SIGNAL_ONLY
**Q8 Trifecta:** Consensus trifecta box hits: 0/46 = 0.0% | EXOTICS_SIGNAL_ONLY
**Q9 Best construction:** Old VELO top-1 as win anchor + consensus box for exotic fill. Minimal overlap (avg ~2 unique picks from 3 models) = low-cost box.
**Q10 Forward test:** Run 7-day prospective shadow of: (A) Old anchor + consensus box exacta. (B) EW candidates on field>=8. Both PAPER only, no live staking.

### Q11 Blocked by missing data
- pick_sp missing — EW and exotics cannot be profit-proven (need VFU-21)
- No ranked list per model — top-2/top-3 model containment unverifiable (SINGLE_TOP_PICK_ONLY)
- Exotic dividends unknown — all returns are SIMULATED_SP_PROXY_NOT_DIVIDEND_PROOF
- field_size gaps: 0 EW races missing field_size

### Q12 Next
- Continue VCP-03 burn-in daily triple.
- No model promotion.
- VFU-21 pick_sp backfill is the next structural repair — EW and exotics cannot be profit-proven without price data.
- New Build reclassification to VALUE_SCOUT / EXOTIC_FILL_CANDIDATE pending prospective validation.
- Old VELO RPR dependency audit across full 33-day corpus — cannot complete from single day.

---
## Next Action Recommendation
- **A+B:** Continue VCP-03 burn-in only — daily triple mandatory + VFU-21 pick_sp backfill next (operator decision required) — EW/exotics cannot be profit-proven without price data
- Deferred C: 7-day prospective shadow of New Build top-3 / EW / exotics — AFTER VCP-03 completes
- Deferred D: RPR dependency audit across full 33-day corpus — single day insufficient

## Reclassification Candidates
- New Build: VALUE_SCOUT / EXOTIC_FILL_CANDIDATE (pending prospective validation)
- Old VELO: STRIKE_ANCHOR / RPR_PUBLIC_STRENGTH_ANCHOR (pending 33-day RPR audit)
- EW Candidate: PLACE_SIGNAL_NOT_PROFIT_PROOF (pending VFU-21 pick_sp)

## Active Contradiction
- **C-01** (WARN): Mission Control source_truth=RP_MERGED_CLEAN but learning/promotion gate BLOCKED
  (GATE_PIPELINE_TRUTH_FALSE_PASS_NO_VERDICTS). Expected and valid. NOT SUPPRESSED.

## Final Classifications
- J30_FORENSIC_FULL_PACK_COMPLETE
- OLD_VELO_RPR_DEPENDENCY_AUDITED
- NEW_BUILD_TOP3_VALUE_CONTAINMENT_AUDITED
- EW_CANDIDATE_REALITY_AUDITED
- MIDPRICE_MISS_RECOVERY_AUDITED
- EXACTA_FORECAST_AUDITED
- TRIFECTA_TRICAST_AUDITED
- EXOTICS_CONTAINMENT_AUDITED
- EXOTICS_PROFIT_NOT_CLAIMED_WITHOUT_DIVIDENDS
- SP_PROXY_LABELLED_NOT_DIVIDEND_PROOF
- EW_PROFITABILITY_STATUS_REEVALUATED
- NEW_BUILD_VALUE_SCOUT_STATUS_EVALUATED
- OLD_VELO_RPR_ANCHOR_STATUS_EVALUATED
- CONTRADICTION_C01_RECORDED_NOT_SUPPRESSED
- MEMORY_CAPTURE_OPEN
- FAILURE_LEARNING_OPEN
- PROMOTION_LEARNING_GATED
- NO_VFU_21_START
- NO_VCP_04_START
- NO_LIVE_SCORING_CHANGE
- NO_VP_THRESHOLD_CHANGE
- NO_MODEL_PROMOTION
- NO_SUPABASE_WRITES
- NO_TELEGRAM_SEND
- CANONICAL_HORSE_PASSPORT_NOT_MUTATED
- REPORT_ONLY

---
REPORT_ONLY — J30-FOR complete.

---

# J30-FOR — Combined Race Table — 2026-06-30

| Race | Course | Off | FS | Winner | W-SP | 2nd | 3rd | Old | NoRPR | NB | EW | OldW | NoRPRW | NB-T3 | EW-P | Ex-Ord | Ex-Box | Tri-Box | Miss |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 922170 | Brighton | 2.43 | 12 | Big Time Rascal | 5.5 | Valsharah | Washington Hei | Port Hedland | — | Valsharah | N | . | . | Y | . | N | N | N | mid_priced_won |
| 922165 | Brighton | 3.13 | 7 | Antiquity | 10.0 | Marsh Benham | Rogue Dynasty | Antiquity | — | Spirit Of Albi | Y | W | . | N | P | N | N | N | n/a |
| 922168 | Brighton | 3.43 | 5 | Denby's Dream | 4.5 | Aneirin's Swor | Hove Ranger | Hove Ranger | — | She's Crafty | N | . | . | N | . | N | N | N | n/a |
| 922166 | Brighton | 4.13 | 8 | Bohemian Breeze | 5.5 | Annexation | Cartwheel | Twilight Guest | — | San Francisco  | N | . | . | N | . | N | N | N | mid_priced_won |
| 922167 | Brighton | 4.43 | 11 | Prefer The Sister | 3.25 | Havana Mojito | Dion Baker | Havana Mojito | — | Joycean Way | N | . | . | N | . | N | N | N | n/a |
| 922169 | Brighton | 5.15 | 6 | Norcross Brow | 1.73 | Venetian Roman | Pimentel | Norcross Brow | — | Electrocution | N | W | . | N | . | N | N | N | n/a |
| 922171 | Ffos Las | 6.09 | 8 | Egyptian Pharaoh | 2.2 | Dialstone | Liberate | Egyptian Phara | — | Adalo | N | W | . | N | . | N | N | N | n/a |
| 922172 | Ffos Las | 6.39 | 8 | Dark Whisper | 2.75 | Lean d'Aisling | Impierious | Dark Whisper | — | Impierious | N | W | . | Y | . | N | N | N | n/a |
| 922175 | Ffos Las | 7.09 | 9 | Angel's Call | 5.5 | King Of The Da | A Rose Adaay | King Of The Da | — | King Of The Da | Y | . | . | Y | P | N | N | N | n/a |
| 922174 | Ffos Las | 7.39 | 9 | Tonal | 3.5 | Dappled Light | Cypriot Diaspo | Cypriot Diaspo | — | Tonal | N | . | . | Y | . | N | N | N | n/a |
| 922176 | Ffos Las | 8.09 | 7 | Forever Glamorous | 2.5 | My Mate Mackle | Follow My Hear | Tanaka | — | Forever Glamor | N | . | . | Y | . | N | N | N | short_fav_won |
| 922173 | Ffos Las | 8.39 | 10 | Golden Flame | 9.5 | Merrijig | Cogital | Cogital | — | Sapphire Siroc | N | . | . | N | . | N | N | N | n/a |
| 922181 | Musselburgh | 2.00 | 7 | Mayor Of Maghera | 2.75 | Perfidia | Second Fiddle | Approaching Da | — | Perfidia | N | . | . | Y | . | N | N | N | short_fav_won |
| 922178 | Musselburgh | 2.30 | 7 | Bear Lee | 9.0 | Lexington Boom | Turnstile | Turnstile | — | Turnstile | N | . | . | Y | . | N | N | N | n/a |
| 922177 | Musselburgh | 3.00 | 10 | Haayimm | 6.0 | Dwindling Fund | Thunder Wonder | High Degree | — | Haayimm | N | . | . | Y | . | N | N | N | mid_priced_won |
| 922182 | Musselburgh | 3.30 | 9 | Classy Clarets | 3.0 | Monhammer | Ramon Di Loria | Monhammer | — | Classy Clarets | Y | . | . | Y | P | N | Y | N | n/a |
| 922179 | Musselburgh | 4.00 | 8 | Native Instinct | 3.5 | Diamont Katie | Abduction | Iris Dancer | — | The Gay Blade | Y | . | . | N | . | N | N | N | mid_priced_won |
| 922180 | Musselburgh | 4.30 | 6 | Is She Now | 2.25 | Falaise Blanc | Sophiesticate | Sophiesticate | — | Gemini Man | N | . | . | N | . | N | N | N | n/a |
| 922183 | Musselburgh | 5.05 | 10 | Invincible Crown | 5.0 | Sands Of Seve | Auntie Jo | Wee Mary | — | Wee Mary | N | . | . | N | . | N | N | N | mid_priced_won |
| 923663 | Roscommon | 5.30 | 18 | Damsel In Distress | 12.0 | Sea Of Rain | Nando Royale | Sea Of Rain | — | September Duke | N | . | . | N | . | N | N | N | n/a |
| 923664 | Roscommon | 6.00 | 14 | Elusive Echo | 3.0 | Almeiyda | Star Of Beauty | Star Of Beauty | — | Almeiyda | N | . | . | Y | . | N | N | N | n/a |
| 923665 | Roscommon | 6.30 | 18 | La La Lucrative | 6.0 | Toy Soldier | Givehertilxmas | Toy Soldier | — | Methgal | N | . | . | N | . | N | N | N | n/a |
| 923666 | Roscommon | 7.00 | 10 | Nermal | 3.5 | Vantage Code | Ella's Gold | Ella's Gold | — | Honouramongthi | N | . | . | N | . | N | N | N | n/a |
| 923667 | Roscommon | 7.30 | 13 | Thatwilldoso | 5.0 | Flying Fortres | Follow Me | Flying Fortres | — | Flying Fortres | N | . | . | Y | . | N | N | N | n/a |
| 923668 | Roscommon | 8.00 | 8 | Bosphorus Rose | 5.0 | Abbey Actress | Starford | Starford | — | Shaool | N | . | . | N | . | N | N | N | n/a |
| 923669 | Roscommon | 8.30 | 16 | Ashikita | 2.88 | Catherine Mage | Coolnagrattan | Ashikita | — | Coolnagrattan | N | W | . | Y | . | N | N | N | n/a |
| 923569 | Salisbury | 2.07 | 8 | Breacher | 13.0 | Squadron | Power Effort | Squadron | — | Jiro | N | . | . | N | . | N | N | N | n/a |
| 923570 | Salisbury | 2.37 | 6 | King Of Stars | 5.5 | The Thames Boa | Cayman Tai | Connie's Rose | — | Cayman Tai | N | . | . | Y | . | N | N | N | mid_priced_won |
| 923571 | Salisbury | 3.07 | 11 | Treasurer | 4.0 | Harry Knows | Flying Pirate | Metamouse | — | Metamouse | N | . | . | N | . | N | N | N | mid_priced_won |
| 923572 | Salisbury | 3.37 | 7 | Fleetwater | 17.0 | Sudden Flight | Addison Grey | Queue Dos | — | Sudden Flight | N | . | . | Y | . | N | N | N | outsider_won |
| 923573 | Salisbury | 4.07 | 7 | Aleatrix | 4.33 | Storming Point | Virtue Diligen | Storming Point | — | Storming Point | N | . | . | Y | . | N | N | N | n/a |
| 923574 | Salisbury | 4.37 | 3 | Gone By | 2.2 | Pearl River | Mythical Valen | Gone By | — | Gone By | N | W | . | Y | . | N | N | N | n/a |
| 923575 | Salisbury | 5.10 | 6 | Hot And Cold | 4.33 | Lyra Lea | John Harrison | Hot And Cold | — | Station Bar | N | W | . | N | . | N | N | N | n/a |
| 922093 | Stratford | 6.18 | 3 | Captain Cool | 4.5 | Tellherthename | Ice In The Vei | Captain Cool | — | Captain Cool | N | W | . | Y | . | N | N | N | n/a |
| 922094 | Stratford | 6.48 | 8 | Square d'Alboni | 2.1 | Penzance | Bound For Glor | Square d'Albon | — | Usyk | N | W | . | N | . | N | N | N | n/a |
| 922096 | Stratford | 7.18 | 8 | Lion Of The Desert | 7.0 | Tyson | Balboa | Tyson | — | Prince De Juil | N | . | . | N | . | N | N | N | n/a |
| 922097 | Stratford | 7.48 | 10 | Stellarmasterpiece | 5.0 | Brooklyn Lulla | Get The Value | Katzoff | — | Stellarmasterp | N | . | . | Y | . | N | N | N | mid_priced_won |
| 922095 | Stratford | 8.18 | 5 | Lakefield Flyer | 6.5 | Delpotro | Glenmalure Fly | Glenmalure Fly | — | Therhythmofthe | N | . | . | N | . | N | N | N | n/a |
| 922098 | Stratford | 8.48 | 7 | Thetype Istitle | 3.75 | Redbarn | Cool Million | Redbarn | — | Redbarn | N | . | . | Y | . | N | N | N | n/a |
| 923670 | Wexford | 2.20 | 6 | Soir De Garde | 6.5 | William Tell | Nadia's Boy | Scalpnagoon | — | Soir De Garde | N | . | . | Y | . | N | N | N | mid_priced_won |
| 923671 | Wexford | 2.50 | 13 | Mic Drop | 6.0 | Femme Magnifiq | Tequila Talkin | Mic Drop | — | Jane Eire | Y | W | . | N | P | N | N | N | n/a |
| 923672 | Wexford | 3.20 | 16 | Chosen Shant | 10.0 | L'Amiral Frome | Sea Of Doubt | Chosen Shant | — | Shannon Bank | N | W | . | N | . | N | N | N | n/a |
| 923673 | Wexford | 3.50 | 12 | Rue Taylor | 13.0 | Teenage Kiss | Malton Groove | Malton Groove | — | Harbour Highwa | Y | . | . | N | P | N | N | N | n/a |
| 923674 | Wexford | 4.20 | 8 | Lady Bluebird | 21.0 | Future Prospec | Pampar Lady | Farfromnowhere | — | Lady Bluebird | N | . | . | Y | . | N | N | N | outsider_won |
| 923675 | Wexford | 4.50 | 16 | Rockonliam | 2.0 | Ned In The Par | Jetovango | In The Trenche | — | Ned In The Par | N | . | . | Y | . | N | N | N | short_fav_won |
| 923676 | Wexford | 5.20 | 10 | Garnacho | 3.75 | Costacurta | Maxi Mac Gold | Londonofficeca | — | Costacurta | N | . | . | Y | . | N | N | N | mid_priced_won |