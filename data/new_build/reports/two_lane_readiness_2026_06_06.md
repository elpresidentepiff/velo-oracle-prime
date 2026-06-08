# Race Day Two-Lane Readiness: 2026-06-06
Generated: 2026-06-06T16:10:38.907821Z

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

## Race Day Scorecards — 2026-06-06
_49 races, 448 runners_

### 13:20 Doncaster — Northwick Group Handicap **[SUPPRESS]**
- Runners: 16 | Passport: 16/16
- **Lane A (operational):** Instant Bond (0.107), Moonhall Lass (0.105), Candy Warhol (0.093)
- **Lane B (paper):** Instant Bond (0.075), Moonhall Lass (0.085), Bibendum (0.075) ⚠ PAPER_ONLY_NO_INTENT

### 13:30 Epsom — Betfred Tattenham Corner Stakes (Group 3) (Formerl **[NO_EDGE]**
- Runners: 8 | Passport: 8/8
- **Lane A (operational):** Poet Master (0.123), Never So Brave (0.122), Alcantor (0.118)
- **Lane B (paper):** Poet Master (0.123), Never So Brave (0.119), Alcantor (0.126) ⚠ PAPER_ONLY_NO_INTENT

### 13:40 Musselburgh — Edinburgh Gin Rhubarb And Ginger Handicap **[FRAME_TRUST]**
- Runners: 7 | Passport: 7/7
- **Lane A (operational):** Classy Clarets (0.224), Fear And Fast (0.185), Wee Mary (0.182)
- **Lane B (paper):** Classy Clarets (0.182), Fear And Fast (0.179), Wee Mary (0.173) ⚠ PAPER_ONLY_NO_INTENT

### 13:45 Worcester — FBC Manby Bowdler Mares' Handicap Chase (Arc Summe **[NO_EDGE]**
- Runners: 4 | Passport: 4/4
- **Lane A (operational):** She Is For Me Boys (0.259), Laffer Curve (0.233), Miss Denver (0.143)
- **Lane B (paper):** She Is For Me Boys (0.241), Laffer Curve (0.268), Miss Denver (0.145) ⚠ PAPER_ONLY_NO_INTENT

### 13:55 Doncaster — British Stallion Studs EBF Maiden Fillies' Stakes  **[NO_EDGE]**
- Runners: 6 | Passport: 6/6
- **Lane A (operational):** Rhodes Runner (0.243), Jazz Queen (0.238), Cash Cove (0.172)
- **Lane B (paper):** Rhodes Runner (0.209), Jazz Queen (0.247), Cash Cove (0.152) ⚠ PAPER_ONLY_NO_INTENT

### 14:05 Epsom — Princess Elizabeth Stakes (Group 3) (Fillies & Mar **[NO_EDGE]**
- Runners: 8 | Passport: 8/8
- **Lane A (operational):** Breckenbrough (0.163), Pina Sonata (0.136), Shes Perfect (0.123)
- **Lane B (paper):** Breckenbrough (0.125), Pina Sonata (0.112), Pacific Mission (0.101) ⚠ PAPER_ONLY_NO_INTENT

### 14:15 Musselburgh — Edinburgh Gin Hugo Spritz Selling Stakes **[NO_EDGE]**
- Runners: 7 | Passport: 7/7
- **Lane A (operational):** Havana Gift (0.181), Needin' U (0.167), Tree Wizard (0.158)
- **Lane B (paper):** Havana Gift (0.184), Needin' U (0.162), Tree Wizard (0.146) ⚠ PAPER_ONLY_NO_INTENT

### 14:20 Worcester — CopyBet Supporting UK Horse Racing Handicap Chase  **[NO_EDGE]**
- Runners: 11 | Passport: 11/11
- **Lane A (operational):** The Flying Poet (0.139), Captain Boudet (0.121), Redbridge Rambler (0.119)
- **Lane B (paper):** The Flying Poet (0.108), Captain Boudet (0.124), Jack To Bat (0.122) ⚠ PAPER_ONLY_NO_INTENT

### 14:30 Doncaster — Dysons And TPI Taping And Jointing Ltd Handicap **[SUPPRESS]**
- Runners: 10 | Passport: 10/10
- **Lane A (operational):** Naana's Sparkle (0.108), Master Of My Fate (0.097), Squealer (0.096)
- **Lane B (paper):** Master Of My Fate (0.099), Squealer (0.093), Paddy's Day (0.094) ⚠ PAPER_ONLY_NO_INTENT

