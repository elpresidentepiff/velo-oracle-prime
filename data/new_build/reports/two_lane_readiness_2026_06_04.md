# Race Day Two-Lane Readiness: 2026-06-04
Generated: 2026-06-04T21:51:39.687535Z

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

## Race Day Scorecards — 2026-06-04
_43 races, 391 runners_

### 14:00 Uttoxeter — Racing To School Reaches 25 Years Novices' Hurdle  **[WIN_TRUST]**
- Runners: 5 | Passport: 5/5
- **Lane A (operational):** Starshine Legend (0.296), White Riot (0.292), Biggles (0.257)
- **Lane B (paper):** Starshine Legend (0.266), White Riot (0.240), Loriko (0.209) ⚠ PAPER_ONLY_NO_INTENT

### 14:12 Wetherby — Vauxhall Knaresborough Britsh EBF Fillies' Restric **[FRAME_TRUST]**
- Runners: 8 | Passport: 7/8 ⚠ WEAK_DATA
- **Lane A (operational):** Ziggy Starshine (0.261), Birkacre Brow (0.131), Wateera (0.109)
- **Lane B (paper):** Ziggy Starshine (0.176), Birkacre Brow (0.122), Wateera (0.111) ⚠ PAPER_ONLY_NO_INTENT

### 14:21 Hamilton — Sodexo Live! 2yo Series EBF Maiden Fillies' Stakes **[WIN_TRUST]**
- Runners: 4 | Passport: 4/4
- **Lane A (operational):** Jazz Queen (0.356), Meennaa (0.348), Angels Passing (0.189)
- **Lane B (paper):** Jazz Queen (0.310), Meennaa (0.248), Angels Passing (0.198) ⚠ PAPER_ONLY_NO_INTENT

### 14:30 Uttoxeter — JAL Roofing Novices' Hurdle (GBB Race) **[LOW_DATA]**
- Runners: 6 | Passport: 5/6 ⚠ WEAK_DATA
- **Lane A (operational):** Presentandcorrect (0.151), Millena Agent (0.131), Executive Producer (0.107)
- **Lane B (paper):** Presentandcorrect (0.132), Millena Agent (0.135), Coumeenoole (0.095) ⚠ PAPER_ONLY_NO_INTENT

### 14:42 Wetherby — Vauxhall Knaresborough Britsh EBF Fillies' Restric **[NO_EDGE]**
- Runners: 9 | Passport: 8/9 ⚠ WEAK_DATA
- **Lane A (operational):** Mardy Bum (0.137), Beautiful Rainbow (0.127), Someone To Love (0.104)
- **Lane B (paper):** Mardy Bum (0.144), Beautiful Rainbow (0.111), Angel Steps (0.099) ⚠ PAPER_ONLY_NO_INTENT

### 14:51 Hamilton — Morton Fraser Macroberts LLP Handicap **[SUPPRESS]**
- Runners: 10 | Passport: 10/10
- **Lane A (operational):** Thunderstorm Katie (0.108), Wish This (0.101), Kelpie Grey (0.099)
- **Lane B (paper):** Thunderstorm Katie (0.098), Wish This (0.095), Kelpie Grey (0.089) ⚠ PAPER_ONLY_NO_INTENT

### 15:00 Uttoxeter — Nourkrin Handicap Hurdle **[SUPPRESS]**
- Runners: 8 | Passport: 8/8
- **Lane A (operational):** Tiger Orchid (0.130), Breezethroughlife (0.114), Noble Birth (0.110)
- **Lane B (paper):** Breezethroughlife (0.113), Noble Birth (0.130), Secret Trix (0.106) ⚠ PAPER_ONLY_NO_INTENT

### 15:12 Wetherby — Amstel Fillies' Novice Stakes (GBB Race) **[NO_EDGE]**
- Runners: 7 | Passport: 7/7
- **Lane A (operational):** Black Orchid (0.276), Overbudget (0.218), Reigning Queen (0.203)
- **Lane B (paper):** Black Orchid (0.184), Overbudget (0.230), Viviana (0.174) ⚠ PAPER_ONLY_NO_INTENT

