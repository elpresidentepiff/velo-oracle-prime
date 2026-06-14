# Race Day Two-Lane Readiness: 2026-06-07
Generated: 2026-06-07T05:00:39.891691Z

**Overall Status:** `READY`
**Operational Lane:** `LANE_A_CORE_PASSPORT`

## Quality Gates
| Gate | Pass |
|---|---|
| rpr_clean | ✓ |
| sp_clean | ✓ |
| passport_coverage_above_50pct | ✓ |
| no_leakage_violations | ✓ |

## Intent Coverage
- Coverage: **0.0%** (gate: 80.0%) — `UNAVAILABLE_BELOW_GATE`
- Intent features are historical (race_id, horse) pairs. Current-card rows never match → 0% is expected for morning reads.

## Lane Selection
- **LANE_A_CORE_PASSPORT** — Intent coverage 0.0% < 80.0% gate. Lane B is PAPER_ONLY_NO_INTENT. Lane A (Core+Passport) is operational read.

## Lane A: Core V0_OR + Passport (30 features) — Operational
- Model: `C:\Users\puror\velo-oracle-prime\data\new_build\models\core_v0_or_passport\core_v0_or_passport_model.pkl`

## Lane B: Challenger V1 Core+Passport+Intent (45 features)
- Status: `PAPER_ONLY_NO_INTENT`
- Intent coverage: 0.0%

## Race Day Scorecards — 2026-06-07
_30 races, 320 runners_

### 13:07 Navan — Lynn Lodge Stud Irish EBF Maiden **[NO_EDGE]**
- Runners: 10 | Passport: 1/10 ⚠ WEAK_DATA
- **Lane A (operational):** Cleodolinda (0.153), Desert Alchemist (0.104), Rejoinder (0.104)
- **Lane B (paper):** Cleodolinda (0.117), Desert Alchemist (0.094), Rejoinder (0.094) ⚠ PAPER_ONLY_NO_INTENT

### 13:22 Punchestown — Bermingham Cameras Novice Chase **[LOW_DATA]**
- Runners: 5 | Passport: 1/5 ⚠ WEAK_DATA
- **Lane A (operational):** Uno Me I Like My T (0.164), Ma Jacks Hill (0.161), Jolie Jewel (0.143)
- **Lane B (paper):** Uno Me I Like My T (0.157), Ma Jacks Hill (0.155), Supersundae (0.135) ⚠ PAPER_ONLY_NO_INTENT

### 13:42 Navan — Navan Racing Festival Early Bird Tickets On Sale N **[NO_EDGE]**
- Runners: 7 | Passport: 2/7 ⚠ WEAK_DATA
- **Lane A (operational):** Cuban Grey (0.133), Namiid (0.122), Bodhi Bear (0.106)
- **Lane B (paper):** Cuban Grey (0.116), Namiid (0.120), Bodhi Bear (0.106) ⚠ PAPER_ONLY_NO_INTENT

### 13:50 Goodwood — Rod Gaskin Garden Machinery Handicap **[NO_EDGE]**
- Runners: 9 | Passport: 9/9
- **Lane A (operational):** Sturlasson (0.125), Sudden Flight (0.114), Fleetwater (0.092)
- **Lane B (paper):** Sturlasson (0.120), Sudden Flight (0.108), Brosay (0.099) ⚠ PAPER_ONLY_NO_INTENT

### 13:57 Punchestown — Jim Ryan Memorial Novice Chase **[LOW_DATA]**
- Runners: 3 | Passport: 2/3 ⚠ WEAK_DATA
- **Lane A (operational):** Emily Love (0.262), Raglan Road (0.213), Yoradreamer (0.201)
- **Lane B (paper):** Emily Love (0.244), Raglan Road (0.228), Yoradreamer (0.163) ⚠ PAPER_ONLY_NO_INTENT

