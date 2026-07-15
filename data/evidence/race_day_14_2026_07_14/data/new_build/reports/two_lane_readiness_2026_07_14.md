# Race Day Two-Lane Readiness: 2026-07-14
Generated: 2026-07-14T14:44:30.174250Z

**Overall Status:** `READY`
**Operational Lane:** `LANE_A_CORE_PASSPORT`

## Quality Gates
| Gate | Pass |
|---|---|
| rpr_clean | ✓ |
| sp_clean | ✓ |
| passport_coverage_above_50pct | ✗ |
| no_leakage_violations | ✓ |

## Intent Coverage
- Coverage: **0.0%** (gate: 80.0%) — `UNAVAILABLE_BELOW_GATE`
- Intent features are historical (race_id, horse) pairs. Current-card rows never match → 0% is expected for morning reads.

## Lane Selection
- **LANE_A_CORE_PASSPORT** — Intent coverage 0.0% < 80.0% gate. Lane B is PAPER_ONLY_NO_INTENT. Lane A (Core+Passport) is operational read.

## Lane A: Core V0_OR + Passport (30 features) — Operational
- Model: `/mnt/c/Users/puror/velo-oracle-prime/data/new_build/models/core_v0_or_passport/core_v0_or_passport_model.pkl`

## Lane B: Challenger V1 Core+Passport+Intent (45 features)
- Status: `PAPER_ONLY_NO_INTENT`
- Intent coverage: 0.0%

## Race Day Scorecards — 2026-07-14
_43 races, 368 runners_

### 13:54 Leicester — Best Ticket Deals Online leicester-racecourse.co.u **[NO_EDGE]**
- Runners: 10 | Passport: 6/10 ⚠ WEAK_DATA
- **Lane A (operational):** Le Grand Etoile (0.119), Bluestone Lady (0.112), Tiger In The Tree (0.100)
- **Lane B (paper):** Le Grand Etoile (0.118), Bluestone Lady (0.118), Agnes Hathaway (0.090) ⚠ PAPER_ONLY_NO_INTENT

### 14:07 Downpatrick — ITBA Mares Maiden Hurdle **[NO_EDGE]**
- Runners: 11 | Passport: 4/11 ⚠ WEAK_DATA
- **Lane A (operational):** Fastnet Crystal (0.191), Ritz Plan (0.110), Room For One More (0.104)
- **Lane B (paper):** Fastnet Crystal (0.151), Ritz Plan (0.106), Jet To Glory (0.098) ⚠ PAPER_ONLY_NO_INTENT

### 14:17 Beverley — EBF Fillies' Novice Stakes (GBB/IRE Incentive Race **[FRAME_TRUST]**
- Runners: 4 | Passport: 1/4 ⚠ WEAK_DATA
- **Lane A (operational):** Fast Track (0.257), Loveulongtime (0.209), Hair Raising (0.208)
- **Lane B (paper):** Fast Track (0.198), Loveulongtime (0.193), Kokumi (0.192) ⚠ PAPER_ONLY_NO_INTENT

### 14:24 Leicester — British EBF Novice Stakes (GBB/GBBPlus Race) **[NO_EDGE]**
- Runners: 6 | Passport: 1/6 ⚠ WEAK_DATA
- **Lane A (operational):** Cloud Forest (0.178), Knight Of Storms (0.149), Kudos Too (0.148)
- **Lane B (paper):** Cloud Forest (0.183), Knight Of Storms (0.138), Kudos Too (0.138) ⚠ PAPER_ONLY_NO_INTENT

### 14:30 Ffos Las — Dandara Homes EBF Maiden Stakes (GBB Race) **[LOW_DATA]**
- Runners: 5 | Passport: 1/5 ⚠ WEAK_DATA
- **Lane A (operational):** Louis The Fifth (0.171), Sole Ambition (0.168), El Paso (0.167)
- **Lane B (paper):** Louis The Fifth (0.160), Sole Ambition (0.160), El Paso (0.158) ⚠ PAPER_ONLY_NO_INTENT

### 14:37 Downpatrick — Randox (C & G) Maiden Hurdle **[LOW_DATA]**
- Runners: 9 | Passport: 0/9 ⚠ WEAK_DATA
- **Lane A (operational):** Jet Renegade (0.124), Fuusland (0.124), Fortis Et Liber (0.124)
- **Lane B (paper):** Jet Renegade (0.110), Fuusland (0.110), Fortis Et Liber (0.110) ⚠ PAPER_ONLY_NO_INTENT

