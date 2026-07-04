# COURSE-00 — AW Cluster Deep Dive

Generated: 2026-07-01 01:17 UTC
Status: WATCHLIST_ONLY | NO_COURSE_01_IMPLEMENTATION

**Tracks audited:** Southwell (AW), Kempton (AW), Wolverhampton (AW), Lingfield (AW), Newcastle (Aw), Chelmsford (Aw)
**Combined N:** 51 | **Wins:** 11 | **SR:** 21.6%
**Total MP misses:** 86 | **6-10 band:** 31

---

## Southwell (AW)

- **Surface:** fibresand
- **Circuit:** sharp
- **Draw bias:** yes — side: low at 5f, 6f
- **Front runner advantage:** yes
- **Run-in:** 2f | Sprint chute: no
- **N:** 0 | **Wins:** 0 | **SR:** None
- **Avg winner SP:** None | **Avg pick SP:** None
- **SP gap:** None
- **MP misses total:** 30 | **6-10 band:** 13 | **4-6 band:** 12
- **Root cause:** unknown
- **Watchlist status:** WATCHLIST_ONLY
- **Required features:** DRAW_EYES_REQUIRED, PACE_EYES_REQUIRED, AW_PACE_EYES_REQUIRED
- **Notes:** Fibresand surface. Strong front-runner bias. Low draw in sprints. Pace angle critical.

## Kempton (AW)

- **Surface:** polytrack
- **Circuit:** flat_straight
- **Draw bias:** yes — side: low at 5f, 6f
- **Front runner advantage:** yes
- **Run-in:** 2.5f | Sprint chute: yes
- **N:** 0 | **Wins:** 0 | **SR:** None
- **Avg winner SP:** None | **Avg pick SP:** None
- **SP gap:** None
- **MP misses total:** 20 | **6-10 band:** 4 | **4-6 band:** 9
- **Root cause:** unknown
- **Watchlist status:** WATCHLIST_ONLY
- **Required features:** DRAW_EYES_REQUIRED, PACE_EYES_REQUIRED, AW_PACE_EYES_REQUIRED
- **Notes:** Triangular polytrack. Sprint chute exists. Low draw favoured in sprints. Front-runners very competitive.

## Wolverhampton (AW)

- **Surface:** tapeta
- **Circuit:** sharp
- **Draw bias:** yes — side: high_at_5f_low_at_6f at 5f, 6f
- **Front runner advantage:** yes
- **Run-in:** 2f | Sprint chute: no
- **N:** 0 | **Wins:** 0 | **SR:** None
- **Avg winner SP:** None | **Avg pick SP:** None
- **SP gap:** None
- **MP misses total:** 20 | **6-10 band:** 8 | **4-6 band:** 6
- **Root cause:** unknown
- **Watchlist status:** WATCHLIST_ONLY
- **Required features:** DRAW_EYES_REQUIRED, PACE_EYES_REQUIRED, AW_PACE_EYES_REQUIRED
- **Notes:** Tapeta. High draw at 5f, low draw at 6f. Front-runner hold-on common. Bias direction distance-dependent.

## Lingfield (AW)

- **Surface:** polytrack
- **Circuit:** sharp
- **Draw bias:** yes — side: high at 5f, 6f, 7f
- **Front runner advantage:** yes
- **Run-in:** 2f | Sprint chute: no
- **N:** 0 | **Wins:** 0 | **SR:** None
- **Avg winner SP:** None | **Avg pick SP:** None
- **SP gap:** None
- **MP misses total:** 16 | **6-10 band:** 6 | **4-6 band:** 8
- **Root cause:** unknown
- **Watchlist status:** WATCHLIST_ONLY
- **Required features:** DRAW_EYES_REQUIRED, PACE_EYES_REQUIRED, AW_PACE_EYES_REQUIRED
- **Notes:** Polytrack. High draw bias in sprints. Left-hand sharp. Front-runners hold well.

## Newcastle (Aw)

- **Surface:** tapeta
- **Circuit:** galloping
- **Draw bias:** yes — side: low at 5f, 6f
- **Front runner advantage:** yes
- **Run-in:** 3f | Sprint chute: no
- **N:** 44 | **Wins:** 9 | **SR:** 0.2045
- **Avg winner SP:** 8.86 | **Avg pick SP:** None
- **SP gap:** None
- **MP misses total:** 0 | **6-10 band:** 0 | **4-6 band:** 0
- **Root cause:** unknown
- **Watchlist status:** WATCHLIST_ONLY
- **Required features:** DRAW_EYES_REQUIRED, PACE_EYES_REQUIRED
- **Notes:** Tapeta. Galloping track despite AW surface. Low draw in sprints. Longer run-in than most AW tracks.

## Chelmsford (Aw)

- **Surface:** polytrack
- **Circuit:** sharp
- **Draw bias:** yes — side: low at 5f, 6f
- **Front runner advantage:** yes
- **Run-in:** 2f | Sprint chute: no
- **N:** 7 | **Wins:** 2 | **SR:** 0.2857
- **Avg winner SP:** 12.0 | **Avg pick SP:** None
- **SP gap:** None
- **MP misses total:** 0 | **6-10 band:** 0 | **4-6 band:** 0
- **Root cause:** unknown
- **Watchlist status:** WATCHLIST_ONLY
- **Required features:** DRAW_EYES_REQUIRED, PACE_EYES_REQUIRED
- **Notes:** Polytrack. Sharp oval. Low draw bias in sprints.

---

## AW Cluster — Key Findings

1. All 6 AW tracks have confirmed draw bias (known=yes).
2. All 6 have front_runner_advantage=yes.
3. DRAW_EYES_REQUIRED + PACE_EYES_REQUIRED + AW_PACE_EYES_REQUIRED flagged for AW tracks.
4. Mid-price 6-10 misses concentrated in Southwell, Kempton, Wolverhampton.
5. Surface type (fibresand vs polytrack vs tapeta) adds additional model gap.
6. containment_is_not_profit = True — identifying these tracks is not the same as fixing SR.
7. All rules WATCHLIST_ONLY. No implementation without COURSE-01 authorisation.