# Race Day Two-Lane Readiness: 2026-06-03
Generated: 2026-06-03T12:42:23.043795Z

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

## Race Day Scorecards — 2026-06-03
_43 races, 455 runners_

### 11:40 Happy Valley — Mount Butler Handicap (Class 5) (Course C) (Turf) **[SUPPRESS]**
- Runners: 14 | Passport: 14/14
- **Lane A (operational):** Family Fortune (0.116), Wah May Wai Wai (0.102), Telecom Power (0.089)
- **Lane B (paper):** Family Fortune (0.093), Wah May Wai Wai (0.082), Telecom Power (0.067) ⚠ PAPER_ONLY_NO_INTENT

### 12:10 Happy Valley — Mount Nicholson Handicap (Class 5) (Course C) (Tur **[NO_EDGE]**
- Runners: 14 | Passport: 14/14
- **Lane A (operational):** Always My Folks (0.148), Majestic Delight (0.125), Double Bingo (0.100)
- **Lane B (paper):** Always My Folks (0.117), Majestic Delight (0.088), Thousand Cups (0.085) ⚠ PAPER_ONLY_NO_INTENT

### 12:40 Happy Valley — Wong Nai Chung Gap Handicap (Class 4) (Course C) ( **[SUPPRESS]**
- Runners: 14 | Passport: 14/14
- **Lane A (operational):** Leading Agility (0.109), Free Pony (0.105), Young Arrow (0.078)
- **Lane B (paper):** Leading Agility (0.076), Free Pony (0.080), Victor The Rapid (0.063) ⚠ PAPER_ONLY_NO_INTENT

### 13:10 Happy Valley — Middle Gap Handicap (Class 4) (Course C) (Turf) **[NO_EDGE]**
- Runners: 14 | Passport: 14/14
- **Lane A (operational):** Run Run Timing (0.183), Dashing Maurison (0.117), Take Action (0.114)
- **Lane B (paper):** Run Run Timing (0.122), Take Action (0.092), Exceed The Limit (0.082) ⚠ PAPER_ONLY_NO_INTENT

### 13:40 Happy Valley — Cricket Club Valley Stakes Handicap (Class 4) (Cou **[NO_EDGE]**
- Runners: 14 | Passport: 14/14
- **Lane A (operational):** Georgian Sigma (0.155), Brownneedsfurther (0.141), Flashing Fighter (0.133)
- **Lane B (paper):** Georgian Sigma (0.117), Brownneedsfurther (0.102), Flashing Fighter (0.116) ⚠ PAPER_ONLY_NO_INTENT

### 14:10 Happy Valley — Wong Nai Chung Gap Handicap (Class 4) (Course C) ( **[SUPPRESS]**
- Runners: 14 | Passport: 14/14
- **Lane A (operational):** The Heir (0.154), Vigor Eye (0.146), Meowth (0.138)
- **Lane B (paper):** Vigor Eye (0.121), Meowth (0.118), Bits Superstar (0.106) ⚠ PAPER_ONLY_NO_INTENT

### 14:30 Newton Abbot — Sun Racing Free Tickets With Sun Club Maiden Hurdl **[NO_EDGE]**
- Runners: 9 | Passport: 9/9
- **Lane A (operational):** River Don (0.160), Tiger Rouge (0.109), Premier Fantasy (0.103)
- **Lane B (paper):** River Don (0.148), Tiger Rouge (0.116), French Diablo (0.107) ⚠ PAPER_ONLY_NO_INTENT

### 14:45 Happy Valley — Shouson Hill Handicap (Class 3) (Course C) (Turf) **[NO_EDGE]**
- Runners: 14 | Passport: 14/14
- **Lane A (operational):** Happy Index (0.123), Amazing Kid (0.117), Ace Champion (0.103)
- **Lane B (paper):** Happy Index (0.106), Greater Bae (0.102), Dancing Classics (0.100) ⚠ PAPER_ONLY_NO_INTENT