### 14:47 Beverley — Young Guns Handicap **[NO_EDGE]**
- Runners: 8 | Passport: 3/8 ⚠ WEAK_DATA
- **Lane A (operational):** Dabbling (0.136), Our Hero Matty (0.119), What A Tahoo (0.117)
- **Lane B (paper):** Dabbling (0.136), Our Hero Matty (0.107), Roy Lane (0.106) ⚠ PAPER_ONLY_NO_INTENT

### 14:54 Leicester — Nelson Restaurant For Classic Raceday Dining Handi **[WIN_TRUST]**
- Runners: 6 | Passport: 5/6 ⚠ WEAK_DATA
- **Lane A (operational):** Betelgeuse (0.231), Ottoman (0.197), Trojan Truth (0.179)
- **Lane B (paper):** Betelgeuse (0.223), Ottoman (0.184), Spec Of Light (0.137) ⚠ PAPER_ONLY_NO_INTENT

### 15:00 Ffos Las — Golwg Gwendraeth Nursery Handicap **[SUPPRESS]**
- Runners: 5 | Passport: 3/5 ⚠ WEAK_DATA
- **Lane A (operational):** Our Fella (0.171), Tallahassee Lassie (0.170), Drum Major (0.169)
- **Lane B (paper):** Our Fella (0.178), Tallahassee Lassie (0.172), Drum Major (0.169) ⚠ PAPER_ONLY_NO_INTENT

### 15:07 Downpatrick — Join Racing TV Now With A Free Trial Handicap Hurd **[LOW_DATA]**
- Runners: 15 | Passport: 4/15 ⚠ WEAK_DATA
- **Lane A (operational):** Sea Of Doubt (0.080), Centaq (0.079), Trixaboutmaisie (0.073)
- **Lane B (paper):** Sea Of Doubt (0.083), Centaq (0.074), Trixaboutmaisie (0.066) ⚠ PAPER_ONLY_NO_INTENT

### 15:17 Beverley — Malcolm Greenslade Doncaster LVA Stalwart Memorial **[FRAME_TRUST]**
- Runners: 4 | Passport: 4/4
- **Lane A (operational):** Pendella (0.273), Mandarin Spirit (0.229), Tamzan (0.198)
- **Lane B (paper):** Pendella (0.205), Mandarin Spirit (0.157), Tamzan (0.164) ⚠ PAPER_ONLY_NO_INTENT

### 15:24 Leicester — Join Racing TV Today Handicap **[NO_EDGE]**
- Runners: 6 | Passport: 5/6 ⚠ WEAK_DATA
- **Lane A (operational):** Port Hedland (0.211), Dreambird Dolly (0.165), Nzuri (0.146)
- **Lane B (paper):** Port Hedland (0.176), Dreambird Dolly (0.135), Nzuri (0.138) ⚠ PAPER_ONLY_NO_INTENT

### 15:30 Ffos Las — Diplomat Hotel Maiden Stakes (GBB Race) **[NO_EDGE]**
- Runners: 7 | Passport: 1/7 ⚠ WEAK_DATA
- **Lane A (operational):** Queen Sana (0.141), Far From Fern (0.133), Star Velocity (0.131)
- **Lane B (paper):** Far From Fern (0.125), Star Velocity (0.123), Kodicall (0.124) ⚠ PAPER_ONLY_NO_INTENT

### 15:37 Downpatrick — Plus 2 Print Remembering Tony Oakes MBE Maiden Hur **[SUPPRESS]**
- Runners: 12 | Passport: 2/12 ⚠ WEAK_DATA
- **Lane A (operational):** Sampoet (0.105), Marcelrock (0.100), Spill A Drop (0.096)
- **Lane B (paper):** Marcelrock (0.087), Spill A Drop (0.079), O'Callaghan Can (0.088) ⚠ PAPER_ONLY_NO_INTENT

### 15:48 Beverley — Beverley Annual Badgeholders Handicap **[NO_EDGE]**
- Runners: 9 | Passport: 6/9 ⚠ WEAK_DATA
- **Lane A (operational):** Kitsune Power (0.133), Lever Up (0.132), Wicklow Way (0.112)
- **Lane B (paper):** Kitsune Power (0.115), Lever Up (0.138), Star Start (0.095) ⚠ PAPER_ONLY_NO_INTENT