### 14:40 Epsom — Coolmore Coronation Cup (Group 1) **[WIN_TRUST]**
- Runners: 6 | Passport: 6/6
- **Lane A (operational):** Calandagan (0.273), Jan Brueghel (0.242), Illinois (0.190)
- **Lane B (paper):** Calandagan (0.250), Jan Brueghel (0.233), Illinois (0.197) ⚠ PAPER_ONLY_NO_INTENT

### 14:50 Musselburgh — Edinburgh Gin Classic Handicap **[NO_EDGE]**
- Runners: 9 | Passport: 9/9
- **Lane A (operational):** Zubaru (0.147), Modern Times (0.136), Black Storm (0.123)
- **Lane B (paper):** Zubaru (0.109), Modern Times (0.125), Black Storm (0.101) ⚠ PAPER_ONLY_NO_INTENT

### 14:55 Worcester — Law Without The Horsing Around Handicap Chase (Arc **[NO_EDGE]**
- Runners: 9 | Passport: 9/9
- **Lane A (operational):** Culligran (0.172), Noble Recall (0.125), Jiair Madrik (0.121)
- **Lane B (paper):** Culligran (0.156), Noble Recall (0.113), Majestic Moment (0.132) ⚠ PAPER_ONLY_NO_INTENT

### 15:05 Doncaster — Solar Xpress Handicap (GBBPlus Race) **[NO_EDGE]**
- Runners: 6 | Passport: 6/6
- **Lane A (operational):** Siam Ruby (0.222), Lopeo (0.190), Gaelic Approach (0.187)
- **Lane B (paper):** Siam Ruby (0.168), Lopeo (0.170), Study Of Words (0.151) ⚠ PAPER_ONLY_NO_INTENT

### 15:15 Epsom — Betfred 'Dash' Handicap (Heritage Handicap) **[SUPPRESS]**
- Runners: 20 | Passport: 20/20
- **Lane A (operational):** Kinswoman (0.075), Star Chorus (0.063), Democracy Dilemma (0.062)
- **Lane B (paper):** Star Chorus (0.063), Cindy Lou Who (0.059), Rhythm N Hooves (0.052) ⚠ PAPER_ONLY_NO_INTENT

### 15:28 Musselburgh — Edinburgh Gin Queen Of Scots British EBF Fillies'  **[NO_EDGE]**
- Runners: 7 | Passport: 7/7
- **Lane A (operational):** La Brodeuse (0.157), Brazilian Rose (0.140), Figjam (0.103)
- **Lane B (paper):** La Brodeuse (0.136), Brazilian Rose (0.120), Circe (0.113) ⚠ PAPER_ONLY_NO_INTENT

### 15:33 Worcester — Manby Not Mandy Open National Hunt Flat Race (Cate **[NO_EDGE]**
- Runners: 9 | Passport: 9/9
- **Lane A (operational):** C'Est Pour Moi (0.140), Redbarn (0.098), Giant's Way (0.098)
- **Lane B (paper):** C'Est Pour Moi (0.131), Litaque (0.107), Delusionofgrandeur (0.107) ⚠ PAPER_ONLY_NO_INTENT

### 15:45 Doncaster — British Stallion Studs EBF Novice Stakes (GBB Race **[NO_EDGE]**
- Runners: 11 | Passport: 11/11
- **Lane A (operational):** Shipbourne (0.176), Flight Control (0.115), Blue Icon (0.087)
- **Lane B (paper):** Shipbourne (0.129), Blue Icon (0.085), Deadline (0.086) ⚠ PAPER_ONLY_NO_INTENT

### 16:00 Epsom — Betfred Derby (Group 1) (No Geldings) **[SUPPRESS]**
- Runners: 14 | Passport: 14/14
- **Lane A (operational):** Poker (0.116), Alderman (0.102), Item (0.102)
- **Lane B (paper):** Item (0.084), Pierre Bonnard (0.082), Action (0.080) ⚠ PAPER_ONLY_NO_INTENT

### 16:10 Musselburgh — Edinburgh Cup Handicap **[NO_EDGE]**
- Runners: 7 | Passport: 7/7
- **Lane A (operational):** Blues And Royals (0.196), Pandemonium (0.195), Magical Merlot (0.180)
- **Lane B (paper):** Blues And Royals (0.154), Pandemonium (0.210), Strength Of Spirit (0.177) ⚠ PAPER_ONLY_NO_INTENT