### 14:48 Nottingham — £9 Racedays At Nottingham Racecourse Novice Stakes **[NO_EDGE]**
- Runners: 12 | Passport: 12/12
- **Lane A (operational):** Menhaal (0.146), True Charm (0.144), The Ginger Kid (0.141)
- **Lane B (paper):** Menhaal (0.140), The Ginger Kid (0.127), Le Grand Etoile (0.118) ⚠ PAPER_ONLY_NO_INTENT

### 15:00 Newton Abbot — Edmundson Electrical Torquay Novices' Handicap Cha **[WIN_TRUST]**
- Runners: 4 | Passport: 4/4
- **Lane A (operational):** Doc McCoy (0.255), Dunkerque (0.244), Franigane (0.211)
- **Lane B (paper):** Doc McCoy (0.240), Dunkerque (0.237), Franigane (0.190) ⚠ PAPER_ONLY_NO_INTENT

### 15:15 Happy Valley — Tai Tam Gap Handicap (Class 2) (Course C) (Turf) **[NO_EDGE]**
- Runners: 11 | Passport: 11/11
- **Lane A (operational):** Beauty Alliance (0.144), Armor Golden Eagle (0.138), Silvery Breeze (0.113)
- **Lane B (paper):** Beauty Alliance (0.113), Silvery Breeze (0.094), Pocketing (0.100) ⚠ PAPER_ONLY_NO_INTENT

### 15:18 Nottingham — British Stallion Studs EBF Maiden Fillies' Stakes  **[SUPPRESS]**
- Runners: 10 | Passport: 10/10
- **Lane A (operational):** Fast Track (0.129), Halliwell Stream (0.124), Miss Tuite (0.123)
- **Lane B (paper):** Fast Track (0.098), Halliwell Stream (0.112), Senorita Bonita (0.093) ⚠ PAPER_ONLY_NO_INTENT

### 15:30 Newton Abbot — Par Inn Novices' Handicap Chase **[NO_EDGE]**
- Runners: 8 | Passport: 8/8
- **Lane A (operational):** It's A Breeze (0.132), Kenzo Des Bruyeres (0.124), Daring Plan (0.122)
- **Lane B (paper):** It's A Breeze (0.117), Kenzo Des Bruyeres (0.116), Ferando (0.099) ⚠ PAPER_ONLY_NO_INTENT

### 15:48 Nottingham — Wildwest Beer Festival 4th July Fillies' Handicap **[NO_EDGE]**
- Runners: 11 | Passport: 11/11
- **Lane A (operational):** Vitality (0.126), Bami (0.110), Lillie Margot (0.109)
- **Lane B (paper):** Vitality (0.112), Jamie Sommers (0.102), Glasgow Kiss (0.087) ⚠ PAPER_ONLY_NO_INTENT

### 15:50 Happy Valley — Violet Hill Handicap (Class 3) (Course C) (Turf) **[NO_EDGE]**
- Runners: 14 | Passport: 14/14
- **Lane A (operational):** Smart Avenue (0.129), Stormi (0.128), All Round Winner (0.121)
- **Lane B (paper):** Smart Avenue (0.110), All Round Winner (0.101), California Moxie (0.093) ⚠ PAPER_ONLY_NO_INTENT

### 16:00 Newton Abbot — Charles Darrow Mares' Handicap Hurdle **[SUPPRESS]**
- Runners: 5 | Passport: 5/5
- **Lane A (operational):** Queens Venture (0.196), Porter In The Park (0.177), Jena d'Oudairies (0.165)
- **Lane B (paper):** Queens Venture (0.257), Porter In The Park (0.165), Just A Memory (0.143) ⚠ PAPER_ONLY_NO_INTENT

### 16:18 Nottingham — Hospitality At Nottingham Racecourse Handicap **[NO_EDGE]**
- Runners: 10 | Passport: 10/10
- **Lane A (operational):** A Major Payne (0.155), Kasgani (0.122), Orangesandlemons (0.122)
- **Lane B (paper):** A Major Payne (0.120), Orangesandlemons (0.126), No Knee Never (0.118) ⚠ PAPER_ONLY_NO_INTENT