### 15:21 Hamilton — Weatherbys Global Stallions Handicap **[NO_EDGE]**
- Runners: 9 | Passport: 9/9
- **Lane A (operational):** Obito (0.148), Tee Aitch Aye (0.130), Zowal (0.123)
- **Lane B (paper):** Obito (0.158), Tee Aitch Aye (0.133), Highland Olly (0.112) ⚠ PAPER_ONLY_NO_INTENT

### 15:30 Uttoxeter — JMI Planning 10 Years In Business Mares' Handicap  **[WIN_TRUST]**
- Runners: 4 | Passport: 4/4
- **Lane A (operational):** That's Nice (0.261), Regal Renaissance (0.242), Queens Wish (0.239)
- **Lane B (paper):** That's Nice (0.274), Regal Renaissance (0.205), Queens Wish (0.238) ⚠ PAPER_ONLY_NO_INTENT

### 15:42 Wetherby — Heineken 0.0 Fillies' Handicap **[SUPPRESS]**
- Runners: 14 | Passport: 14/14
- **Lane A (operational):** Seeing Stars (0.125), Volendam (0.115), Nanoscience (0.112)
- **Lane B (paper):** Volendam (0.090), Magic Box (0.091), Dream Illusion (0.096) ⚠ PAPER_ONLY_NO_INTENT

### 15:51 Hamilton — Weatherbys Digital Solutions Clyde Handicap **[NO_EDGE]**
- Runners: 7 | Passport: 6/7 ⚠ WEAK_DATA
- **Lane A (operational):** Altareq (0.160), Eternal Force (0.160), Two B Tanned (0.134)
- **Lane B (paper):** Altareq (0.133), Eternal Force (0.145), Botanical (0.139) ⚠ PAPER_ONLY_NO_INTENT

### 16:00 Uttoxeter — Litholexal Handicap Hurdle **[SUPPRESS]**
- Runners: 9 | Passport: 9/9
- **Lane A (operational):** Brionywells (0.111), Bells Of Ufford (0.107), The Best Way (0.106)
- **Lane B (paper):** Bells Of Ufford (0.089), Hillsin (0.115), Pepite De Saphir (0.097) ⚠ PAPER_ONLY_NO_INTENT

### 16:12 Wetherby — Malvern Castle And Compass Hospitality Handicap **[NO_EDGE]**
- Runners: 9 | Passport: 9/9
- **Lane A (operational):** Sovereign Bright (0.156), Ciao Capo (0.124), Stepanov (0.118)
- **Lane B (paper):** Sovereign Bright (0.158), Ciao Capo (0.101), Stepanov (0.118) ⚠ PAPER_ONLY_NO_INTENT

### 16:21 Hamilton — Aspire Cleaning & Facilities Ltd Handicap **[NO_EDGE]**
- Runners: 6 | Passport: 6/6
- **Lane A (operational):** Parisiac (0.159), Call To Action (0.153), Water Of Leith (0.143)
- **Lane B (paper):** Call To Action (0.123), Water Of Leith (0.127), Hi Lord (0.125) ⚠ PAPER_ONLY_NO_INTENT

### 16:30 Uttoxeter — Turf Services Handicap Chase (ARC Summer Chase Ser **[FRAME_TRUST]**
- Runners: 6 | Passport: 6/6
- **Lane A (operational):** Karnaval Point (0.182), Wheresmemoneygone (0.181), Immortal Fame (0.147)
- **Lane B (paper):** Karnaval Point (0.179), Wheresmemoneygone (0.128), Immortal Fame (0.150) ⚠ PAPER_ONLY_NO_INTENT

### 16:42 Wetherby — Book Your Autumn Hospitality Packages Now Handicap **[SUPPRESS]**
- Runners: 16 | Passport: 16/16
- **Lane A (operational):** Inspired (0.102), Stratocracy (0.081), Catalyse (0.081)
- **Lane B (paper):** Inspired (0.090), Catalyse (0.079), Lady Mariko (0.076) ⚠ PAPER_ONLY_NO_INTENT

