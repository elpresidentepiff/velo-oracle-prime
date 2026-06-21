# Radical Edge Discovery
Generated: 2026-06-19T23:43:53.401655+00:00

## Decision
- Go live now: False
- Next build: RADICAL_VELO_GATED_ARCHITECTURE_SHADOW
- Why: Evidence supports separation of scorer, Sigma gate, passport memory, and late market sidecar. It does not support one blended live model yet.

## Innovation Universe
- Rows: 1104
- Strike rate: 0.2536
- Frame rate: 0.558
- ROI/pt: -0.0729
- P&L: -80.43

## Sigma Gate
- Rows: 1104
- Baseline AUC: 0.5806
- Gate AUC: 0.7494
- Staging model: C:\Users\puror\velo-oracle-prime\models\radical_sigma_gate_staging\sigma_win_gate.pkl

| Ranker | Top % | n | SR | Frame | ROI/pt | P&L | Avg SP |
|---|---:|---:|---:|---:|---:|---:|---:|
| baseline_vp | 10 | 27 | 0.4074 | 0.7778 | -0.0989 | -2.67 | 2.686 |
| baseline_vp | 20 | 55 | 0.3636 | 0.8182 | -0.1529 | -8.41 | 2.981 |
| baseline_vp | 30 | 82 | 0.3171 | 0.7561 | -0.2404 | -19.71 | 3.58 |
| baseline_vp | 50 | 138 | 0.2609 | 0.6812 | -0.2864 | -39.53 | 4.674 |
| sigma_gate | 10 | 27 | 0.6667 | 1.0 | -0.0433 | -1.17 | 1.464 |
| sigma_gate | 20 | 55 | 0.5636 | 0.9636 | -0.0555 | -3.05 | 1.725 |
| sigma_gate | 30 | 82 | 0.4512 | 0.8902 | -0.1773 | -14.54 | 2.051 |
| sigma_gate | 50 | 138 | 0.3623 | 0.7681 | -0.1796 | -24.79 | 2.743 |

## Frame Gate
- Rows: 1104
- Baseline AUC: 0.6641
- Gate AUC: 0.7878
- Staging model: C:\Users\puror\velo-oracle-prime\models\radical_sigma_gate_staging\sigma_frame_gate.pkl

| Ranker | Top % | n | SR | Frame | ROI/pt | P&L | Avg SP |
|---|---:|---:|---:|---:|---:|---:|---:|
| baseline_vp | 10 | 27 | 0.4074 | 0.7778 | -0.0989 | -2.67 | 2.686 |
| baseline_vp | 20 | 55 | 0.3636 | 0.8182 | -0.1529 | -8.41 | 2.981 |
| baseline_vp | 30 | 82 | 0.3171 | 0.7561 | -0.2404 | -19.71 | 3.58 |
| baseline_vp | 50 | 138 | 0.2609 | 0.6812 | -0.2864 | -39.53 | 4.674 |
| sigma_gate | 10 | 27 | 0.6667 | 1.0 | -0.0219 | -0.59 | 1.503 |
| sigma_gate | 20 | 55 | 0.5818 | 0.9636 | 0.0336 | 1.85 | 1.788 |
| sigma_gate | 30 | 82 | 0.4878 | 0.9146 | -0.0509 | -4.17 | 2.086 |
| sigma_gate | 50 | 138 | 0.3551 | 0.7609 | -0.2032 | -28.04 | 2.789 |

