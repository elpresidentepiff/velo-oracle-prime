# Human Intent Intelligence Entry: Daryl Jacob Jump Jockey Profile

**Captured:** 2026-06-04T22:29:43-07:00  
**Source Type:** jockey profile / documentary transcript supplied by operator  
**Authority:** CANDIDATE_ONLY  
**Model Fuel:** NO  
**Staking / Telegram / Betfair Authority:** NONE  

## Raw Source Summary

The supplied transcript follows Daryl Jacob through the jump-racing ecosystem: retained-owner relationships, target-race planning, schooling, travel, weight pressure, injury risk, emotional load, Cheltenham/Grand National ambition, and the psychology of winning and losing.

This entry is stored as a mechanism extract, not as a verbatim transcript.

## Named People / Organisations

| Name | Role / Signal Context |
|---|---|
| Daryl Jacob | Jump jockey; central subject. |
| Simon Munir | Retaining owner; double green colours. |
| Isaac Souede | Retaining owner; double green colours. |
| Anthony Bromley | Race manager; described as a key buyer/planner. |
| Nigel Twiston-Davies | Trainer context for individual rides/horses. |
| Nicky Henderson | Trainer context for Cheltenham/top horses. |
| Paul Nicholls | Trainer context from earlier Cheltenham winners. |
| Robert Alner | Major career mentor/trainer figure. |
| Sally Alner | Support/mentor figure in early career. |
| Kieran Kelly | Late mentor/friend; emotional driver and career-origin signal. |
| Kelly Jacob | Family support context; jockey lifestyle strain. |

## Named Horses / Race Context

| Horse | Context Extracted |
|---|---|
| Bristol De Mai | Grand National / Cheltenham target discussion; ground-dependent Gold Cup vs Ryanair path. |
| Neptune Collonges | 2012 Grand National winner; jockey knew horse better than market price implied. |
| Muratello | Example of one-ride day, beaten third, losing/expectation context. |
| Top Notch | Career momentum horse; Cheltenham near-miss context. |
| Call Me Lord | Hot favourite beaten; Cheltenham-prep confidence dent. |
| Kel Destan | Beat Call Me Lord; illustrates trial-race CV impact. |
| The Conditional | Cheltenham handicap near-miss; strong ride but second-place psychology. |
| Concertista | Major retained-owner Cheltenham winner; "last bullet" pressure and emotional release. |
| The Listener | Career-making ride; front-running / confidence building. |
| Reve De Sivola | Career-sustaining Grade 1 horse. |
| Zarkandar | Cheltenham winner context. |
| Lac Fontana | Cheltenham winner context. |
| Port Melon | Pre-race accident / injury risk context. |

## Mechanism Extracts

### 1. Retained-Owner Ecosystem

Observation: The jockey described a tight team with retaining owners and a race manager. Trust, confidence, and ride allocation are part of the edge.

Inference: Retained jockey + retained owner + race manager can indicate long-range placement intent. This is not the same as a generic jockey booking.

Candidate Tag: `RETAINED_OWNER_SIGNAL`

### 2. Race Targeting Is Conditional, Not Linear

Observation: Bristol De Mai was discussed as a possible Grand National candidate after Cheltenham, with Gold Cup vs Ryanair dependent on ground.

Inference: Target plans are dynamic. A stated target can be real, but the actual race chosen may pivot on ground, weight, and how the horse exits its prior race.

Candidate Tags: `TARGET_RACE_PATH`, `GROUND_DEPENDENT_INTENT`, `BIG_RACE_DREAM`

### 3. Home Knowledge Beats Market Price In Some Cases

Observation: Jacob said he never felt Neptune Collonges was truly a 33-1 shot because of what he knew from riding/understanding the horse.

Inference: Jockey/home-side knowledge can detect live chance not visible in public price. Market may underprice older or unfashionable horses if internal confidence remains.

Candidate Tags: `HOME_KNOWLEDGE_EDGE`, `MARKET_UNDERREAD`, `RHYTHM_JUMP_CONFIDENCE`

### 4. Jump Rhythm Is A Jockey-Specific Edge

Observation: Jacob repeatedly emphasised rhythm, jumping, and getting a horse travelling for him before thinking competitively.

Inference: For jump racing, jockey-horse rhythm and schooling compatibility may matter more than flat-form style metrics. A horse that jumps "for" a jockey may be a special relationship signal.

Candidate Tags: `JUMP_RHYTHM_EDGE`, `JOCKEY_HORSE_COMPATIBILITY`

### 5. Confidence Is Managed Like A Performance Asset