### 16:51 Hamilton — Sodexo Live! Events Handicap **[NO_EDGE]**
- Runners: 8 | Passport: 7/8 ⚠ WEAK_DATA
- **Lane A (operational):** Jujubella (0.141), Clansman (0.133), Sure And Stedfast (0.124)
- **Lane B (paper):** Jujubella (0.124), Clansman (0.104), Sure And Stedfast (0.103) ⚠ PAPER_ONLY_NO_INTENT

### 17:03 Uttoxeter — Quinnbet Handicap Hurdle **[SUPPRESS]**
- Runners: 7 | Passport: 7/7
- **Lane A (operational):** Calibos (0.112), Genbu (0.089), Clever Relation (0.081)
- **Lane B (paper):** Lively Citizen (0.092), Zucayan (0.065), Ask A Sainte (0.067) ⚠ PAPER_ONLY_NO_INTENT

### 17:10 Lingfield (AW) — Sky Sports Racing Virgin 512 Handicap **[NO_EDGE]**
- Runners: 12 | Passport: 12/12
- **Lane A (operational):** Francisco (0.115), Dashing Donkey (0.108), Fort Augustus (0.107)
- **Lane B (paper):** Francisco (0.108), Dashing Donkey (0.104), Fort Augustus (0.092) ⚠ PAPER_ONLY_NO_INTENT

### 17:15 Wetherby — Live Streams On Racing TV Extra Handicap **[NO_EDGE]**
- Runners: 10 | Passport: 8/10 ⚠ WEAK_DATA
- **Lane A (operational):** Dragon God (0.124), Eldeyaar (0.102), Mrs Trump (0.097)
- **Lane B (paper):** Dragon God (0.113), Amerjeet (0.090), He's An Angel (0.090) ⚠ PAPER_ONLY_NO_INTENT

### 17:22 Hamilton — Hampton By Hilton Hamilton Park Handicap **[NO_EDGE]**
- Runners: 11 | Passport: 10/11 ⚠ WEAK_DATA
- **Lane A (operational):** Uncle Liam (0.135), Ravenswell (0.128), Recobella (0.091)
- **Lane B (paper):** Uncle Liam (0.112), Ravenswell (0.120), Recobella (0.085) ⚠ PAPER_ONLY_NO_INTENT

### 17:30 Leopardstown — Irish Stallion Farms EBF Fillies Maiden (IRE Incen **[SUPPRESS]**
- Runners: 11 | Passport: 10/11 ⚠ WEAK_DATA
- **Lane A (operational):** Honey Deuce (0.086), Blonde Over Blue (0.086), Margot Mae (0.086)
- **Lane B (paper):** Honey Deuce (0.086), Blonde Over Blue (0.088), Alpha (0.087) ⚠ PAPER_ONLY_NO_INTENT

### 17:40 Lingfield (AW) — attheraces.com/marketmovers Handicap **[NO_EDGE]**
- Runners: 7 | Passport: 6/7 ⚠ WEAK_DATA
- **Lane A (operational):** Peregrine Falcon (0.174), Shalaa Asker (0.158), Desdemona (0.157)
- **Lane B (paper):** Peregrine Falcon (0.162), Desdemona (0.146), Style King (0.149) ⚠ PAPER_ONLY_NO_INTENT

### 17:50 Wetherby — Book Tickets Online At wetherbyracing.co.uk Handic **[NO_EDGE]**
- Runners: 9 | Passport: 8/9 ⚠ WEAK_DATA
- **Lane A (operational):** Surgeon Commander (0.158), Data Fata Secutus (0.137), Dabbling (0.114)
- **Lane B (paper):** Surgeon Commander (0.121), Data Fata Secutus (0.117), Dabbling (0.114) ⚠ PAPER_ONLY_NO_INTENT

### 18:00 Leopardstown — BOYLE Sports Apprentice Handicap **[NO_EDGE]**
- Runners: 11 | Passport: 11/11
- **Lane A (operational):** Playin Cool (0.137), Mehman (0.114), Eddie G (0.111)
- **Lane B (paper):** Playin Cool (0.120), Mehman (0.083), Eddie G (0.106) ⚠ PAPER_ONLY_NO_INTENT