### 14:07 Perth — Scone Palace Jousting Tournament Novices' Hurdle ( **[NO_EDGE]**
- Runners: 7 | Passport: 7/7
- **Lane A (operational):** Trigg (0.233), Flying Ace (0.199), Saint Cunning (0.174)
- **Lane B (paper):** Trigg (0.162), Flying Ace (0.180), Saint Cunning (0.167) ⚠ PAPER_ONLY_NO_INTENT

### 14:17 Navan — Book Your Hospitality Now For Navan Racing Festiva **[SUPPRESS]**
- Runners: 23 | Passport: 13/23 ⚠ WEAK_DATA
- **Lane A (operational):** Happy Henry (0.059), Mint Man (0.056), Jazzit (0.050)
- **Lane B (paper):** Happy Henry (0.049), Jazzit (0.048), An Laochmor (0.046) ⚠ PAPER_ONLY_NO_INTENT

### 14:25 Goodwood — British Stallion Studs EBF Novice Stakes (GBB/IRE  **[NO_EDGE]**
- Runners: 6 | Passport: 6/6
- **Lane A (operational):** My A'Ali Baba (0.192), Mobadir (0.170), Asgar (0.150)
- **Lane B (paper):** My A'Ali Baba (0.147), Mobadir (0.151), Asgar (0.144) ⚠ PAPER_ONLY_NO_INTENT

### 14:32 Punchestown — K-Mech Mechanical Handicap Chase **[LOW_DATA]**
- Runners: 13 | Passport: 1/13 ⚠ WEAK_DATA
- **Lane A (operational):** Jalila Moriviere (0.074), Me Wee Bonnie Lass (0.063), Karoline Banbou (0.063)
- **Lane B (paper):** Jalila Moriviere (0.069), Karoline Banbou (0.065), He's Gorgeous (0.061) ⚠ PAPER_ONLY_NO_INTENT

### 14:42 Perth — Sun Racing The Home Of Racing Novices' Limited Han **[SUPPRESS]**
- Runners: 13 | Passport: 13/13
- **Lane A (operational):** Morandi Second (0.093), Blondina (0.086), Magic Gloves (0.080)
- **Lane B (paper):** Magic Gloves (0.081), Breadalbane Lass (0.070), Struth (0.074) ⚠ PAPER_ONLY_NO_INTENT

### 14:52 Navan — Navan Handicap **[SUPPRESS]**
- Runners: 10 | Passport: 7/10 ⚠ WEAK_DATA
- **Lane A (operational):** Jon Riggens (0.161), Clonmacash (0.113), Ocean's Breath (0.111)
- **Lane B (paper):** Clonmacash (0.109), Ocean's Breath (0.105), Collective Power (0.091) ⚠ PAPER_ONLY_NO_INTENT

### 15:00 Goodwood — Goodwood Horseracing Club Membership Selling Stake **[FRAME_TRUST]**
- Runners: 5 | Passport: 5/5
- **Lane A (operational):** Leucothea (0.317), Undercover Affair (0.181), Cavan Lady (0.155)
- **Lane B (paper):** Leucothea (0.215), Undercover Affair (0.157), Cavan Lady (0.163) ⚠ PAPER_ONLY_NO_INTENT

### 15:07 Punchestown — Congratulations Nicole Lockhead Anderson INHSC Lad **[LOW_DATA]**
- Runners: 17 | Passport: 4/17 ⚠ WEAK_DATA
- **Lane A (operational):** Icare Desbois (0.071), Cut The Rope (0.060), Fairlander (0.059)
- **Lane B (paper):** Icare Desbois (0.064), Cut The Rope (0.059), Fairlander (0.053) ⚠ PAPER_ONLY_NO_INTENT

### 15:17 Perth — Scone Palace International Horse Trials Handicap H **[SUPPRESS]**
- Runners: 13 | Passport: 13/13
- **Lane A (operational):** Scots Poet (0.100), Cosmic Soul (0.095), Ailt An Chorrain (0.092)
- **Lane B (paper):** Ailt An Chorrain (0.087), Scriabin (0.072), Just Dottie (0.067) ⚠ PAPER_ONLY_NO_INTENT

