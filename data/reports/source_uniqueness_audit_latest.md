# Source Uniqueness Audit

- Scoring impact: `NONE`

## RP-Only Fields

- owner
- sire / dam / dam sire
- entries
- quotes
- sales / notes when captured
- headgear / wind surgery
- newspaper comment
- tip count
- RP RPR archive-only

## Racing API-Only Fields

- structured race/runner/horse IDs where available
- course/distance/connection shadow analysis fields where present in VÉLØ verdict artifacts

## VÉLØ-Created Fields

- velo_prime_prob
- SQPE
- MDS
- improvement_score
- tier / product / router decision
- RPDC lookup state when attached

## Dangerous / Leakage-Prone Fields

- RPR
- same-race RP ratings
- RP comments if treated as truth
- tip count if treated as winner signal rather than public heat

## Recommendation

Keep RP as archive/context. Promote only after shadow evidence, leakage audit, and operator approval.