### 18:10 Lingfield (AW) — Sky Sports Racing Sky 415 'Confined' EBF Fillies'  **[NO_EDGE]**
- Runners: 13 | Passport: 12/13 ⚠ WEAK_DATA
- **Lane A (operational):** Sunshine Star (0.145), Kenkelly (0.102), Lightning Glory (0.098)
- **Lane B (paper):** Sunshine Star (0.133), Kenkelly (0.095), Musical Accord (0.086) ⚠ PAPER_ONLY_NO_INTENT

### 18:20 Ffos Las — Simply Safe Care Group Handicap **[FRAME_TRUST]**
- Runners: 8 | Passport: 7/8 ⚠ WEAK_DATA
- **Lane A (operational):** Arishka's Dream (0.255), La Belle Forest (0.206), Arctic Wind (0.148)
- **Lane B (paper):** Arishka's Dream (0.202), La Belle Forest (0.194), Arctic Wind (0.112) ⚠ PAPER_ONLY_NO_INTENT

### 18:30 Leopardstown — King George V Cup (Listed Race) **[FRAME_TRUST]**
- Runners: 4 | Passport: 4/4
- **Lane A (operational):** Endorsement (0.279), Amadeus Mozart (0.254), Yousaynothingatall (0.248)
- **Lane B (paper):** Endorsement (0.207), Amadeus Mozart (0.197), Yousaynothingatall (0.196) ⚠ PAPER_ONLY_NO_INTENT

### 18:40 Lingfield (AW) — Free Bets On attheraces.com Handicap **[NO_EDGE]**
- Runners: 6 | Passport: 6/6
- **Lane A (operational):** Kaori (0.212), Extraterrestrial (0.205), Lexington Express (0.150)
- **Lane B (paper):** Kaori (0.187), Extraterrestrial (0.188), Lexington Express (0.154) ⚠ PAPER_ONLY_NO_INTENT

### 18:50 Ffos Las — Llanelli Mind Novice Stakes (GBB Race) **[NO_EDGE]**
- Runners: 6 | Passport: 6/6
- **Lane A (operational):** Persian Land (0.197), Real Trouble (0.188), Galipi (0.143)
- **Lane B (paper):** Persian Land (0.146), Real Trouble (0.184), Another Encore (0.143) ⚠ PAPER_ONLY_NO_INTENT

### 19:00 Leopardstown — Irish Stallion Farms EBF Median Auction Fillies Ma **[SUPPRESS]**
- Runners: 14 | Passport: 14/14
- **Lane A (operational):** Fleur De Provence (0.110), Bang Bang (0.103), Shanala (0.090)
- **Lane B (paper):** Fleur De Provence (0.086), Bang Bang (0.089), Shanala (0.089) ⚠ PAPER_ONLY_NO_INTENT

### 19:10 Lingfield (AW) — Free Tips On attheraces.com Fillies' Handicap **[NO_EDGE]**
- Runners: 9 | Passport: 8/9 ⚠ WEAK_DATA
- **Lane A (operational):** Polka Blue (0.169), Doodling (0.145), Ritaal (0.138)
- **Lane B (paper):** Doodling (0.160), Ritaal (0.138), Pretty Danielle (0.150) ⚠ PAPER_ONLY_NO_INTENT

### 19:20 Ffos Las — Pro Panther Handicap **[NO_EDGE]**
- Runners: 13 | Passport: 12/13 ⚠ WEAK_DATA
- **Lane A (operational):** Orchard (0.113), Opening Bat (0.105), Grey Soul (0.094)
- **Lane B (paper):** Orchard (0.102), Opening Bat (0.104), Auburn Avenue (0.079) ⚠ PAPER_ONLY_NO_INTENT

### 19:30 Leopardstown — BOYLE Sports 'Home Of The Early Payout' Handicap **[NO_EDGE]**
- Runners: 8 | Passport: 7/8 ⚠ WEAK_DATA
- **Lane A (operational):** Johnny Soda (0.158), Monvoe (0.146), Red Autumn (0.119)
- **Lane B (paper):** Johnny Soda (0.152), Monvoe (0.104), Red Autumn (0.106) ⚠ PAPER_ONLY_NO_INTENT