### 15:27 Navan — Irish Stallion Farms EBF Hill Of Tara Stakes (List **[SUPPRESS]**
- Runners: 12 | Passport: 9/12 ⚠ WEAK_DATA
- **Lane A (operational):** Isaac Newton (0.103), Flushing Meadows (0.101), Wemightakedlongway (0.101)
- **Lane B (paper):** Isaac Newton (0.092), Flushing Meadows (0.088), Wemightakedlongway (0.098) ⚠ PAPER_ONLY_NO_INTENT

### 15:35 Goodwood — Weatherbys/British EBF Agnes Keyser Fillies' Stake **[NO_EDGE]**
- Runners: 10 | Passport: 10/10
- **Lane A (operational):** Lady Dora Mae (0.181), Venetia (0.147), Sacred Ground (0.133)
- **Lane B (paper):** Lady Dora Mae (0.114), Venetia (0.104), Ourbren (0.106) ⚠ PAPER_ONLY_NO_INTENT

### 15:42 Punchestown — Lily & Wild Mares Maiden Hurdle **[LOW_DATA]**
- Runners: 19 | Passport: 1/19 ⚠ WEAK_DATA
- **Lane A (operational):** Working Away (0.081), Bold Reflection (0.081), Julie Liath (0.079)
- **Lane B (paper):** Latopix (0.060), Hello Below (0.060), Likeyouhaveplenty (0.060) ⚠ PAPER_ONLY_NO_INTENT

### 15:52 Perth — Perth Silver Cup Handicap Chase (GBB Race) **[NO_EDGE]**
- Runners: 6 | Passport: 6/6
- **Lane A (operational):** Captain Cool (0.184), Hypotenus (0.125), Classic Maestro (0.121)
- **Lane B (paper):** Captain Cool (0.140), Hypotenus (0.110), Classic Maestro (0.105) ⚠ PAPER_ONLY_NO_INTENT

### 16:02 Navan — Darley Irish EBF Kooyonga Stakes (Listed Race) (Fi **[NO_EDGE]**
- Runners: 11 | Passport: 9/11 ⚠ WEAK_DATA
- **Lane A (operational):** Drop Dead Gorgeous (0.153), Syzygy (0.130), Fingerpaint (0.117)
- **Lane B (paper):** Drop Dead Gorgeous (0.154), Syzygy (0.109), Fingerpaint (0.118) ⚠ PAPER_ONLY_NO_INTENT

### 16:10 Goodwood — Billy Vigar Handicap (GBBPlus Race) **[NO_EDGE]**
- Runners: 9 | Passport: 9/9
- **Lane A (operational):** Arc Zoosve (0.169), Across Earth (0.168), Maxident (0.131)
- **Lane B (paper):** Arc Zoosve (0.122), Across Earth (0.142), Maxident (0.105) ⚠ PAPER_ONLY_NO_INTENT

### 16:17 Punchestown — John Dowling Memorial Maiden Hurdle **[NO_EDGE]**
- Runners: 12 | Passport: 2/12 ⚠ WEAK_DATA
- **Lane A (operational):** Captain Hanley (0.151), C Pas Possible (0.140), Les Issards (0.140)
- **Lane B (paper):** C Pas Possible (0.121), Les Issards (0.121), Glenary Prince (0.121) ⚠ PAPER_ONLY_NO_INTENT

### 16:27 Perth — Perth Gold Cup Handicap Chase (GBB Race) **[SUPPRESS]**
- Runners: 10 | Passport: 10/10
- **Lane A (operational):** Somespring Special (0.090), Walk On Quest (0.089), Breizh River (0.082)
- **Lane B (paper):** Walk On Quest (0.079), Breizh River (0.069), The Real Whacker (0.092) ⚠ PAPER_ONLY_NO_INTENT

