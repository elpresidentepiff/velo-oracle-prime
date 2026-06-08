# Race Day Two-Lane Readiness: 2026-06-08
Generated: 2026-06-08T00:40:33.811708Z

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

## Race Day Scorecards — 2026-06-08
_35 races, 369 runners_

### 13:30 Leicester — Heather Small Live @LeicesterRaces Saturday 4th Ju **[NO_EDGE]**
- Runners: 7 | Passport: 2/7 ⚠ WEAK_DATA
- **Lane A (operational):** Heart Sign (0.158), Bradbury (0.136), Adores (0.132)
- **Lane B (paper):** Heart Sign (0.164), Adores (0.123), Too Darn Spicy (0.121) ⚠ PAPER_ONLY_NO_INTENT

### 14:00 Leicester — Go West Live @LeicesterRaces Saturday 4th July Res **[LOW_DATA]**
- Runners: 10 | Passport: 0/10 ⚠ WEAK_DATA
- **Lane A (operational):** Kach Above (0.104), Waiting For Archie (0.103), Better Nature (0.102)
- **Lane B (paper):** Kach Above (0.094), Waiting For Archie (0.094), Better Nature (0.093) ⚠ PAPER_ONLY_NO_INTENT

### 14:15 Carlisle — Racing TV Apprentice Handicap **[NO_EDGE]**
- Runners: 9 | Passport: 9/9
- **Lane A (operational):** Stirrup Cup (0.116), Baba Reza (0.108), Coconut Bay (0.103)
- **Lane B (paper):** Stirrup Cup (0.112), Baba Reza (0.092), Coconut Bay (0.093) ⚠ PAPER_ONLY_NO_INTENT

### 14:45 Carlisle — British Stallion Studs EBF Novice Stakes (GBB Race **[WIN_TRUST]**
- Runners: 4 | Passport: 2/4 ⚠ WEAK_DATA
- **Lane A (operational):** Capilano (0.347), Deputy Vice (0.297), Caeruleus (0.211)
- **Lane B (paper):** Capilano (0.237), Deputy Vice (0.218), Caeruleus (0.194) ⚠ PAPER_ONLY_NO_INTENT

### 15:00 Leicester — Racing Again This Saturday Evening 13th June Restr **[FRAME_TRUST]**
- Runners: 4 | Passport: 2/4 ⚠ WEAK_DATA
- **Lane A (operational):** Vichenza (0.290), Heddon Street (0.216), Muchacho (0.211)
- **Lane B (paper):** Vichenza (0.217), Heddon Street (0.192), Jellystone Park (0.197) ⚠ PAPER_ONLY_NO_INTENT

### 15:15 Carlisle — Carlisle Racecourse Supporting IJF Beneficiaries M **[LOW_DATA]**
- Runners: 7 | Passport: 2/7 ⚠ WEAK_DATA
- **Lane A (operational):** Marhayb (0.131), Midnight Serenade (0.131), Always Blue (0.130)
- **Lane B (paper):** Marhayb (0.123), Midnight Serenade (0.123), Always Blue (0.122) ⚠ PAPER_ONLY_NO_INTENT

### 15:30 Leicester — DSK Environmental Handicap **[NO_EDGE]**
- Runners: 8 | Passport: 6/8 ⚠ WEAK_DATA
- **Lane A (operational):** Enter Sandman (0.195), Davorge Nation (0.124), Love Alive (0.120)
- **Lane B (paper):** Enter Sandman (0.131), Davorge Nation (0.123), Love Alive (0.120) ⚠ PAPER_ONLY_NO_INTENT

### 15:45 Carlisle — Watch Racing TV Live Handicap **[NO_EDGE]**
- Runners: 11 | Passport: 7/11 ⚠ WEAK_DATA
- **Lane A (operational):** Auspicious (0.140), Battenburg Belle (0.101), Mereside Spark (0.101)
- **Lane B (paper):** Auspicious (0.108), Mereside Spark (0.091), Realistic Dream (0.086) ⚠ PAPER_ONLY_NO_INTENT

