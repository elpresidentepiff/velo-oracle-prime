# 2026-06-23 Deep Dive

## Lane Metrics
- Old VELO: 3/17 wins (17.6%), frames 13/17 (76.5%), ?10 win P&L ?-116.90 (return ?53.10, stake ?170)
- New Build A: 2/17 wins (11.8%), frames 8/17 (47.1%), ?10 win P&L ?-5.00 (return ?165.00, stake ?170)
- New Build B paper: 2/18 wins (11.1%), frames 8/18 (44.4%), ?10 win P&L ?-15.00 (return ?165.00, stake ?180)

## Official Old VELO Sigma
- Evaluated: 17 | Wins: 3 (17.6%) | Frame rate: 76.5% | NR: 2 | No-result: 1
- Miss classes: {'mid_priced_won': 3, 'outsider_won': 1}

## Race-by-race model results
| Time | Course | Winner (SP) | Old VELO pick | Pos | VP | MDS | Place | Tier/Product | No-RPR prob | New Build A | Pos | New Build B | Pos | NB tag |
|---|---|---:|---|---:|---:|---:|---:|---|---:|---|---:|---|---:|---|
| 2.15 | Beverley | Lady Caroline Lamb (1.83) | Fern Clyde | 3 | 0.540 | 0.326 | 0.956 | A/WIN_ONLY | 0.179 | Fern Clyde | 3 | Fern Clyde | 3 | NO_EDGE |
| 2.45 | Beverley | Tattie Bogle (8.5) | Sunny Orange | 4 | 0.400 | 0.039 | 0.701 | A/EW_CANDIDATE | 0.080 | Roaring Ralph | 3 | Roaring Ralph | 3 | NO_EDGE |
| 3.15 | Beverley | Tamzan (3.5) | Regal Desire | 2 | 0.594 | 0.232 | 0.816 | A/VISION_ONLY | 0.127 | Pepsea | 4 | Pepsea | 4 | NO_EDGE |
| 3.45 | Beverley | Satyress (5.5) | Arch Legend | 3 | 0.791 | 0.058 | 0.847 | A/EW_CANDIDATE | 0.103 | Arch Legend | 3 | Arch Legend | 3 | NO_EDGE |
| 4.17 | Beverley | Percy's Daydream (7.5) | Titian | 4 | 0.730 | 0.147 | 0.980 | A/EW_CANDIDATE | 0.118 | Percy's Daydream | 1 | Percy's Daydream | 1 | FRAME_TRUST |
| 4.52 | Beverley | Sahm Naif (3.25) | Wadacre Geisha | 2 | 0.524 | 0.063 | 0.544 | A/VISION_ONLY | 0.120 | Resdev Time | 3 | Resdev Time | 3 | NO_EDGE |
| 5.27 | Beverley | Tanaka (19.0) | Jack Rabbit Slims | 2 | 0.323 | 0.050 | 0.488 | B/EW_CANDIDATE | 0.153 | Dabbling | 4 | Dabbling | 4 | NO_EDGE |
| 2.30 | Ffos Las | NO RESULT (None) | Punchbowl Flyer | NO_RESULT | 0.340 | 0.043 | 0.430 | B/EW_CANDIDATE | 0.072 | Proof | NO_RESULT | Proof | NO_RESULT | NO_EDGE |
| 3.00 | Ffos Las | Isle Of Lismore (2.2) | Isle Of Lismore | 1 | 0.323 | 0.054 | 0.666 | B/VISION_ONLY | 0.112 | Candy Warhol | 4 | Candy Warhol | 4 | NO_EDGE |
| 3.30 | Ffos Las | English Time (1.67) | English Time | 1 | 0.459 | 0.357 | 0.963 | A/WIN_ONLY | 0.109 | Malakai Kite | 5 | Malakai Kite | 5 | LOW_DATA |
| 4.00 | Ffos Las | Betty Lemon (12.0) | Uncle Albert | 8 | 0.595 | 0.133 | 0.687 | A/EW_CANDIDATE | 0.070 | Mooretown Lad | 7 | Mooretown Lad | 7 | SUPPRESS |
| 4.35 | Ffos Las | Pureis King (2.0) | Knightmare | 2 | 0.278 | 0.069 | 0.302 | X/PASS | 0.102 | Whiskey Sunrise | 5 | Belle Of Kt | 7 | SUPPRESS |
| 5.10 | Ffos Las | Solanna (3.75) | Havana Tobouggaloo | 5 | 0.577 | 0.088 | 0.679 | A/EW_CANDIDATE | 0.091 | Abando | 7 | Abando | 7 | NO_EDGE |
| 5.17 | Newbury | Arabica Queen (9.0) | Big Hitter | 2 | 0.314 | 0.128 | 0.692 | B/PASS | 0.099 | Arabica Queen | 1 | Arabica Queen | 1 | SUPPRESS |
| 5.50 | Newbury | Yahaira (23.0) | Global Success | 3 | 0.322 | 0.078 | 0.596 | C/PASS | 0.102 | Sovereign Beach | 10 | Sovereign Beach | 10 | LOW_DATA |
| 6.25 | Newbury | Bayside View (1.44) | Bayside View | 1 | 0.666 | 0.737 | 0.999 | A/WIN_ONLY | 0.179 | Roosike | 3 | Anad | 2 | LOW_DATA |
| 7.00 | Newbury | Bami (34.0) | White Ladder | NR | 0.405 | 0.013 | 0.291 | B/PASS | 0.041 | Creative Queen | 7 | Creative Queen | 7 | SUPPRESS |
| 7.35 | Newbury | Rage Of Thunder (4.0) | Roman Spring | 3 | 0.466 | 0.059 | 0.405 | B/EW_CANDIDATE | 0.042 | Albert Cee | NR | Forever My Prince | 6 | SUPPRESS |
| 8.05 | Newbury | Baileys Khelstar (1.5) | Kitty Foyle | NR | 0.470 | 0.106 | 0.927 | A/VISION_ONLY | 0.137 | Taritino | NR | Taritino | NR | WIN_TRUST |
| 8.35 | Newbury | Redbud Sixteen (3.5) | Raintown | 2 | 0.258 | 0.015 | 0.344 | C/PASS | 0.063 | Shady Bay | 3 | Shady Bay | 3 | SUPPRESS |