### 16:30 Newton Abbot — Clearance Handicap Hurdle **[WIN_TRUST]**
- Runners: 5 | Passport: 5/5
- **Lane A (operational):** Howth (0.296), Morning Mayhem (0.203), Centara (0.187)
- **Lane B (paper):** Howth (0.287), Morning Mayhem (0.182), Centara (0.205) ⚠ PAPER_ONLY_NO_INTENT

### 16:40 Curragh — Sky Bet Extra Places Handicap **[SUPPRESS]**
- Runners: 21 | Passport: 21/21
- **Lane A (operational):** Dawn Flame (0.073), Gonna Be Golden (0.072), Caitouna (0.056)
- **Lane B (paper):** Dawn Flame (0.050), Gonna Be Golden (0.056), Caitouna (0.057) ⚠ PAPER_ONLY_NO_INTENT

### 16:48 Nottingham — Watch RacingTV Handicap (GBBPlus Race) **[NO_EDGE]**
- Runners: 7 | Passport: 7/7
- **Lane A (operational):** Gatehouse (0.181), Midnight Rodeo (0.181), Unchartedterritory (0.164)
- **Lane B (paper):** Gatehouse (0.155), Midnight Rodeo (0.177), Unchartedterritory (0.168) ⚠ PAPER_ONLY_NO_INTENT

### 17:00 Newton Abbot — WestCountry Food Supplies Handicap Hurdle **[SUPPRESS]**
- Runners: 12 | Passport: 12/12
- **Lane A (operational):** Ugo Bingo (0.100), Westerton (0.097), Jukebox Annie (0.097)
- **Lane B (paper):** Westerton (0.087), Jukebox Annie (0.074), Zambezi Fix (0.095) ⚠ PAPER_ONLY_NO_INTENT

### 17:10 Curragh — TRI Equestrian Maiden **[SUPPRESS]**
- Runners: 18 | Passport: 18/18
- **Lane A (operational):** Highwayman (0.090), Quinta Girl (0.075), The Piper's Call (0.069)
- **Lane B (paper):** Highwayman (0.082), Quinta Girl (0.071), Trek Home (0.064) ⚠ PAPER_ONLY_NO_INTENT

### 17:18 Nottingham — Dine In Sherwoods Restaurant Handicap **[SUPPRESS]**
- Runners: 12 | Passport: 12/12
- **Lane A (operational):** Hint Of The Jungle (0.132), Rinky Tinky Tinky (0.109), May Encounter (0.101)
- **Lane B (paper):** Hint Of The Jungle (0.083), Rinky Tinky Tinky (0.102), May Encounter (0.088) ⚠ PAPER_ONLY_NO_INTENT

### 17:30 Newton Abbot — Visit Our Classic Car Show 6th June Open National  **[SUPPRESS]**
- Runners: 9 | Passport: 9/9
- **Lane A (operational):** Ocean Rose (0.098), Five Lanes (0.097), Winter Flight (0.096)
- **Lane B (paper):** Winter Flight (0.107), Mr Sunny (0.107), Thepassingtyphoon (0.107) ⚠ PAPER_ONLY_NO_INTENT

### 17:35 Saratoga — Beverly R. Steinman Hurdle Handicap (Grade 1) (Tur **[NO_EDGE]**
- Runners: 8 | Passport: 8/8
- **Lane A (operational):** Coutach (0.270), We're Back Again (0.144), Ziggle Pops (0.118)
- **Lane B (paper):** Coutach (0.162), We're Back Again (0.121), Little Trilby (0.108) ⚠ PAPER_ONLY_NO_INTENT

### 17:40 Curragh — Sky Bet Club Irish EBF Maiden **[NO_EDGE]**
- Runners: 7 | Passport: 7/7
- **Lane A (operational):** Selwyn (0.165), Peckedbytheparrott (0.124), Bull Shark (0.124)
- **Lane B (paper):** Selwyn (0.160), Breath Of Paradise (0.128), To Infinity (0.128) ⚠ PAPER_ONLY_NO_INTENT

