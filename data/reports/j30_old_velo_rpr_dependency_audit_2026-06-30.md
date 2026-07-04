# J30-FOR — Old VELO RPR Dependency Audit — 2026-06-30
**Generated:** 2026-06-30T23:29:55.263451+00:00  
**REPORT_ONLY — no scoring change, no model mutation.**

## Verdict
- Primary: **RPR_HELPED**
- RPR interpretation: `RPR_BOOSTS_WINNERS_MORE_THAN_MISSES`

## Win SR Comparison
| Model | n | Wins | SR | Top-3 containment |
|---|---|---|---|---|
| Old VELO | 46 | 11 | **23.9%** | 67.4% |
| No-RPR | 0 | 0 | n/a | n/a |

## RPR Score Gap Analysis
- Races where RPR boosts score (sqpe_v17 > sqpe_norpr): **38/46**
- Races where RPR drags score: 8
- Avg RPR gap on **wins**: 0.2907
- Avg RPR gap on **misses**: 0.2669
- RPR missing on top pick: 1
- OR missing on top pick: 7

## Pick Agreement
- Old VELO and No-RPR agree on same pick: **n/a** of races
- No-RPR won and Old missed: 0 races
- Old won and No-RPR missed: 11 races
- Both won same race: 0 races

## Winner SP Profile
| Model | Avg winner SP | Median winner SP |
|---|---|---|
| Old VELO | 4.43 | 2.88 |
| No-RPR | None | None |

## Limitation
> SINGLE_TOP_PICK_ONLY — no full ranked list per model; top-2/top-3 rank analysis not possible

---
REPORT_ONLY