### 16:00 Leicester — Hugh James Classified Stakes **[SUPPRESS]**
- Runners: 13 | Passport: 9/13 ⚠ WEAK_DATA
- **Lane A (operational):** Tilsworth Max (0.096), Eulalia (0.092), Shark Two One (0.089)
- **Lane B (paper):** Tilsworth Max (0.076), Eulalia (0.082), Shark Two One (0.073) ⚠ PAPER_ONLY_NO_INTENT

### 16:18 Carlisle — Every Race Live On Racing TV Fillies' Handicap **[NO_EDGE]**
- Runners: 9 | Passport: 8/9 ⚠ WEAK_DATA
- **Lane A (operational):** Epidavros (0.139), Ravishing Beauty (0.118), We've Got This (0.117)
- **Lane B (paper):** Epidavros (0.131), We've Got This (0.115), Positive Thoughts (0.117) ⚠ PAPER_ONLY_NO_INTENT

### 16:35 Leicester — Mesothelioma UK Handicap (GBBplus Race) **[SUPPRESS]**
- Runners: 11 | Passport: 11/11
- **Lane A (operational):** Zatsgood (0.130), Percy's Daydream (0.124), Noble Horizon (0.121)
- **Lane B (paper):** Zatsgood (0.100), Noble Horizon (0.127), Double Red (0.120) ⚠ PAPER_ONLY_NO_INTENT

### 16:43 Roscommon — Garvey's Bar, Ballintubber Maiden Hurdle **[NO_EDGE]**
- Runners: 14 | Passport: 6/14 ⚠ WEAK_DATA
- **Lane A (operational):** Ritz Plan (0.144), Cinating (0.104), Teffian Warrior (0.091)
- **Lane B (paper):** Ritz Plan (0.109), Cinating (0.090), Teffian Warrior (0.093) ⚠ PAPER_ONLY_NO_INTENT

### 16:53 Carlisle — Follow Racing TV On X Handicap **[NO_EDGE]**
- Runners: 13 | Passport: 13/13
- **Lane A (operational):** Amancio (0.138), Krissy (0.126), Titainium (0.111)
- **Lane B (paper):** Amancio (0.111), Krissy (0.088), Concert Boy (0.089) ⚠ PAPER_ONLY_NO_INTENT

### 17:04 Windsor — Royal Jersey Laundry Clean Sweep Handicap **[NO_EDGE]**
- Runners: 12 | Passport: 9/12 ⚠ WEAK_DATA
- **Lane A (operational):** Charlie Boyo (0.148), Woolisle (0.120), Exhibitioning (0.116)
- **Lane B (paper):** Charlie Boyo (0.155), Exhibitioning (0.094), Unionville (0.099) ⚠ PAPER_ONLY_NO_INTENT

### 17:10 Leicester — Smooth FM Ladies' Day Saturday 4th July Book Now C **[NO_EDGE]**
- Runners: 9 | Passport: 8/9 ⚠ WEAK_DATA
- **Lane A (operational):** Antiphon (0.186), Dreambird Dolly (0.113), Rohini (0.102)
- **Lane B (paper):** Antiphon (0.142), Dreambird Dolly (0.095), A Lott Of Kane (0.102) ⚠ PAPER_ONLY_NO_INTENT

### 17:18 Roscommon — McNulty Furniture Rated Novice Hurdle **[WIN_TRUST]**
- Runners: 3 | Passport: 3/3
- **Lane A (operational):** Chanceawetmorning (0.394), Polepatrick (0.231), Berto Ramirez (0.218)
- **Lane B (paper):** Chanceawetmorning (0.243), Polepatrick (0.181), Berto Ramirez (0.127) ⚠ PAPER_ONLY_NO_INTENT

### 17:28 Carlisle — Join Racing TV Now Handicap **[SUPPRESS]**
- Runners: 10 | Passport: 10/10
- **Lane A (operational):** Ideal Guest (0.126), Albeyours (0.123), Orbital Chime (0.109)
- **Lane B (paper):** Albeyours (0.101), Orbital Chime (0.105), Rwenearlytheredad (0.100) ⚠ PAPER_ONLY_NO_INTENT