## Best Regimes
### odds_band
- EIGHT_TO_FOURTEEN: n=134 SR=0.097 frame=0.3582 ROI=0.0709 avg_sp=10.869
- ODDS_ON_LT_1_5: n=44 SR=0.7727 frame=0.9773 ROI=0.0291 avg_sp=1.338
- TWO_TO_THREE: n=235 SR=0.3319 frame=0.7149 ROI=0.0208 avg_sp=3.142
- EVS_TO_6_4: n=182 SR=0.511 frame=0.8571 ROI=-0.0224 avg_sp=1.964
- FIVE_TO_EIGHT: n=161 SR=0.1304 frame=0.4099 ROI=-0.0776 avg_sp=7.017
- THREE_TO_FIVE: n=215 SR=0.1721 frame=0.5256 ROI=-0.2071 avg_sp=4.666
### vp_band
- VP_15_25: n=366 SR=0.1967 frame=0.4699 ROI=-0.0072 avg_sp=9.674
- VP_LT_15: n=117 SR=0.2051 frame=0.4274 ROI=-0.0499 avg_sp=10.647
- VP_55_PLUS: n=74 SR=0.4324 frame=0.7973 ROI=-0.0543 avg_sp=3.526
- VP_25_35: n=283 SR=0.2403 frame=0.5406 ROI=-0.0799 avg_sp=7.078
- VP_35_45: n=170 SR=0.2882 frame=0.6765 ROI=-0.1426 avg_sp=4.523
- VP_45_55: n=94 SR=0.3723 frame=0.7128 ROI=-0.2241 avg_sp=3.581
### field_band
- FS_6_8: n=338 SR=0.3107 frame=0.6923 ROI=0.1373 avg_sp=5.328
- FS_2_5: n=95 SR=0.4316 frame=0.8316 ROI=0.002 avg_sp=3.862
- FS_13_PLUS: n=250 SR=0.192 frame=0.412 ROI=-0.0399 avg_sp=10.027
- FS_9_12: n=421 SR=0.2043 frame=0.4751 ROI=-0.278 avg_sp=8.269
### class_band
- CLASS_3: n=44 SR=0.25 frame=0.6364 ROI=0.9291 avg_sp=7.246
- CLASS_4: n=788 SR=0.2881 frame=0.5939 ROI=-0.0455 avg_sp=6.275
- CLASS_6: n=75 SR=0.12 frame=0.4133 ROI=-0.1816 avg_sp=10.001
- CLASS_2: n=43 SR=0.186 frame=0.4884 ROI=-0.1937 avg_sp=10.13
- CLASS_5: n=132 SR=0.1667 frame=0.447 ROI=-0.4106 avg_sp=11.948
- CLASS_1: n=22 SR=0.1364 frame=0.4091 ROI=-0.4214 avg_sp=5.906
### router_combo
- v1=1|v2=1|v6=0: n=80 SR=0.4125 frame=0.8 ROI=0.0304 avg_sp=2.621
- v1=0|v2=0|v6=0: n=962 SR=0.2401 frame=0.5322 ROI=-0.0788 avg_sp=8.039
- v1=1|v2=1|v6=1: n=52 SR=0.25 frame=0.5962 ROI=-0.0962 avg_sp=3.55
- v1=1|v2=0|v6=0: n=10 SR=0.3 frame=0.9 ROI=-0.202 avg_sp=2.81
### course
- Bellewstown: n=13 SR=0.3077 frame=0.3846 ROI=1.3138 avg_sp=9.583
- Leicester: n=20 SR=0.35 frame=0.6 ROI=1.157 avg_sp=8.054
- Newbury: n=26 SR=0.2308 frame=0.4615 ROI=1.0254 avg_sp=10.16
- Market Rasen: n=13 SR=0.3077 frame=0.8462 ROI=0.4185 avg_sp=6.879
- Chester: n=14 SR=0.4286 frame=0.6429 ROI=0.3929 avg_sp=4.804
- Ayr: n=20 SR=0.15 frame=0.5 ROI=0.2975 avg_sp=6.739
### odds_x_field
- LONGSHOT_15_PLUS|FS_6_8: n=20 SR=0.05 frame=0.25 ROI=1.05 avg_sp=20.9
- EIGHT_TO_FOURTEEN|FS_6_8: n=31 SR=0.1613 frame=0.4839 ROI=0.8065 avg_sp=11.113
- TWO_TO_THREE|FS_13_PLUS: n=28 SR=0.4286 frame=0.6786 ROI=0.3571 avg_sp=3.192
- FIVE_TO_EIGHT|FS_6_8: n=45 SR=0.1778 frame=0.6222 ROI=0.2444 avg_sp=6.884
- EVS_TO_6_4|FS_9_12: n=47 SR=0.5957 frame=0.8723 ROI=0.186 avg_sp=1.995
- EVS_TO_6_4|FS_2_5: n=33 SR=0.5758 frame=1.0 ROI=0.0958 avg_sp=1.882
### odds_x_vp
- EIGHT_TO_FOURTEEN|VP_25_35: n=30 SR=0.1333 frame=0.4333 ROI=0.4667 avg_sp=10.667
- EVS_TO_6_4|VP_15_25: n=29 SR=0.6207 frame=0.8276 ROI=0.2269 avg_sp=2.046
- TWO_TO_THREE|VP_15_25: n=57 SR=0.386 frame=0.6842 ROI=0.2237 avg_sp=3.205
- EVS_TO_6_4|VP_55_PLUS: n=23 SR=0.6522 frame=1.0 ROI=0.207 avg_sp=1.847
- LONGSHOT_15_PLUS|VP_15_25: n=70 SR=0.0429 frame=0.1714 ROI=0.1286 avg_sp=24.914
- THREE_TO_FIVE|VP_25_35: n=62 SR=0.2258 frame=0.5323 ROI=0.0777 avg_sp=4.669
### class_x_field
- CLASS_5|FS_13_PLUS: n=20 SR=0.25 frame=0.4 ROI=0.7665 avg_sp=20.216
- CLASS_4|FS_6_8: n=242 SR=0.3512 frame=0.719 ROI=0.1238 avg_sp=4.71
- CLASS_4|FS_2_5: n=72 SR=0.4583 frame=0.875 ROI=0.0994 avg_sp=3.286
- CLASS_4|FS_13_PLUS: n=188 SR=0.2074 frame=0.4362 ROI=-0.1346 avg_sp=8.619
- CLASS_4|FS_9_12: n=286 SR=0.2448 frame=0.521 ROI=-0.1668 avg_sp=6.81
- CLASS_6|FS_9_12: n=46 SR=0.1304 frame=0.3478 ROI=-0.2037 avg_sp=10.926

