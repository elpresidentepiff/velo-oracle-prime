# Deep Race Agent Local Gold Inventory - 2026-06-21

This inventory records useful local files found in `C:\Users\puror\Downloads` for building the Deep Race Agent.

## Highest Value Machine Data

| File | Use For Agent | Notes |
|---|---|---|
| `raceform.csv` | Historical race archive, course/track profiling, race type, draw, going, SP, OR, RPR, TS, comments | Large file, about 663 MB. Columns include date, course, race_id, off, race_name, type, class, dist, going, ran, pos, draw, horse, jockey, trainer, sp, or, rpr, ts, sire, dam, owner, comment. |
| `ratings.csv` | Current BHA-style rating and rating-movement lookup | Columns include Flat rating, Diff Flat, AWT rating, Diff AWT, Chase rating, Diff Chase, Hurdle rating, Diff Hurdle. |
| `ratings (1).csv` | Smaller rating snapshot/check file | Same schema as `ratings.csv`; useful for parser tests. |
| `performance-figures.csv` | Recent performance trend vector | Columns include Latest, 2 runs ago, 3 runs ago, 4 runs ago, 5 runs ago, 6 runs ago. Values look like discipline-prefixed performance figures such as `T:107`, `A:33`, `H:x`. |
| `raceform.csv.xlsx` | Spreadsheet copy of raceform archive | Very large, likely less useful than CSV for code. |

## Race-Day PDF Evidence Packs

The downloaded course PDF sets decode as:

| Code | Meaning | Agent Use |
|---|---|---|
| `0010_XX` | Selection box | Competitor/selections consensus: Spotlight, RP Ratings, Topspeed, Postdata, newspapers. |
| `0011_XX` | Postdata grid | Postdata, Topspeed and factor grid: trainer form, going, distance, course, draw, ability, recent form. |
| `0012_XX` | Colour racecard | Race conditions, runners, weights, jockey/trainer, OR, TS, RPR. |
| `0015_OR` | Official ratings/history sheet | OR movement, recent runs, best winning ratings, highest entered, lowest win, RPR master. |
| `0016_XX` | Spotlight comments | Natural-language horse analysis, trainer/jockey, SP, OR, TS, RPR. |
| `0032_TS` | Topspeed ratings | Speed figures by conditions: distance, course, class, going bands, runner-count bands, base/master. |

Useful downloaded examples include Pontefract, Goodwood, Newbury, Brighton, Hexham, Catterick, Worcester, Leopardstown, York, Chester, Sandown, Gowran Park, Fairyhouse and others from May/June 2026.

No `BRI_20260621`, `HEX_20260621`, or `PON_20260621` PDF files were found in Downloads during this scan.

## BHA / Industry Reference Data

| File | Agent Use |
|---|---|
| `2025_Annual-Data-Pack-1.pdf` | Field-size, fixture, race-volume and industry context across 2021-2025. Good for baseline course/race competitiveness context. |
| `January26 bha.pdf`, `February26 bha.pdf`, `March26 bha.pdf`, `April26 bha.pdf`, `May26 bha.pdf`, `2026_Q1 bha.pdf` | Monthly/YTD BHA context: field size, odds-against favourite %, 8+ runner %, non-runners, close finish %, race volume. Useful as global regime background, not horse-level evidence. |
| `Race_Off_Times_2025_Full.pdf`, `Race_Off_Times_Full_2024.pdf`, `Off_Times_April_24_March_25.pdf` | Late-race/off-time reason analysis. Useful for operational context, not selection logic. |
| `Horse_Population_Report_*.pdf` | Population-level context. Lower priority for daily race decisions. |
| `2yo_Classification_2022.pdf`, `Anglo_Irish_Classifications_2021_22.pdf` | Historical class anchors and elite benchmarks. Reference-only unless building pedigree/class education. |

## Books / Papers

| File | Use |
|---|---|
| `The Horse-Racing Problem-A Bayesian Approach...pdf` | Concept reference for probabilistic horse-race modelling. |
| `[World Scientific Series in Finance] Exotic Betting...pdf` | Concept reference for exotic/pool betting and public-market inefficiency. |
| `Thinking, Fast and Slow...pdf` | Bias/mindset reference for agent caution and overconfidence checks. |

Do not bulk-copy book text into reports. Use these as reference inspiration for rules such as Bayesian updating, market inefficiency, and cognitive-bias warnings.

## Recommended Agent Integration

1. Build `local_racing_gold_inventory.json` from this inventory.
2. Build parsers for the six PDF sheet types using examples from Downloads.
3. Add a Deep Race Agent evidence layer:
   - Racecard facts from `0012`.
   - Competitor consensus from `0010`.
   - Postdata grid from `0011`.
   - OR/rating movement from `0015_OR` plus `ratings.csv`.
   - Spotlight text from `0016`.
   - Topspeed condition fit from `0032_TS`.
   - Historical race/course statistics from `raceform.csv`.
4. Keep BHA monthly packs as global context only.
5. Keep all agent output paper-only until Sigma replay proves lift.
