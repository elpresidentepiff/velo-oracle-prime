# VÉLØ RP CLAIM EXTRACTOR — REGEX BASELINE

**Run at:** 2026-05-19T05:43:33.262484+00:00  
**Total records processed:** 1000  
**Sources:** Supabase horse_comments=1000, RP profile=0

---

## Claim Coverage

| Claim Type | Count | Coverage % |
|---|---|---|
| improvement_claim | 53 | 5.3% |
| handicap_claim | 58 | 5.8% |
| stable_intent_claim | 9 | 0.9% |
| trip_claim | 25 | 2.5% |
| ground_claim | 85 | 8.5% |
| class_claim | 0 | 0.0% |
| fitness_claim | 36 | 3.6% |
| negative_claim | 157 | 15.7% |
| unsupported_hype_claim | 32 | 3.2% |

---

## Sample High-Claim Records

**Hexagonal** — 3 claims detected
Claims: handicap_claim, negative_claim, unsupported_hype_claim
> Definite promise in a couple of turf maidens last year but disappointed on handicap debut at Dundalk; unexposed and remains with potential so check th

**Hexagonal** — 3 claims detected
Claims: handicap_claim, negative_claim, unsupported_hype_claim
> Definite promise in a couple of turf maidens last year but disappointed on handicap debut at Dundalk; unexposed and remains with potential so check th

**Hexagonal** — 3 claims detected
Claims: handicap_claim, negative_claim, unsupported_hype_claim
> Definite promise in a couple of turf maidens last year but disappointed on handicap debut at Dundalk; unexposed and remains with potential so check th

**Handin Manypockets** — 2 claims detected
Claims: handicap_claim, negative_claim
> Lightly raced gelding who was beaten under 10l in a useful 2m4f maiden hurdle at Cheltenham three runs back; struggled on handicap debut at Taunton (3

**Check The Score** — 2 claims detected
Claims: improvement_claim, ground_claim
> No match for the winner at Southwell but that was over hurdles and after 363 days off; won his only previous chase by 3l at Market Rasen 13 months ago

---

## Claim Type Definitions

| Type | Description |
|---|---|
| improvement_claim | Horse expected to improve (green, first run, strip fitter) |
| handicap_claim | Handicap mark or rating assessment |
| stable_intent_claim | Trainer/connections interest or intent signals |
| trip_claim | Trip/distance preference stated |
| ground_claim | Going/ground preference stated |
| class_claim | Drop or rise in class noted |
| fitness_claim | Fitness level signal (well, spot-on, needed run) |
| negative_claim | Negative flag (disappointing, below par, pulled up) |
| unsupported_hype_claim | Vague positive filler with no structural basis |

---

## Governance

```
Phase A — regex baseline. Read-only.
Does not modify scoring, routing, or live state.
Phase B (DSPy pipeline) requires operator approval.
Phase C (fine-tuned SLM) requires GPU + separate approval.
```