Observation: Anthony Bromley said top jockeys need reassurance more than people realise. Losing hot favourites leaves emotional damage; Cheltenham near-misses accumulate pressure.

Inference: Jockey confidence is a variable. Recent big-race seconds, hot-favourite defeats, or pressure to deliver in owner colours may alter risk tolerance and ride execution.

Candidate Tags: `JOCKEY_CONFIDENCE_STATE`, `BIG_STAGE_PRESSURE`, `RECENT_DEFEAT_DENT`

### 6. Ride Retention Creates Return-From-Injury Pressure

Observation: Jacob described wanting to return quickly after injury so other jockeys had fewer chances to win on "his" horses and take the rides.

Inference: Post-injury comeback timing may be driven by ride-retention incentives, not pure physical readiness. This may matter in assessing jockey fitness and decision sharpness.

Candidate Tags: `RIDE_RETENTION_PRESSURE`, `POST_INJURY_RETURN_RISK`

### 7. Weight Pressure Is A Hidden Performance Variable

Observation: The transcript describes low-weight targets, sweat suits, car heaters, missed meals, dehydration, and heavy travel for limited riding fees.

Inference: Low assigned weight can be a horse advantage but a jockey strain. The hidden question is whether the jockey is naturally comfortable at that weight or forced down hard.

Candidate Tags: `WEIGHT_CUT_STRESS`, `LOW_WEIGHT_HIDDEN_COST`, `JOCKEY_FATIGUE_RISK`

### 8. Travel Economics Can Distort Availability And Sharpness

Observation: Long travel, 70,000 miles a year, ferry trips, one-ride days, hotels, and late declarations are normal. Some rides may not be profitable after expenses.

Inference: A single ride after extreme travel should be interpreted with context. It may signal strong commitment if the jockey deliberately travels for one meaningful ride, or fatigue/noise if routine economics are poor.

Candidate Tags: `ONE_RIDE_COMMITMENT`, `LONG_TRAVEL_FATIGUE`, `DECLARATION_VOLATILITY`

### 9. Big Meetings Create Different Psychology

Observation: Cheltenham was described as the Olympics of the sport. A single winner can define a season; seconds are emotionally discounted.

Inference: Festival rides carry pressure and may change tactics. "Last realistic chance of the week" may intensify intent and risk appetite.

Candidate Tags: `FESTIVAL_PRESSURE`, `LAST_BULLET_RIDE`, `SEASON_DEFINING_TARGET`

### 10. Horse CV / Target Narrative Can Be Dented By Trial Defeat

Observation: Call Me Lord being beaten before Cheltenham was described as denting the horse's CV and making the festival picture less rosy.

Inference: Trial-race defeat can alter both internal confidence and public narrative. The aftermath may create either true downgrade or overreaction value depending on underlying excuse.

Candidate Tags: `TRIAL_DEFEAT_DENT`, `TARGET_CONFIDENCE_SHIFT`, `PUBLIC_NARRATIVE_RESET`

## Candidate Feature Ideas

These are hypotheses only:

| Candidate Signal | Description | Authority |
|---|---|---|
| `retained_owner_jockey_alignment` | Same jockey retained by owner/race manager on target horse. | CANDIDATE_ONLY |
| `one_ride_commitment_flag` | Jockey travels for one ride, especially outside local circuit. | CANDIDATE_ONLY |
| `low_weight_cut_risk` | Jockey asked to ride materially below natural/typical weight. | CANDIDATE_ONLY |
| `festival_pressure_state` | Jockey has major meeting pressure, near-miss streak, or last realistic bullet. | CANDIDATE_ONLY |
| `jockey_horse_rhythm_history` | Evidence that jockey schools/rides horse at home and understands rhythm/jumping. | CANDIDATE_ONLY |
| `post_injury_return_pressure` | Jockey returning quickly after fall/injury to protect ride book. | CANDIDATE_ONLY |
| `ground_dependent_target_switch` | Public target depends on going/race conditions. | CANDIDATE_ONLY |

## Control Notes

- Do not use this entry as a positive or negative rating.
- Do not attach it to Passport.
- Do not let market price validate or invalidate the human mechanism by itself.
- Use only as raw material for a later Human Intent taxonomy.
- Any future rail must be forward-tested and compared against existing VELO/New Build outputs.

## Working Doctrine Learned

The market sees the price. The people inside the game manage pressure, timing, confidence, weight, rhythm, ownership politics, and career survival. Those forces can explain why a horse is being prepared, protected, hidden, pushed, or abandoned.
