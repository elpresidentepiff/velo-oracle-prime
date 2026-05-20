ACCA REPLAY AUDIT - LATEST

Status: SHADOW_OPERATOR_ONLY
Total days replayed: 7
Regime accuracy: 0.5714
Dates replayed: 2026-05-05, 2026-05-04, 2026-05-03, 2026-05-02, 2026-05-01, 2026-05-07, 2026-04-29
Dates skipped: 2026-05-06

Fold hit rates:
- 2-fold: generated=5 hits=3 hit_rate=0.6
- 3-fold: generated=4 hits=2 hit_rate=0.5
- 4-fold: generated=4 hits=1 hit_rate=0.25
- 5-fold: generated=1 hits=1 hit_rate=1.0
- 6-fold: generated=1 hits=1 hit_rate=1.0

Trap false-positive rate: 0.0956
Trusted-leg failure rate: 0.2264

Per-day summary:
- 2026-05-05 | scanned=32 | metadata=1.0 | cashrun=PRESENT | enrichment=USED | regime=ACCA_DAY_WEAK actual=NO_ACCA_DAY match=False | traps=15 | trapped_winners=1 | trusted_failures=1
  - 2-fold: generated=True result=MISS
  - 3-fold: generated=False result=SUPPRESSED
  - 4-fold: generated=False result=SUPPRESSED
  - 5-fold: generated=False result=SUPPRESSED
  - 6-fold: generated=False result=SUPPRESSED
  - calibration: Loosen trap calibration on high-VP / high-industry legs and review decoy thresholds.
- 2026-05-04 | scanned=59 | metadata=1.0 | cashrun=PRESENT | enrichment=USED | regime=NO_ACCA_DAY actual=NO_ACCA_DAY match=True | traps=34 | trapped_winners=3 | trusted_failures=3
  - 2-fold: generated=False result=SUPPRESSED
  - 3-fold: generated=False result=SUPPRESSED
  - 4-fold: generated=False result=SUPPRESSED
  - 5-fold: generated=False result=SUPPRESSED
  - 6-fold: generated=False result=SUPPRESSED
  - calibration: Loosen trap calibration on high-VP / high-industry legs and review decoy thresholds.
- 2026-05-03 | scanned=36 | metadata=1.0 | cashrun=PRESENT | enrichment=USED | regime=ACCA_DAY_MEDIUM actual=ACCA_DAY_WEAK match=False | traps=16 | trapped_winners=2 | trusted_failures=2
  - 2-fold: generated=True result=HIT
  - 3-fold: generated=True result=INCOMPLETE
  - 4-fold: generated=True result=INCOMPLETE
  - 5-fold: generated=False result=SUPPRESSED
  - 6-fold: generated=False result=SUPPRESSED
  - calibration: Loosen trap calibration on high-VP / high-industry legs and review decoy thresholds.
- 2026-05-02 | scanned=55 | metadata=1.0 | cashrun=MISSING_OPTIONAL | enrichment=USED | regime=ACCA_DAY_MEDIUM actual=NO_ACCA_DAY match=False | traps=36 | trapped_winners=3 | trusted_failures=3
  - 2-fold: generated=True result=MISS
  - 3-fold: generated=True result=INCOMPLETE
  - 4-fold: generated=True result=INCOMPLETE
  - 5-fold: generated=False result=SUPPRESSED
  - 6-fold: generated=False result=SUPPRESSED
  - calibration: Loosen trap calibration on high-VP / high-industry legs and review decoy thresholds.
- 2026-05-01 | scanned=1 | metadata=0.0 | cashrun=PRESENT | enrichment=MISSING_OPTIONAL | regime=NO_ACCA_DAY actual=NO_ACCA_DAY match=True | traps=0 | trapped_winners=0 | trusted_failures=0
  - 2-fold: generated=False result=SUPPRESSED
  - 3-fold: generated=False result=SUPPRESSED
  - 4-fold: generated=False result=SUPPRESSED
  - 5-fold: generated=False result=SUPPRESSED
  - 6-fold: generated=False result=SUPPRESSED
  - calibration: Keep suppression logic unchanged; day filter behaved correctly.
- 2026-05-07 | scanned=41 | metadata=1.0 | cashrun=MISSING_OPTIONAL | enrichment=USED | regime=ACCA_DAY_STRONG actual=ACCA_DAY_STRONG match=True | traps=15 | trapped_winners=2 | trusted_failures=1
  - 2-fold: generated=True result=HIT
  - 3-fold: generated=True result=HIT
  - 4-fold: generated=True result=HIT
  - 5-fold: generated=True result=HIT
  - 6-fold: generated=True result=HIT
  - calibration: Loosen trap calibration on high-VP / high-industry legs and review decoy thresholds.
- 2026-04-29 | scanned=38 | metadata=1.0 | cashrun=MISSING_OPTIONAL | enrichment=USED | regime=ACCA_DAY_MEDIUM actual=ACCA_DAY_MEDIUM match=True | traps=20 | trapped_winners=2 | trusted_failures=2
  - 2-fold: generated=True result=HIT
  - 3-fold: generated=True result=HIT
  - 4-fold: generated=True result=MISS
  - 5-fold: generated=False result=SUPPRESSED
  - 6-fold: generated=False result=SUPPRESSED
  - calibration: Loosen trap calibration on high-VP / high-industry legs and review decoy thresholds.

Calibration recommendations:
- Replay more dates before trusting 5-fold or 6-fold output beyond shadow.
- Review trap logic on strong-VP winners incorrectly flagged as decoys.
- Run a Racing API enrichment on/off ablation before claiming structural lift.
- Run a CASHRUN on/off comparison once enough overlapping days exist.
- Require full metadata coverage before any 5-fold or 6-fold is generated.