### 16:15 Worcester — #Bepartofit Novices' Hurdle (Arc Summer Novices' B **[NO_EDGE]**
- Runners: 8 | Passport: 8/8
- **Lane A (operational):** Little Lady Rock (0.212), Pioneer Pete (0.150), Solo Eclipse (0.122)
- **Lane B (paper):** Little Lady Rock (0.154), Pioneer Pete (0.114), Solo Eclipse (0.114) ⚠ PAPER_ONLY_NO_INTENT

### 16:25 Doncaster — Summer Saturday Series At Doncaster Racecourse Han **[NO_EDGE]**
- Runners: 11 | Passport: 11/11
- **Lane A (operational):** Monsieur Bondy (0.127), Montezin (0.108), Spell Master (0.105)
- **Lane B (paper):** Monsieur Bondy (0.104), Apotheosis (0.105), Akkadian Thunder (0.111) ⚠ PAPER_ONLY_NO_INTENT

### 16:30 Hexham — Marjorie Thompsett Auntie Marj Memorial Amateur Jo **[NO_EDGE]**
- Runners: 10 | Passport: 10/10
- **Lane A (operational):** Byron Hill (0.127), Fine Point (0.115), Ushuaia Dancer (0.114)
- **Lane B (paper):** Byron Hill (0.116), Fine Point (0.102), Ushuaia Dancer (0.101) ⚠ PAPER_ONLY_NO_INTENT

### 16:40 Epsom — Cherryfield (Croydon) Lester Piggott Handicap (GBB **[NO_EDGE]**
- Runners: 10 | Passport: 10/10
- **Lane A (operational):** York Tower (0.161), Silver State (0.157), Hell Yeah He Did (0.155)
- **Lane B (paper):** York Tower (0.136), Silver State (0.128), Hell Yeah He Did (0.130) ⚠ PAPER_ONLY_NO_INTENT

### 16:45 Musselburgh — Edinburgh Gin Seaside Holyrood Handicap **[NO_EDGE]**
- Runners: 8 | Passport: 8/8
- **Lane A (operational):** Kind Touch (0.193), Mighty Magnus (0.164), Major Neigh Sayer (0.161)
- **Lane B (paper):** Mighty Magnus (0.161), Major Neigh Sayer (0.144), Dandy Breeze (0.150) ⚠ PAPER_ONLY_NO_INTENT

### 16:50 Worcester — Best Scrap Metal Prices CRS Malvern Handicap Hurdl **[FRAME_TRUST]**
- Runners: 7 | Passport: 7/7
- **Lane A (operational):** Castle Ivers (0.188), Continuance (0.144), Trust House (0.129)
- **Lane B (paper):** Castle Ivers (0.185), Continuance (0.169), Bertie B (0.110) ⚠ PAPER_ONLY_NO_INTENT

### 17:00 Doncaster — attheraces.com Handicap **[SUPPRESS]**
- Runners: 11 | Passport: 11/11
- **Lane A (operational):** Amelia's Joy (0.114), Mayo County (0.111), Ziggy's Angel (0.107)
- **Lane B (paper):** Amelia's Joy (0.088), Ziggy's Angel (0.097), Highfield Sunshine (0.086) ⚠ PAPER_ONLY_NO_INTENT

### 17:05 Hexham — Most Important 3-Year-Old Race Today Juvenile Hurd **[WIN_TRUST]**
- Runners: 6 | Passport: 6/6
- **Lane A (operational):** Sudbury Hill (0.262), Steel Fixer (0.190), Mount Eden (0.187)
- **Lane B (paper):** Sudbury Hill (0.233), Mount Eden (0.145), Tiny Riot (0.106) ⚠ PAPER_ONLY_NO_INTENT

### 17:10 Chepstow — Michael Maine Memorial Cup Handicap **[NO_EDGE]**
- Runners: 9 | Passport: 9/9
- **Lane A (operational):** Call Time (0.170), Son Of Astar (0.147), Hidden Verse (0.146)
- **Lane B (paper):** Call Time (0.150), Son Of Astar (0.140), Hidden Verse (0.131) ⚠ PAPER_ONLY_NO_INTENT

### 17:15 Musselburgh — Edinburgh Gin Cannonball Handicap **[SUPPRESS]**
- Runners: 12 | Passport: 12/12
- **Lane A (operational):** Zebra Star (0.102), Monhammer (0.098), Samra Star (0.094)
- **Lane B (paper):** Samra Star (0.087), Freak Encounter (0.078), Pebble Dash (0.078) ⚠ PAPER_ONLY_NO_INTENT