### 15:57 Leicester — Evening Racing @leicesterraces Wednesday 22nd July **[FRAME_TRUST]**
- Runners: 6 | Passport: 6/6
- **Lane A (operational):** Arvana Belle (0.229), Auspicious (0.199), Musical Soldier (0.182)
- **Lane B (paper):** Arvana Belle (0.205), Auspicious (0.155), Poetic Grace (0.145) ⚠ PAPER_ONLY_NO_INTENT

### 16:05 Ffos Las — Preventapest Handicap **[LOW_DATA]**
- Runners: 9 | Passport: 4/9 ⚠ WEAK_DATA
- **Lane A (operational):** Tokyo Joe (0.102), Dandy G Boy (0.101), Mayberry Moon (0.100)
- **Lane B (paper):** Tokyo Joe (0.096), Dandy G Boy (0.109), Freddie's Star (0.108) ⚠ PAPER_ONLY_NO_INTENT

### 16:12 Downpatrick — Go fibrefast With Fibrus Broadband Rated Novice Hu **[FRAME_TRUST]**
- Runners: 6 | Passport: 5/6 ⚠ WEAK_DATA
- **Lane A (operational):** Lemmy Caution (0.262), Surfin Usa (0.151), Gangster Granny (0.142)
- **Lane B (paper):** Lemmy Caution (0.213), Playtime (0.172), Written In My Soul (0.139) ⚠ PAPER_ONLY_NO_INTENT

### 16:23 Beverley — Connexin Gigabit Gallop Handicap **[LOW_DATA]**
- Runners: 10 | Passport: 6/10 ⚠ WEAK_DATA
- **Lane A (operational):** Barmyblade (0.100), Pinpoint (0.099), Without Flaw (0.098)
- **Lane B (paper):** Barmyblade (0.093), Pinpoint (0.091), Without Flaw (0.094) ⚠ PAPER_ONLY_NO_INTENT

### 16:30 Leicester — Leicester Racecourse Ideal Conference Venue Fillie **[WIN_TRUST]**
- Runners: 4 | Passport: 4/4
- **Lane A (operational):** Bergamo Gold (0.324), Melody De Vega (0.264), Hot Silk (0.234)
- **Lane B (paper):** Bergamo Gold (0.284), Melody De Vega (0.233), Fille Imbassee (0.162) ⚠ PAPER_ONLY_NO_INTENT

### 16:40 Ffos Las — Dandara, Beautiful New Homes In Carway "Confined"  **[NO_EDGE]**
- Runners: 9 | Passport: 5/9 ⚠ WEAK_DATA
- **Lane A (operational):** Homeland (0.110), Hammal (0.108), Havana Tobouggaloo (0.106)
- **Lane B (paper):** Homeland (0.112), Hammal (0.098), Havana Tobouggaloo (0.099) ⚠ PAPER_ONLY_NO_INTENT

### 16:47 Downpatrick — Tote Guarantee, Never Beaten By SP Handicap Hurdle **[SUPPRESS]**
- Runners: 13 | Passport: 5/13 ⚠ WEAK_DATA
- **Lane A (operational):** Mephisto (0.078), Nakassama (0.078), Ringdufferin (0.078)
- **Lane B (paper):** Nakassama (0.076), Oh Janey (0.067), Adaliz (0.068) ⚠ PAPER_ONLY_NO_INTENT

### 16:53 Wolverhampton (AW) — Sky Sports Racing Sky 415 Fillies' Handicap **[NO_EDGE]**
- Runners: 9 | Passport: 5/9 ⚠ WEAK_DATA
- **Lane A (operational):** Desert Belle (0.191), Lady Magu (0.146), Ghost Story (0.138)
- **Lane B (paper):** Desert Belle (0.144), Lady Magu (0.156), Ghost Story (0.120) ⚠ PAPER_ONLY_NO_INTENT

### 16:58 Beverley — Racing Again On Monday Evening Handicap **[NO_EDGE]**
- Runners: 8 | Passport: 6/8 ⚠ WEAK_DATA
- **Lane A (operational):** Viviana (0.162), The Sweet Escape (0.140), Shahik (0.133)
- **Lane B (paper):** Viviana (0.139), The Sweet Escape (0.119), Enjoy The Night (0.116) ⚠ PAPER_ONLY_NO_INTENT

### 17:04 Leicester — Private Boxes For Best View @leicesterraces Classi **[NO_EDGE]**
- Runners: 11 | Passport: 7/11 ⚠ WEAK_DATA
- **Lane A (operational):** Rogue Rebellion (0.157), Bullington Bry (0.122), Gardening (0.121)
- **Lane B (paper):** Rogue Rebellion (0.132), Bullington Bry (0.114), Gardening (0.112) ⚠ PAPER_ONLY_NO_INTENT