## Toxic Regimes
### odds_band
- LONGSHOT_15_PLUS: n=133 SR=0.0301 frame=0.1654 ROI=-0.2632 avg_sp=25.654
- THREE_TO_FIVE: n=215 SR=0.1721 frame=0.5256 ROI=-0.2071 avg_sp=4.666
- FIVE_TO_EIGHT: n=161 SR=0.1304 frame=0.4099 ROI=-0.0776 avg_sp=7.017
- EVS_TO_6_4: n=182 SR=0.511 frame=0.8571 ROI=-0.0224 avg_sp=1.964
### vp_band
- VP_45_55: n=94 SR=0.3723 frame=0.7128 ROI=-0.2241 avg_sp=3.581
- VP_35_45: n=170 SR=0.2882 frame=0.6765 ROI=-0.1426 avg_sp=4.523
- VP_25_35: n=283 SR=0.2403 frame=0.5406 ROI=-0.0799 avg_sp=7.078
- VP_55_PLUS: n=74 SR=0.4324 frame=0.7973 ROI=-0.0543 avg_sp=3.526
### field_band
- FS_9_12: n=421 SR=0.2043 frame=0.4751 ROI=-0.278 avg_sp=8.269
- FS_13_PLUS: n=250 SR=0.192 frame=0.412 ROI=-0.0399 avg_sp=10.027
- FS_2_5: n=95 SR=0.4316 frame=0.8316 ROI=0.002 avg_sp=3.862
- FS_6_8: n=338 SR=0.3107 frame=0.6923 ROI=0.1373 avg_sp=5.328
### class_band
- CLASS_1: n=22 SR=0.1364 frame=0.4091 ROI=-0.4214 avg_sp=5.906
- CLASS_5: n=132 SR=0.1667 frame=0.447 ROI=-0.4106 avg_sp=11.948
- CLASS_2: n=43 SR=0.186 frame=0.4884 ROI=-0.1937 avg_sp=10.13
- CLASS_6: n=75 SR=0.12 frame=0.4133 ROI=-0.1816 avg_sp=10.001
### router_combo
- v1=1|v2=0|v6=0: n=10 SR=0.3 frame=0.9 ROI=-0.202 avg_sp=2.81
- v1=1|v2=1|v6=1: n=52 SR=0.25 frame=0.5962 ROI=-0.0962 avg_sp=3.55
- v1=0|v2=0|v6=0: n=962 SR=0.2401 frame=0.5322 ROI=-0.0788 avg_sp=8.039
- v1=1|v2=1|v6=0: n=80 SR=0.4125 frame=0.8 ROI=0.0304 avg_sp=2.621
### course
- Warwick: n=12 SR=0.0 frame=0.75 ROI=-1.0 avg_sp=17.699
- Bangor-on-Dee: n=14 SR=0.0 frame=0.5 ROI=-1.0 avg_sp=7.669
- Thirsk: n=14 SR=0.0 frame=0.1429 ROI=-1.0 avg_sp=7.704
- Perth: n=29 SR=0.069 frame=0.4138 ROI=-0.8955 avg_sp=10.169
### odds_x_field
- LONGSHOT_15_PLUS|FS_9_12: n=64 SR=0.0156 frame=0.125 ROI=-0.7656 avg_sp=25.547
- THREE_TO_FIVE|FS_9_12: n=93 SR=0.1398 frame=0.4946 ROI=-0.3711 avg_sp=4.625
- EIGHT_TO_FOURTEEN|FS_9_12: n=53 SR=0.0566 frame=0.3019 ROI=-0.3396 avg_sp=10.906
- FIVE_TO_EIGHT|FS_13_PLUS: n=50 SR=0.1 frame=0.28 ROI=-0.27 avg_sp=7.178
### odds_x_vp
- LONGSHOT_15_PLUS|VP_25_35: n=31 SR=0.0 frame=0.129 ROI=-1.0 avg_sp=25.258
- THREE_TO_FIVE|VP_35_45: n=29 SR=0.1379 frame=0.4828 ROI=-0.4369 avg_sp=4.473
- FIVE_TO_EIGHT|VP_LT_15: n=21 SR=0.0952 frame=0.3333 ROI=-0.3571 avg_sp=7.024
- THREE_TO_FIVE|VP_15_25: n=75 SR=0.1467 frame=0.5867 ROI=-0.3201 avg_sp=4.727
### class_x_field
- CLASS_5|FS_9_12: n=63 SR=0.1111 frame=0.381 ROI=-0.7456 avg_sp=12.481
- CLASS_5|FS_6_8: n=41 SR=0.1463 frame=0.561 ROI=-0.5207 avg_sp=7.302
- CLASS_6|FS_9_12: n=46 SR=0.1304 frame=0.3478 ROI=-0.2037 avg_sp=10.926
- CLASS_4|FS_9_12: n=286 SR=0.2448 frame=0.521 ROI=-0.1668 avg_sp=6.81