### 19:40 Lingfield (AW) — Download The At The Races App EBF Restricted Maide **[SUPPRESS]**
- Runners: 10 | Passport: 10/10
- **Lane A (operational):** Fire Thunder (0.127), Doha Rd (0.108), It'sbeenemotional (0.105)
- **Lane B (paper):** Doha Rd (0.109), It'sbeenemotional (0.099), Defiant Dream (0.093) ⚠ PAPER_ONLY_NO_INTENT

### 19:50 Ffos Las — New Thomas Arms Handicap **[FRAME_TRUST]**
- Runners: 9 | Passport: 7/9 ⚠ WEAK_DATA
- **Lane A (operational):** Reem Rak (0.183), Al's River (0.110), Salkadan (0.108)
- **Lane B (paper):** Reem Rak (0.180), Al's River (0.099), Kelly Burn (0.095) ⚠ PAPER_ONLY_NO_INTENT

### 20:00 Leopardstown — BOYLE Sports Best Odds From 8am Handicap **[SUPPRESS]**
- Runners: 16 | Passport: 16/16
- **Lane A (operational):** Harana (0.118), Molto Amichi (0.088), Daler (0.088)
- **Lane B (paper):** Harana (0.096), Molto Amichi (0.084), Daler (0.087) ⚠ PAPER_ONLY_NO_INTENT

### 20:10 Lingfield (AW) — Download The At The Races App EBF Restricted Maide **[SUPPRESS]**
- Runners: 10 | Passport: 9/10 ⚠ WEAK_DATA
- **Lane A (operational):** Forest Berry (0.116), Potters Margot (0.101), Happy Humpo (0.099)
- **Lane B (paper):** Happy Humpo (0.095), Clear Horizon (0.093), Ron's Angel (0.093) ⚠ PAPER_ONLY_NO_INTENT

### 20:20 Ffos Las — Go Maintenance Classified Stakes **[NO_EDGE]**
- Runners: 8 | Passport: 7/8 ⚠ WEAK_DATA
- **Lane A (operational):** Belle Amie (0.178), Hedonista (0.115), Highland Harvey (0.115)
- **Lane B (paper):** Belle Amie (0.134), Hedonista (0.104), Buck Barrow (0.097) ⚠ PAPER_ONLY_NO_INTENT

### 20:30 Leopardstown — Leopardstown Premier Lounge Handicap **[SUPPRESS]**
- Runners: 17 | Passport: 17/17
- **Lane A (operational):** Down The Glen (0.080), Bear Right (0.067), Cosmic Funk (0.067)
- **Lane B (paper):** Down The Glen (0.071), Love Orchid (0.065), Glamazon (0.065) ⚠ PAPER_ONLY_NO_INTENT

### 20:40 Lingfield (AW) — Follow @attheraces On X Handicap **[SUPPRESS]**
- Runners: 11 | Passport: 10/11 ⚠ WEAK_DATA
- **Lane A (operational):** Sail On Sailor (0.118), Beryl's Girl (0.103), Lordsbridge Bay (0.099)
- **Lane B (paper):** Beryl's Girl (0.084), Lordsbridge Bay (0.088), Angel Summer (0.081) ⚠ PAPER_ONLY_NO_INTENT

### 20:50 Ffos Las — New Thomas Arms Handicap **[WIN_TRUST]**
- Runners: 6 | Passport: 6/6
- **Lane A (operational):** Premier (0.231), Ghost Story (0.189), Crackergee (0.144)
- **Lane B (paper):** Premier (0.231), Ghost Story (0.175), Crackergee (0.149) ⚠ PAPER_ONLY_NO_INTENT

## Boundaries
- Paper-only intelligence. No betting instruction.
- No Telegram, staking, live scoring table writes, or official-pick override.
- Old Live VÉLØ and Shadow VÉLØ untouched.
- RPR archive-only. No SP in morning model. No JTC-D all-time sidecar.