## Old VELO damage buckets
- Course Beverley: 0/7 wins (0.0%), frames 5/7 (71.4%)
- Course Ffos Las: 2/5 wins (40.0%), frames 3/5 (60.0%)
- Course Newbury: 1/5 wins (20.0%), frames 5/5 (100.0%)
- Product WIN_ONLY: 2/3 wins (66.7%), frames 3/3 (100.0%)
- Product EW_CANDIDATE: 0/7 wins (0.0%), frames 3/7 (42.9%)
- Product VISION_ONLY: 1/3 wins (33.3%), frames 3/3 (100.0%)
- Product PASS: 0/4 wins (0.0%), frames 4/4 (100.0%)

## Old misses outside frame
- 2.45 Beverley: picked Sunny Orange pos 4 (VP 0.400, MDS 0.039, place 0.701); winner Tattie Bogle SP 8.5; NewA Roaring Ralph pos 3
- 4.17 Beverley: picked Titian pos 4 (VP 0.730, MDS 0.147, place 0.980); winner Percy's Daydream SP 7.5; NewA Percy's Daydream pos 1
- 4.00 Ffos Las: picked Uncle Albert pos 8 (VP 0.595, MDS 0.133, place 0.687); winner Betty Lemon SP 12.0; NewA Mooretown Lad pos 7
- 5.10 Ffos Las: picked Havana Tobouggaloo pos 5 (VP 0.577, MDS 0.088, place 0.679); winner Solanna SP 3.75; NewA Abando pos 7