## Sidecars
- D: V1 + JTC-D + Intl Lagged [LEAK_RISK]: AUC=0.8422 SR=0.4438 lift=0.1453 leakage=True verdict=SHADOW_ONLY
- B: V1 + JTC-D [LEAKAGE_RISK]: AUC=0.8418 SR=0.4433 lift=0.1449 leakage=True verdict=SHADOW_ONLY
- G: V1 + Market [MARKET_LANE]: AUC=0.8069 SR=0.3603 lift=0.11 leakage=False verdict=MARKET_LANE
- H: V1 + Intl + Market [MARKET_LANE]: AUC=0.8069 SR=0.3614 lift=0.11 leakage=False verdict=MARKET_LANE
- C: V1 + Intl Lagged: AUC=0.6967 SR=0.2545 lift=-0.0002 leakage=False verdict=REJECTED_NO_LIFT
- A: Challenger V1 (baseline): AUC=0.6969 SR=0.2502 lift=0.0 leakage=False verdict=REJECTED_NO_LIFT

## Radical Doctrine
- Live Velo should become a gated decision system, not a universal top-pick bettor.
- Morning model: clean RP race-shape + Velo doctrine + passport memory only.
- Late model: market lane is separate and time-boxed; never contaminates morning truth.
- Sigma gate decides bet/pass after the scorer speaks; it does not replace the scorer.
- JTC-D is high-value but quarantined until rebuilt as lagged/date-bounded.
- Longshots split: 8-14 can be an edge-discovery zone; 15+ is not execution-ready.
- High Sigma frame confidence is a cash-run/acca clue, not proof of win-bet value.