### 17:39 Windsor — O'Malley EBF Fillies' Novice Stakes (GBB Race) **[LOW_DATA]**
- Runners: 12 | Passport: 3/12 ⚠ WEAK_DATA
- **Lane A (operational):** Desert Symphony (0.086), Starburster (0.084), Glorious Game (0.082)
- **Lane B (paper):** Desert Symphony (0.078), Starburster (0.078), Spirit Of Glory (0.080) ⚠ PAPER_ONLY_NO_INTENT

### 17:48 Roscommon — Dermot Hughes Car Sales Handicap Hurdle **[NO_EDGE]**
- Runners: 11 | Passport: 10/11 ⚠ WEAK_DATA
- **Lane A (operational):** Stede Bonnet (0.144), Avalo (0.108), Rakki (0.104)
- **Lane B (paper):** Stede Bonnet (0.135), Rakki (0.106), Sir Allen (0.088) ⚠ PAPER_ONLY_NO_INTENT

### 18:09 Windsor — Hunter Plant Hire/MC International Novice Stakes ( **[NO_EDGE]**
- Runners: 11 | Passport: 3/11 ⚠ WEAK_DATA
- **Lane A (operational):** Storming Point (0.147), Screen Actor (0.090), Paean Of Appin (0.088)
- **Lane B (paper):** Storming Point (0.112), Screen Actor (0.084), Minerality (0.088) ⚠ PAPER_ONLY_NO_INTENT

### 18:18 Roscommon — McGowan Accountancy Services Novice Chase **[NO_EDGE]**
- Runners: 8 | Passport: 8/8
- **Lane A (operational):** Bannow Blaze (0.199), Workahead (0.152), Reiki Revolution (0.152)
- **Lane B (paper):** Bannow Blaze (0.161), Workahead (0.099), Reiki Revolution (0.127) ⚠ PAPER_ONLY_NO_INTENT

### 18:30 Pontefract — Napoleons Casino Bradford Apprentice Handicap (App **[NO_EDGE]**
- Runners: 7 | Passport: 7/7
- **Lane A (operational):** Reidh (0.195), Forever Noah (0.167), Knicks (0.161)
- **Lane B (paper):** Reidh (0.191), Forever Noah (0.139), Knicks (0.168) ⚠ PAPER_ONLY_NO_INTENT

### 18:48 Roscommon — Bet With Tote.ie On Racing & Sports Connacht Natio **[SUPPRESS]**
- Runners: 19 | Passport: 19/19
- **Lane A (operational):** Rocky's Howya (0.078), Rocky's Diamond (0.076), Boston Rover (0.060)
- **Lane B (paper):** Rocky's Howya (0.064), Rocky's Diamond (0.107), Where's My Jet (0.062) ⚠ PAPER_ONLY_NO_INTENT

### 19:00 Pontefract — Racing TV EBF Restricted Maiden Fillies' Stakes (B **[SUPPRESS]**
- Runners: 11 | Passport: 2/11 ⚠ WEAK_DATA
- **Lane A (operational):** Khazamh (0.101), Fern Clyde (0.100), Cousin Rachel (0.090)
- **Lane B (paper):** Khazamh (0.095), Cousin Rachel (0.083), Bayside Way (0.085) ⚠ PAPER_ONLY_NO_INTENT

### 19:09 Windsor — Install Electrical Contractors Limited Novice Stak **[LOW_DATA]**
- Runners: 16 | Passport: 9/16 ⚠ WEAK_DATA
- **Lane A (operational):** Virtue Diligence (0.072), Cuff It (0.066), Zynak (0.066)
- **Lane B (paper):** Virtue Diligence (0.066), Zynak (0.062), Phantom Recon (0.064) ⚠ PAPER_ONLY_NO_INTENT

### 19:18 Roscommon — Sweeney Oil Handicap Chase **[SUPPRESS]**
- Runners: 14 | Passport: 14/14
- **Lane A (operational):** Stoneyford Lady (0.086), Keep On Dreaming (0.077), Piccolo Player (0.074)
- **Lane B (paper):** Stoneyford Lady (0.067), Keep On Dreaming (0.073), Piccolo Player (0.065) ⚠ PAPER_ONLY_NO_INTENT