### 18:00 Ripon — British Stallion Studs EBF Novice Stakes (GBB/IRE  **[FRAME_TRUST]**
- Runners: 7 | Passport: 7/7
- **Lane A (operational):** Fantasy Force (0.255), Spectacular Diver (0.191), Calef (0.136)
- **Lane B (paper):** Fantasy Force (0.186), Spectacular Diver (0.184), Calef (0.130) ⚠ PAPER_ONLY_NO_INTENT

### 18:10 Curragh — Pension Structures Irish EBF Maiden **[SUPPRESS]**
- Runners: 14 | Passport: 14/14
- **Lane A (operational):** Sirocco Sands (0.123), Tradewinds (0.100), Nation Blaze (0.087)
- **Lane B (paper):** Sirocco Sands (0.086), Tradewinds (0.091), Nation Blaze (0.086) ⚠ PAPER_ONLY_NO_INTENT

### 18:20 Warwick — EHB Residential Maiden Hurdle (GBB Race) **[FRAME_TRUST]**
- Runners: 7 | Passport: 7/7
- **Lane A (operational):** Garde My Guinness (0.205), Chambers (0.150), Lyric (0.143)
- **Lane B (paper):** Garde My Guinness (0.194), Lyric (0.151), Colibri Bleu (0.143) ⚠ PAPER_ONLY_NO_INTENT

### 18:35 Ripon — Book Online At ripon-races.co.uk Maiden Fillies' S **[WIN_TRUST]**
- Runners: 4 | Passport: 4/4
- **Lane A (operational):** Gone By (0.437), Golden Step (0.337), Joud (0.335)
- **Lane B (paper):** Gone By (0.358), Golden Step (0.244), Joud (0.244) ⚠ PAPER_ONLY_NO_INTENT

### 18:45 Curragh — Sky Bet Price Boosts Premier Handicap **[NO_EDGE]**
- Runners: 12 | Passport: 12/12
- **Lane A (operational):** Sparky Sparky (0.186), Cool Azul (0.157), Fox In Flight (0.145)
- **Lane B (paper):** Sparky Sparky (0.133), Cool Azul (0.132), Ipanema Queen (0.133) ⚠ PAPER_ONLY_NO_INTENT

### 18:55 Warwick — Insight Surveyors Handicap Hurdle **[NO_EDGE]**
- Runners: 9 | Passport: 9/9
- **Lane A (operational):** Baltray (0.134), Touchwoodexpress (0.125), Luna Run (0.116)
- **Lane B (paper):** Baltray (0.123), Touchwoodexpress (0.117), Tyson (0.109) ⚠ PAPER_ONLY_NO_INTENT

### 19:10 Ripon — Bishopton Equine Handicap **[SUPPRESS]**
- Runners: 14 | Passport: 14/14
- **Lane A (operational):** Travis (0.111), Perfidia (0.101), Jesmond Dawn (0.101)
- **Lane B (paper):** Travis (0.085), Avatar Jet (0.083), The Childe Of Hale (0.083) ⚠ PAPER_ONLY_NO_INTENT

### 19:20 Curragh — Sky Bet Race To The Ebor Handicap **[SUPPRESS]**
- Runners: 12 | Passport: 12/12
- **Lane A (operational):** Granite Bay (0.106), Factual Fact (0.102), Emit (0.099)
- **Lane B (paper):** Granite Bay (0.094), Emit (0.102), Yulia (0.101) ⚠ PAPER_ONLY_NO_INTENT

### 19:30 Warwick — Virtus Property Services Handicap Hurdle **[FRAME_TRUST]**
- Runners: 5 | Passport: 5/5
- **Lane A (operational):** Amatchmadeinheaven (0.201), Kentucky River (0.165), Modern Style (0.150)
- **Lane B (paper):** Amatchmadeinheaven (0.209), Kentucky River (0.197), Midnight View (0.123) ⚠ PAPER_ONLY_NO_INTENT

