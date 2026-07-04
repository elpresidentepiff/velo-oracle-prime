======================================================================
RESULTS-01 OPERATOR BRIEF — VÉLØ FULL RESULTS TRUTH AUDIT
Generated: 2026-07-01 00:05 UTC
======================================================================

Q1. OVERALL PERFORMANCE
    Total rows: 2977 | Wins: 673 | Places: 823 | Misses: 1444
    Strike Rate: 22.6% | Frame Rate: 50.2%
    Date range: 102 unique dates in sigma dump

Q2. BIGGEST PRICE WINNERS (top 10 by SP):
  - UNKNOWN (Hexham 2026-03-25) @51.0 [X]
  - Call My Bluff (IRE) (Newbury 2026-04-17) @41.0 [B]
  - Roysse (Bangor-On-Dee 2026-05-16) @34.0 [A]
  - Pivotal Terms (GB) (Newcastle (Aw) 2026-04-13) @34.0 [C]
  - Sheamus Seimhiu (Leopardstown 2026-05-15) @26.0 [C]
  - Bella Union (IRE) (Bellewstown (Ire) 2026-04-18) @23.0 [C]
  - UNKNOWN (UNKNOWN 2026-03-15) @21.0 [UNKNOWN]
  - Believeinmenow (York 2026-05-15) @21.0 [B]
  - Joolianoss (IRE) (Ascot 2026-05-01) @19.0 [C]
  - Tuppence (FR) (Ayr 2026-04-17) @19.0 [X]

Q3. TIER BREAKDOWN
    Tier A: n=550 SR=38.2%
    Tier B: n=998 SR=23.2%
    Tier C: n=828 SR=15.9%

Q4. COURSE PERFORMANCE
    Edge confirmed (n>=10): Ffos Las, Musselburgh, Catterick, Brighton, Newmarket (July), Lingfield, Ripon, Worcester, Stratford, Wetherby, Salisbury, Hexham, Uttoxeter, Chester, York, Southwell, Pontefract, Curragh, Huntingdon, Kelso, Newcastle, Sligo (Ire), Killarney (Ire), Leopardstown (Ire), Naas (Ire), Wexford (Ire), Bellewstown (Ire)
    Drains (n>=10): Beverley, Down Royal, Ayr, Kilbeggan, Perth, Clonmel, Wexford, Ludlow, Curragh (Ire)
    Total unique courses: 104

Q5. RPR DEPENDENCY
    Verdict: RPR_HELPED
    Boosted n=128 SR=24.2%
    Dragged n=10 SR=20.0%
    Avg gap: 0.2484

Q6. NEW BUILD MODEL
    n=669 SR=15.4% Place=41.5%
    Top3 containment=0.4413 — CONTAINMENT IS NOT PROFIT

Q7. EW CANDIDATE LANE
    n=59 EW place rate=37.3%
    Verdict: EW_PARTIAL_DATA_NO_PROFIT_CLAIM
    Unknown field size: 15 | Unknown SP: 15

Q8. MID-PRICE MISS RECOVERY
    n=803 mid-price misses
    NB picked winner: 12 (1.5%)
    NoRPR picked winner: 15 (1.9%)

Q9. EXOTICS SIGNAL
    Knowable races: 718
    Exacta box rate: 8.8% (63 hits)
    Trifecta box rate: 1.0% (7 hits)
    *** DIVIDEND STATUS: UNKNOWN — NO PROFIT CLAIM ***

Q10. TRAINING VS SIGMA GAP
    Corpus status: LOADED_PYARROW_PANDAS
    Corpus rows: 1079
    Gap dates (in audit, not in training): 76

Q11. MISS CLASSIFICATION BREAKDOWN
    mid_priced_won: 803
    outsider_won: 245
    short_fav_won: 213
    market_decoy_followed: 187
    outsider_hedge_omitted: 40

Q12. DATA COVERAGE
    winner_sp present: 2876/2977
    pick_sp present: 1212/2977
    winner_name present: 2577/2977
    RP results races indexed: 1392
    Verdict races indexed: 3173

Q13. HARD CONSTRAINTS CONFIRMED
    NO_SUPABASE_WRITES: TRUE
    NO_LIVE_SCORING_CHANGE: TRUE
    NO_MODEL_PROMOTION: TRUE
    NO_TELEGRAM_SEND: TRUE
    CANONICAL_HORSE_PASSPORT_NOT_MUTATED: TRUE
    CONTAINMENT_IS_NOT_PROFIT: TRUE
    SP_PROXY_IS_NOT_DIVIDEND_PROOF: TRUE

Q14. CONTRADICTIONS FLAGGED
    EW profit not claimable (field/SP gaps): 30 rows affected
    Exotics dividend unknown: 718 races — NO profit claim
    winner_sp missing in audit: 101 rows

Q15. NEXT OPERATOR ACTIONS (gated)
    - Review COURSE_EDGE_CONFIRMED courses for lane targeting
    - Verify RPR verdict: RPR_HELPED — adjust weighting if MISLED
    - New Build SR=15.4% — gate promotion at n>=300
    - EW candidate: expand dividend data capture before any EW staking
    - Training gap: 76 dates not in training corpus

======================================================================
END OF OPERATOR BRIEF — REPORT_ONLY
======================================================================