### 17:20 Epsom — HKJC World Pool Northern Dancer Handicap (GBBPlus  **[SUPPRESS]**
- Runners: 16 | Passport: 16/16
- **Lane A (operational):** Bulletin (0.076), Dancing In Paris (0.070), Spinning Wheel (0.068)
- **Lane B (paper):** Bulletin (0.069), Dancing In Paris (0.072), Regal Ulixes (0.064) ⚠ PAPER_ONLY_NO_INTENT

### 17:25 Worcester — CopyBet Overnight Best Odds Guaranteed Handicap Hu **[SUPPRESS]**
- Runners: 11 | Passport: 11/11
- **Lane A (operational):** Prince De Juilley (0.136), Impecunious (0.113), Eaton Anne (0.111)
- **Lane B (paper):** Impecunious (0.121), Eaton Anne (0.118), Peter's Last Deal (0.111) ⚠ PAPER_ONLY_NO_INTENT

### 17:35 Lingfield — attheraces.com/marketmovers Handicap **[NO_EDGE]**
- Runners: 6 | Passport: 6/6
- **Lane A (operational):** Birthday Angel (0.220), A Major Payne (0.208), Bintkend (0.174)
- **Lane B (paper):** Birthday Angel (0.159), A Major Payne (0.165), Bintkend (0.161) ⚠ PAPER_ONLY_NO_INTENT

### 17:40 Hexham — Marrill Group Stamping Futures Handicap Chase **[NO_EDGE]**
- Runners: 9 | Passport: 9/9
- **Lane A (operational):** Out On Her Own (0.144), Dream Jet (0.139), Conquer The Breeze (0.136)
- **Lane B (paper):** Out On Her Own (0.118), Dream Jet (0.149), Conquer The Breeze (0.145) ⚠ PAPER_ONLY_NO_INTENT

### 17:47 Chepstow — LSL Racing Horse Sales Syndication Leasing/EBF Res **[NO_EDGE]**
- Runners: 9 | Passport: 9/9
- **Lane A (operational):** My Maria (0.147), Penny Capri (0.114), Miss Moneypit (0.102)
- **Lane B (paper):** My Maria (0.135), Penny Capri (0.107), Angels Lane (0.100) ⚠ PAPER_ONLY_NO_INTENT

### 17:55 Epsom — JRA Tokyo Trophy Handicap **[SUPPRESS]**
- Runners: 16 | Passport: 16/16
- **Lane A (operational):** Fine Interview (0.087), Gold Star Hero (0.082), Sondad (0.074)
- **Lane B (paper):** Fine Interview (0.083), Gold Star Hero (0.066), Sondad (0.065) ⚠ PAPER_ONLY_NO_INTENT

### 18:05 Lingfield — Buy A Share At daretodreamracing.co.uk Handicap **[NO_EDGE]**
- Runners: 7 | Passport: 7/7
- **Lane A (operational):** Rajendra (0.187), Royal Bodyguard (0.178), Sovereign Bay (0.168)
- **Lane B (paper):** Rajendra (0.197), Royal Bodyguard (0.138), Fans Favourite (0.145) ⚠ PAPER_ONLY_NO_INTENT

### 18:10 Hexham — Hexham Racecourse Holiday Home & Caravan Park Hand **[NO_EDGE]**
- Runners: 9 | Passport: 9/9
- **Lane A (operational):** Giovanni Change (0.131), Always Busy (0.119), Sir Carnegie (0.118)
- **Lane B (paper):** Giovanni Change (0.114), Always Busy (0.115), Lakefield Flyer (0.100) ⚠ PAPER_ONLY_NO_INTENT

### 18:20 Chepstow — Capital Windscreens Supporting Breast Cancer Handi **[NO_EDGE]**
- Runners: 7 | Passport: 7/7
- **Lane A (operational):** Ebn Sabt (0.178), Aigeas (0.178), Poetry Of Time (0.177)
- **Lane B (paper):** Ebn Sabt (0.176), Aigeas (0.168), Poetry Of Time (0.144) ⚠ PAPER_ONLY_NO_INTENT

### 18:35 Lingfield — Free Bets On attheraces.com Restricted Maiden Stak **[SUPPRESS]**
- Runners: 9 | Passport: 9/9
- **Lane A (operational):** Cold Fish (0.129), Relentless Hero (0.119), Fabled Spirit (0.115)
- **Lane B (paper):** Relentless Hero (0.111), Fabled Spirit (0.108), Liberate (0.102) ⚠ PAPER_ONLY_NO_INTENT

### 18:43 Hexham — ogledigital.co.uk Google Ads Tailed Off Too? Handi **[FRAME_TRUST]**
- Runners: 6 | Passport: 6/6
- **Lane A (operational):** Freddy Robinson (0.181), Two Auld Pals (0.145), Glory And Honour (0.127)
- **Lane B (paper):** Freddy Robinson (0.185), Two Auld Pals (0.104), Glory And Honour (0.122) ⚠ PAPER_ONLY_NO_INTENT