### 19:42 Ripon — weatherbysshop.co.uk Handicap **[SUPPRESS]**
- Runners: 13 | Passport: 13/13
- **Lane A (operational):** Raft Up (0.124), Men Of Honour (0.096), Keldeo (0.092)
- **Lane B (paper):** Raft Up (0.100), Men Of Honour (0.085), Keldeo (0.094) ⚠ PAPER_ONLY_NO_INTENT

### 19:55 Curragh — Try Racing TV For Free Now At racingtv.com/freetri **[NO_EDGE]**
- Runners: 9 | Passport: 9/9
- **Lane A (operational):** Pleased (0.180), Arrietty (0.135), I Hope You Dance (0.116)
- **Lane B (paper):** Pleased (0.141), Arrietty (0.110), Porters Corner (0.101) ⚠ PAPER_ONLY_NO_INTENT

### 20:00 Warwick — Rainier Developments Handicap Chase **[NO_EDGE]**
- Runners: 7 | Passport: 7/7
- **Lane A (operational):** Carpe Diem (0.170), Misteroddsocks (0.138), Knightsbridge (0.135)
- **Lane B (paper):** Carpe Diem (0.111), Knightsbridge (0.106), Northern Symphonie (0.121) ⚠ PAPER_ONLY_NO_INTENT

### 20:12 Ripon — Napoleons Casino And Restaurant Leeds Handicap **[NO_EDGE]**
- Runners: 8 | Passport: 8/8
- **Lane A (operational):** Betweenthesticks (0.175), Canaria Queen (0.143), Speeding Bullet (0.129)
- **Lane B (paper):** Betweenthesticks (0.146), Speeding Bullet (0.121), Azuinthejungle (0.112) ⚠ PAPER_ONLY_NO_INTENT

### 20:25 Curragh — Sky Bet Build A Bet Handicap **[SUPPRESS]**
- Runners: 23 | Passport: 23/23
- **Lane A (operational):** Salah Belle (0.072), Poweracclaim (0.067), Kitty Bear (0.067)
- **Lane B (paper):** Salah Belle (0.056), Poweracclaim (0.066), Jazzit (0.053) ⚠ PAPER_ONLY_NO_INTENT

### 20:30 Warwick — Stockton House Mares' Handicap Hurdle **[NO_EDGE]**
- Runners: 7 | Passport: 7/7
- **Lane A (operational):** Best Night (0.175), Northern Air (0.158), Blackwater Lilly (0.152)
- **Lane B (paper):** Best Night (0.207), Northern Air (0.181), Siorai (0.169) ⚠ PAPER_ONLY_NO_INTENT

### 20:42 Ripon — Ripon Theatre Festival 5th - 12th July Handicap **[NO_EDGE]**
- Runners: 8 | Passport: 8/8
- **Lane A (operational):** Karakula Dancer (0.202), Popty Ping (0.171), Talking In Kode (0.119)
- **Lane B (paper):** Karakula Dancer (0.159), Popty Ping (0.145), Deep Sleep (0.095) ⚠ PAPER_ONLY_NO_INTENT

### 21:00 Warwick — Taylor Wimpey Strategic Land Midlands Handicap Cha **[NO_EDGE]**
- Runners: 5 | Passport: 5/5
- **Lane A (operational):** Theonlywayiswessex (0.231), Therhythmofthenite (0.230), Royal Deeside (0.190)
- **Lane B (paper):** Theonlywayiswessex (0.252), Therhythmofthenite (0.266), Royal Deeside (0.165) ⚠ PAPER_ONLY_NO_INTENT

## Boundaries
- Paper-only intelligence. No betting instruction.
- No Telegram, staking, live scoring table writes, or official-pick override.
- Old Live VÉLØ and Shadow VÉLØ untouched.
- RPR archive-only. No SP in morning model. No JTC-D all-time sidecar.