### 17:09 Killarney — Irish Stallion Farms EBF Fillies Maiden **[LOW_DATA]**
- Runners: 5 | Passport: 0/5 ⚠ WEAK_DATA
- **Lane A (operational):** Capolinea (0.196), Acanto (0.170), Taj Crown (0.169)
- **Lane B (paper):** Capolinea (0.178), Acanto (0.160), Glittering Gem (0.160) ⚠ PAPER_ONLY_NO_INTENT

### 17:14 Ffos Las — Dandara, Find Your Perfect New Home Handicap **[LOW_DATA]**
- Runners: 4 | Passport: 2/4 ⚠ WEAK_DATA
- **Lane A (operational):** Liveinthelight (0.231), Caelan (0.229), Meet Me In Meraki (0.199)
- **Lane B (paper):** Liveinthelight (0.207), Caelan (0.198), Meet Me In Meraki (0.187) ⚠ PAPER_ONLY_NO_INTENT

### 17:19 Downpatrick — Downpatrick Racecourse Family Funday Supporters IN **[LOW_DATA]**
- Runners: 10 | Passport: 1/10 ⚠ WEAK_DATA
- **Lane A (operational):** Be My Fortune (0.155), Its Time For A Run (0.155), Poets Walk Paris (0.155)
- **Lane B (paper):** Be My Fortune (0.145), Its Time For A Run (0.145), Poets Walk Paris (0.145) ⚠ PAPER_ONLY_NO_INTENT

### 17:25 Wolverhampton (AW) — Free Tips On attheraces.com Restricted Maiden Stak **[LOW_DATA]**
- Runners: 11 | Passport: 3/11 ⚠ WEAK_DATA
- **Lane A (operational):** George Wickham (0.092), Good Guys Girl (0.091), Smooth Flight (0.090)
- **Lane B (paper):** George Wickham (0.086), Smooth Flight (0.085), Deadline (0.086) ⚠ PAPER_ONLY_NO_INTENT

### 17:40 Killarney — Hotel Killarney Maiden **[NO_EDGE]**
- Runners: 8 | Passport: 2/8 ⚠ WEAK_DATA
- **Lane A (operational):** Sron Na Caise (0.129), Mischievous Fun (0.121), Desert Swing (0.121)
- **Lane B (paper):** Sron Na Caise (0.116), Mischievous Fun (0.111), Desert Swing (0.111) ⚠ PAPER_ONLY_NO_INTENT

### 17:55 Wolverhampton (AW) — attheraces.com/marketmovers Handicap **[NO_EDGE]**
- Runners: 10 | Passport: 7/10 ⚠ WEAK_DATA
- **Lane A (operational):** Manly Fireball (0.150), Night Storm (0.141), Charlie Mason (0.134)
- **Lane B (paper):** Night Storm (0.123), Charlie Mason (0.126), American Style (0.119) ⚠ PAPER_ONLY_NO_INTENT

### 18:10 Killarney — Irish Examiner Handicap **[NO_EDGE]**
- Runners: 12 | Passport: 9/12 ⚠ WEAK_DATA
- **Lane A (operational):** Beau Army (0.104), Sayonara (0.101), Cause I Like You (0.088)
- **Lane B (paper):** Beau Army (0.104), Ramair (0.076), Wingit (0.074) ⚠ PAPER_ONLY_NO_INTENT

### 18:25 Wolverhampton (AW) — Download The At The Races App Maiden Stakes (GBB R **[LOW_DATA]**
- Runners: 12 | Passport: 4/12 ⚠ WEAK_DATA
- **Lane A (operational):** Charlemont GG (0.088), Hey Dude (0.086), Best Yet (0.085)
- **Lane B (paper):** Charlemont GG (0.080), Minzaal Time (0.083), La Fuerza (0.081) ⚠ PAPER_ONLY_NO_INTENT

### 18:37 Longchamp — Cygames Prix de Malleret (Group 2) (Fillies) (Turf **[LOW_DATA]**
- Runners: 5 | Passport: 2/5 ⚠ WEAK_DATA
- **Lane A (operational):** Zlata (0.168), Proxima Du Centaur (0.168), Pink Panthera (0.167)
- **Lane B (paper):** Zlata (0.158), Behrayna (0.164), Dispatches (0.162) ⚠ PAPER_ONLY_NO_INTENT