### 16:37 Navan — Cusack Hotel Group Family Raceday July 11th Handic **[SUPPRESS]**
- Runners: 16 | Passport: 8/16 ⚠ WEAK_DATA
- **Lane A (operational):** Sarmiento Power (0.086), Maxwell Smart (0.074), Idomything (0.069)
- **Lane B (paper):** Sarmiento Power (0.078), Maxwell Smart (0.065), Idomything (0.063) ⚠ PAPER_ONLY_NO_INTENT

### 16:45 Goodwood — Tapster Stakes (Listed Race) **[NO_EDGE]**
- Runners: 6 | Passport: 6/6
- **Lane A (operational):** Glen Buck (0.159), Arabian Crown (0.159), Tenability (0.154)
- **Lane B (paper):** Glen Buck (0.131), Arabian Crown (0.143), Tenability (0.143) ⚠ PAPER_ONLY_NO_INTENT

### 16:52 Punchestown — TRM Supporting Every Stride Of The Journey Handica **[SUPPRESS]**
- Runners: 13 | Passport: 2/13 ⚠ WEAK_DATA
- **Lane A (operational):** Maverick Mack (0.086), William Tell (0.062), Ottoman Style (0.060)
- **Lane B (paper):** Maverick Mack (0.088), William Tell (0.062), Beyond Your Dreams (0.063) ⚠ PAPER_ONLY_NO_INTENT

### 17:02 Perth — Malcolm Group Handicap Chase (GBB Race) **[FRAME_TRUST]**
- Runners: 7 | Passport: 7/7
- **Lane A (operational):** Ira Hayes (0.164), Sir Carnegie (0.132), Neon Diamond (0.123)
- **Lane B (paper):** Ira Hayes (0.182), Sir Carnegie (0.106), Neon Diamond (0.139) ⚠ PAPER_ONLY_NO_INTENT

### 17:12 Navan — Cusack Hotel Group Family Raceday July 11th Handic **[SUPPRESS]**
- Runners: 15 | Passport: 9/15 ⚠ WEAK_DATA
- **Lane A (operational):** Jurality (0.091), Cahir Bay (0.075), Mystic Rose (0.073)
- **Lane B (paper):** Jurality (0.073), Cahir Bay (0.069), Just Another Eagle (0.066) ⚠ PAPER_ONLY_NO_INTENT

### 17:20 Goodwood — Elston Support Your Local Air Ambulance Handicap **[NO_EDGE]**
- Runners: 9 | Passport: 9/9
- **Lane A (operational):** Blue Prince (0.150), Dannick (0.138), Serenity Dream (0.127)
- **Lane B (paper):** Dannick (0.105), Serenity Dream (0.117), Cherry Cobbler (0.111) ⚠ PAPER_ONLY_NO_INTENT

### 17:27 Punchestown — Irish Stallion Farms EBF Mares (Pro/Am) INH Flat R **[LOW_DATA]**
- Runners: 10 | Passport: 1/10 ⚠ WEAK_DATA
- **Lane A (operational):** Coco's Legacy (0.156), Al Arrivee (0.149), Brave Lady (0.122)
- **Lane B (paper):** Coco's Legacy (0.141), Al Arrivee (0.129), Freya Cova (0.102) ⚠ PAPER_ONLY_NO_INTENT

### 17:37 Perth — IM Group Handicap Hurdle **[SUPPRESS]**
- Runners: 14 | Passport: 14/14
- **Lane A (operational):** Maillot Blanc (0.128), Leader Wing (0.108), Burgundy Man (0.098)
- **Lane B (paper):** Maillot Blanc (0.089), Leader Wing (0.068), Myfavouritesister (0.073) ⚠ PAPER_ONLY_NO_INTENT

## Boundaries
- Paper-only intelligence. No betting instruction.
- No Telegram, staking, live scoring table writes, or official-pick override.
- Old Live VÉLØ and Shadow VÉLØ untouched.
- RPR archive-only. No SP in morning model. No JTC-D all-time sidecar.