### 19:30 Pontefract — Fathers Day Family Day Sunday 21st June Handicap ( **[FRAME_TRUST]**
- Runners: 5 | Passport: 5/5
- **Lane A (operational):** Analogical (0.271), Aulis (0.268), Say What You See (0.256)
- **Lane B (paper):** Analogical (0.211), Say What You See (0.210), Raulin (0.209) ⚠ PAPER_ONLY_NO_INTENT

### 19:39 Windsor — Fitzdares Sprint Series Handicap (Windsor Sprint S **[NO_EDGE]**
- Runners: 9 | Passport: 8/9 ⚠ WEAK_DATA
- **Lane A (operational):** Society Kiss (0.170), Clearpoint (0.142), Trefor (0.112)
- **Lane B (paper):** Society Kiss (0.162), Clearpoint (0.113), Trefor (0.113) ⚠ PAPER_ONLY_NO_INTENT

### 19:48 Roscommon — Roscommon (Q.R.) Handicap Chase **[SUPPRESS]**
- Runners: 19 | Passport: 19/19
- **Lane A (operational):** Ballingurteen (0.078), Finnicky Filly (0.056), Silent Flight (0.056)
- **Lane B (paper):** Finnicky Filly (0.050), Global Assembly (0.053), Jouster (0.050) ⚠ PAPER_ONLY_NO_INTENT

### 20:00 Pontefract — Tony Bethell Memorial Handicap **[NO_EDGE]**
- Runners: 12 | Passport: 12/12
- **Lane A (operational):** Rupert The Prince (0.148), Angelardo (0.116), Zimmerman (0.105)
- **Lane B (paper):** Rupert The Prince (0.123), Angelardo (0.097), Zimmerman (0.085) ⚠ PAPER_ONLY_NO_INTENT

### 20:09 Windsor — Heat Your Home With Alpha Classified Stakes **[SUPPRESS]**
- Runners: 16 | Passport: 13/16 ⚠ WEAK_DATA
- **Lane A (operational):** Qaaeadd (0.090), Dubai Harbour (0.084), Clough (0.076)
- **Lane B (paper):** Qaaeadd (0.070), Clough (0.067), Nymphaea (0.071) ⚠ PAPER_ONLY_NO_INTENT

### 20:18 Roscommon — Roscommon Livestock Mart (Pro/Am) INH Flat Race **[LOW_DATA]**
- Runners: 9 | Passport: 0/9 ⚠ WEAK_DATA
- **Lane A (operational):** Linford (0.163), Hilly Filly (0.123), Tell The Boys (0.122)
- **Lane B (paper):** Linford (0.152), Tell The Boys (0.110), Skylab (0.110) ⚠ PAPER_ONLY_NO_INTENT

### 20:30 Pontefract — Bill Carrigill Memorial Handicap **[SUPPRESS]**
- Runners: 12 | Passport: 12/12
- **Lane A (operational):** Shimmering Sands (0.096), Off Spin (0.090), Nanny Park (0.089)
- **Lane B (paper):** Shimmering Sands (0.086), Off Spin (0.077), Falcon Nine (0.077) ⚠ PAPER_ONLY_NO_INTENT

### 20:39 Windsor — Network Airline Services Handicap **[SUPPRESS]**
- Runners: 14 | Passport: 9/14 ⚠ WEAK_DATA
- **Lane A (operational):** Diamond Ali (0.103), Starakova (0.089), Blue Jammin (0.085)
- **Lane B (paper):** Diamond Ali (0.083), Heated Moment (0.072), My Old Mate (0.081) ⚠ PAPER_ONLY_NO_INTENT

### 21:00 Pontefract — Mr Wolf Sprint Handicap **[NO_EDGE]**
- Runners: 10 | Passport: 10/10
- **Lane A (operational):** Emperor's Son (0.164), Call Me Betty (0.114), Veydari (0.112)
- **Lane B (paper):** Emperor's Son (0.141), Call Me Betty (0.101), Dicko The Legend (0.101) ⚠ PAPER_ONLY_NO_INTENT

## Boundaries
- Paper-only intelligence. No betting instruction.
- No Telegram, staking, live scoring table writes, or official-pick override.
- Old Live VÉLØ and Shadow VÉLØ untouched.
- RPR archive-only. No SP in morning model. No JTC-D all-time sidecar.