### 18:40 Killarney — Killarney Plaza Hotel & Spa Handicap **[SUPPRESS]**
- Runners: 14 | Passport: 7/14 ⚠ WEAK_DATA
- **Lane A (operational):** Mythical Rock (0.107), Elusive Duke (0.090), Majestic King (0.086)
- **Lane B (paper):** Mythical Rock (0.092), Elusive Duke (0.080), Hexagonal (0.071) ⚠ PAPER_ONLY_NO_INTENT

### 18:55 Wolverhampton (AW) — Free Bets On attheraces.com Handicap (Div I) **[SUPPRESS]**
- Runners: 11 | Passport: 8/11 ⚠ WEAK_DATA
- **Lane A (operational):** Sanditon (0.116), Dancing With Drums (0.113), On Key (0.099)
- **Lane B (paper):** Sanditon (0.090), Dancing With Drums (0.102), Quite Sweet (0.082) ⚠ PAPER_ONLY_NO_INTENT

### 19:10 Killarney — Irish Stallion Farms EBF Fillies Handicap **[NO_EDGE]**
- Runners: 9 | Passport: 4/9 ⚠ WEAK_DATA
- **Lane A (operational):** Diamond Exchange (0.162), My Girl Grace (0.106), Concert Party (0.099)
- **Lane B (paper):** Diamond Exchange (0.115), My Girl Grace (0.113), Concert Party (0.098) ⚠ PAPER_ONLY_NO_INTENT

### 19:15 Longchamp — Cygames Grand Prix de Paris (Group 1) (No Geldings **[NO_EDGE]**
- Runners: 7 | Passport: 5/7 ⚠ WEAK_DATA
- **Lane A (operational):** Maltese Cross (0.216), Causeway (0.205), Limestone (0.203)
- **Lane B (paper):** Maltese Cross (0.152), Causeway (0.156), Limestone (0.140) ⚠ PAPER_ONLY_NO_INTENT

### 19:25 Wolverhampton (AW) — Free Bets On attheraces.com Handicap (Div II) **[NO_EDGE]**
- Runners: 9 | Passport: 6/9 ⚠ WEAK_DATA
- **Lane A (operational):** Classy Clarets (0.207), Dayman (0.133), Whitesnake (0.112)
- **Lane B (paper):** Classy Clarets (0.148), Dayman (0.115), Whitesnake (0.102) ⚠ PAPER_ONLY_NO_INTENT

### 19:40 Killarney — Rose Hotel Handicap **[NO_EDGE]**
- Runners: 8 | Passport: 3/8 ⚠ WEAK_DATA
- **Lane A (operational):** Tribal Star (0.135), Individualism (0.113), Persian Bliss (0.108)
- **Lane B (paper):** Tribal Star (0.128), Individualism (0.105), Persian Bliss (0.103) ⚠ PAPER_ONLY_NO_INTENT

### 19:50 Longchamp — Radio FG - Prix Maurice de Nieuil (Group 2) (Turf) **[LOW_DATA]**
- Runners: 6 | Passport: 1/6 ⚠ WEAK_DATA
- **Lane A (operational):** Sons And Lovers (0.151), Parachutiste (0.150), Barbate (0.148)
- **Lane B (paper):** Sons And Lovers (0.138), Parachutiste (0.139), Espoir Avenir (0.139) ⚠ PAPER_ONLY_NO_INTENT

### 19:55 Wolverhampton (AW) — Follow @attheraces On X Handicap **[SUPPRESS]**
- Runners: 12 | Passport: 9/12 ⚠ WEAK_DATA
- **Lane A (operational):** Roman Secret (0.106), Educate (0.091), Late Claim (0.089)
- **Lane B (paper):** Roman Secret (0.090), Educate (0.076), Galistra (0.075) ⚠ PAPER_ONLY_NO_INTENT

### 20:10 Killarney — Thorn Plant Hire (Q.R.) Maiden **[NO_EDGE]**
- Runners: 13 | Passport: 8/13 ⚠ WEAK_DATA
- **Lane A (operational):** Catalani (0.207), Lauro's Legend (0.117), Sunny South West (0.113)
- **Lane B (paper):** Catalani (0.103), Sunny South West (0.105), Eagle Fang (0.102) ⚠ PAPER_ONLY_NO_INTENT

## Boundaries
- Paper-only intelligence. No betting instruction.
- No Telegram, staking, live scoring table writes, or official-pick override.
- Old Live VÉLØ and Shadow VÉLØ untouched.
- RPR archive-only. No SP in morning model. No JTC-D all-time sidecar.