### 18:53 Chepstow — Late Arron James Supporting Pancreatic Cancer Hand **[NO_EDGE]**
- Runners: 10 | Passport: 10/10
- **Lane A (operational):** Dapper Gee Gee (0.137), Kisskodi (0.124), Slipper Time (0.123)
- **Lane B (paper):** Kisskodi (0.120), Slipper Time (0.107), This Farh (0.112) ⚠ PAPER_ONLY_NO_INTENT

### 19:05 Lingfield — Free Race Replays On attheraces.com Handicap **[WIN_TRUST]**
- Runners: 3 | Passport: 3/3
- **Lane A (operational):** Zoustar Dreams (0.424), Rosieisme Darling (0.344), My Mate Mackley (0.281)
- **Lane B (paper):** Zoustar Dreams (0.340), Rosieisme Darling (0.246), My Mate Mackley (0.122) ⚠ PAPER_ONLY_NO_INTENT

### 19:13 Hexham — Tricia Hughes Memorial Handicap Hurdle **[NO_EDGE]**
- Runners: 6 | Passport: 6/6
- **Lane A (operational):** Dinons (0.144), Abbey Scope (0.138), Ebselysees (0.128)
- **Lane B (paper):** Dinons (0.121), Abbey Scope (0.117), Stylish Recruit (0.122) ⚠ PAPER_ONLY_NO_INTENT

### 19:25 Chepstow — V3 UK- Principal Contractor Handicap (Chepstow Mil **[NO_EDGE]**
- Runners: 8 | Passport: 8/8
- **Lane A (operational):** Fifty Sent (0.144), Judge Frank (0.144), Saturnalia (0.124)
- **Lane B (paper):** Fifty Sent (0.122), Judge Frank (0.125), Saturnalia (0.109) ⚠ PAPER_ONLY_NO_INTENT

### 19:40 Lingfield — Free Tips On attheraces.com Restricted Maiden Stak **[SUPPRESS]**
- Runners: 13 | Passport: 13/13
- **Lane A (operational):** Show Me Gold (0.113), Dovecote (0.101), Turton (0.077)
- **Lane B (paper):** Show Me Gold (0.081), Dovecote (0.097), Turton (0.073) ⚠ PAPER_ONLY_NO_INTENT

### 20:10 Lingfield — Eikon Helping Young People In Surrey Handicap **[NO_EDGE]**
- Runners: 8 | Passport: 8/8
- **Lane A (operational):** Monsieur Kodi (0.171), Raffles Angel (0.157), Pixie Diva (0.151)
- **Lane B (paper):** Raffles Angel (0.146), Pixie Diva (0.137), Charlie Mason (0.141) ⚠ PAPER_ONLY_NO_INTENT

### 20:25 Chepstow — Capital Windscreens Supporting Autistic Society Ha **[NO_EDGE]**
- Runners: 11 | Passport: 11/11
- **Lane A (operational):** Be An Angel (0.124), Autumn Angel (0.124), Too Much Trevor (0.101)
- **Lane B (paper):** Be An Angel (0.112), Autumn Angel (0.095), Too Much Trevor (0.088) ⚠ PAPER_ONLY_NO_INTENT

### 20:40 Lingfield — Sky Sports Racing Virgin 512 Handicap **[NO_EDGE]**
- Runners: 8 | Passport: 8/8
- **Lane A (operational):** No Gain (0.156), Beau Jardine (0.120), Drafted (0.119)
- **Lane B (paper):** No Gain (0.121), Drafted (0.100), Kessaar Power (0.107) ⚠ PAPER_ONLY_NO_INTENT

### 21:00 Chepstow — Capital Windscreens Supporting Mental Health Handi **[NO_EDGE]**
- Runners: 9 | Passport: 9/9
- **Lane A (operational):** Electric Bass (0.164), Rosco Rogers (0.150), Cloudside Rock (0.129)
- **Lane B (paper):** Electric Bass (0.139), Rosco Rogers (0.132), Marinakis (0.104) ⚠ PAPER_ONLY_NO_INTENT

## Boundaries
- Paper-only intelligence. No betting instruction.
- No Telegram, staking, live scoring table writes, or official-pick override.
- Old Live VÉLØ and Shadow VÉLØ untouched.
- RPR archive-only. No SP in morning model. No JTC-D all-time sidecar.