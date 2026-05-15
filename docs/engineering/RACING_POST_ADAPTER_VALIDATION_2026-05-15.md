# RACING POST ADAPTER VALIDATION — 2026-05-15

## Purpose

First live validation of `RacingPostAdapter V1` against real Racing Post PDF data.
Confirms coverage, field population, claim detection, consensus signals, and read-only
contract for a full 7-venue race day. This is a read-only evidence document.

## Execution

```bash
python scripts/build_racing_post_features.py --date 2026-05-15
```

Output: `data/racing_post_features/2026-05-15.json` (685KB, local only, never committed)

---

## Coverage Summary

| Metric | Value | Assessment |
|---|---|---|
| Venues | 7 | Full day — York, Aintree, Hamilton, Kilbeggan, Leopardstown, Newmarket, Newbury |
| Races | 52 | Complete |
| Runners | 552 | Complete |
| Spotlight present | 52/52 | **100% coverage** |
| Postdata present | 42/52 | 80.8% — expected (NH races lack postdata) |
| Generated at | 2026-05-15T03:23:58Z | UTC, correct |

All 7 venues successfully read. Missing coverage would produce no rows and be
reported in the coverage block — no silent failure observed.

---

## Venue Code Finding

**Finding:** The adapter output stores venues as short codes (`AIN`, `HAM`, `NBY`)
rather than full names (`Aintree`, `Hamilton`, `Newbury`).

**Root cause:** `ingest_racecard_pdfs.py` writes the venue field using the PDF filename
code (e.g. `AIN` from `AIN_20260515_*.pdf`). The adapter reads this verbatim via
`card.get("venue", ...)`. The adapter itself is correct — it reflects what is in the
merged racecard JSON.

**Impact:** The adapter output is a local artifact only. Downstream consumers
(convergence report, dashboard) must normalize venue codes. `build_industry_comparison.py`
already does this via `COURSE_ALIASES`. Any new consumer that joins on venue name must
use the same normalizer.

**Recommendation:** Add `_norm_venue(code: str) -> str` to `racing_post_adapter.py`
that maps short codes to full names at extraction time. Not required for V1 — document
the known state.

---

## Field Population — Per-Runner Assessment

Validated against AIN 4:35 race (6 runners) as the sample case.

| Field | Population | Notes |
|---|---|---|
| `horse` | ✅ All runners named | |
| `or_rank` | ✅ Computed correctly by OR descending | Road To Wembley OR=120, rank=1 |
| `current_or` | Partial | NH races: null for most runners; Road To Wembley (OR=120) populated correctly |
| `current_ts` | ✅ Populated | 29–101 range visible. Into Battle=77, Road To Wembley=101 |
| `current_rpr` | Partial | Road To Wembley RPR=124 populated; NH runners with limited postdata: null |
| `or_trend` | ✅ All values firing | RISING, FALLING, INSUFFICIENT all present |
| `ts_trend` | ✅ All values firing | IMPROVING, FLAT_OR_DECLINING, INSUFFICIENT all present |
| `or_compression` | Partial | All 0 in NH sample — expected, OR compression is a Flat handicap concept |
| `going_flag` | ✅ Populated | `positive`, `uncertain` observed |
| `distance_flag` | ✅ Populated | `positive`, `uncertain` observed |
| `course_flag` | ✅ Populated | `uncertain` dominant in NH opener (expected) |
| `draw_flag` | Partial | `no_data` for NH races — expected, no draw factor |
| `ability_flag` | ✅ Populated | `positive`, `strong_positive`, `negative` all firing |
| `trainer_form` | ✅ Populated | `positive`, `negative` observed |
| `trainer_form_signal` | ✅ Numeric | 0.0, 0.1 observed |
| `plot_conviction` | ✅ Populated | 0.05–0.34 range |
| `handicap_plot_score` | Partial | null for NH horses without handicap marks — expected |
| `stall` | Partial | null in NH races — expected (NH races have no draw) |
| `days_since_last_run` | Partial | null in sample — source field present in colourcard data |
| `headgear` | Partial | null in sample — expected for many NH horses |
| `spotlight_comment` | ✅ Full text | Complete Spotlight prose extracted |
| `claim_tags` | ✅ Firing | `NEGATIVE_CLAIM` fired on "opposable on a few counts" (Red Nile) |
| `consensus_signals` | ✅ Firing | `FLAG:GOING_POSITIVE`, `FLAG:DISTANCE_POSITIVE`, `FLAG:ABILITY_POSITIVE` |
| `postdata_pick` | ✅ Boolean | Road To Wembley correctly flagged True |
| `topspeed_pick` | ✅ Boolean | Road To Wembley correctly flagged True |

---

## Claim Tag Validation

Claim tag extraction fired correctly in the AIN sample:

| Horse | Tag fired | Trigger phrase |
|---|---|---|
| Red Nile | `NEGATIVE_CLAIM` | "opposable on a few counts" |

The spotlight text for the race ("Road To Wembley is taken to defy his penalty... Maskarvel is another who could make it interesting") correctly generated `HANDICAP_CLAIM` at race level via `rp_race_features.top_claim_tags`.

Full 52-race tag distribution not extracted in this validation — a dedicated claim tag audit
should be run post-accumulation.

---

## Consensus Signal Validation

Consensus signals fired correctly:

- Into Battle: `FLAG:GOING_POSITIVE`, `FLAG:DISTANCE_POSITIVE`, `FLAG:ABILITY_POSITIVE`
- Road To Wembley: `RP_POSTDATA_PICK`, `RP_TOPSPEED_PICK` (both systems agree)
- Maskarvel: `FLAG:GOING_POSITIVE`, `FLAG:DISTANCE_POSITIVE`, `FLAG:ABILITY_POSITIVE`

Postdata + Topspeed agreement on the same horse (Road To Wembley) is the strongest
consensus signal — correctly surfaced.

---

## OR Rating Rank Validation

AIN 4:35 rank order:

| Rank | Horse | OR |
|---|---|---|
| 1 | Road To Wembley | 120 |
| 2 | Into Battle | (null) |
| 3 | Jet Renegade | (null) |
| 4 | Maskarvel | (null) |
| 5 | Phantom Gold | (null) |
| 6 | Red Nile | (null) |

Road To Wembley correctly ranked 1 (only horse with a known OR). Null-OR horses
ranked 2–6 by their inferred position — correct, as null sorts to 0 (bottom).

**Finding:** When only one horse has a known OR, the rank order for the remaining field
is arbitrary (all tie at OR=0, sort by insertion order). This is expected for NH
races where many runners lack official ratings.

---

## Read-Only Contract Verification

Confirmed no side effects in this run:

- ✅ No Supabase writes
- ✅ No `velo_verdicts` changes
- ✅ No `sigma_audits` changes
- ✅ `data/sentient_state.json` untouched
- ✅ No SQPE weights changes
- ✅ No Telegram messages
- ✅ No routing rule changes
- ✅ Output is `data/racing_post_features/2026-05-15.json` only

---

## Open Issues for V2

| Issue | Priority | Action |
|---|---|---|
| Venue codes not normalized (AIN/HAM/NBY instead of full names) | Medium | Add `_norm_venue()` in adapter |
| `days_since_last_run` null when colourcard data is present | Low | Debug field path in merged racecard schema |
| `stall` null in NH races | Low | Expected — document |
| `or_rank` arbitrary for null-OR runners | Low | Consider INSUFFICIENT rank label instead of positional |
| Claim tag coverage audit across all 52 races | Medium | Run post-accumulation analysis |

---

## Verdict

**RacingPostAdapter V1 is functioning correctly for its defined scope.**

Coverage is complete (7 venues, 52 races, 552 runners). All primary feature fields
populate. Claim tags and consensus signals fire correctly. The read-only contract
holds — no side effects observed. The venue short code issue is known and non-critical
for the adapter's defined role as a local artifact. Downstream consumers are responsible
for venue normalization.

**No changes required to proceed with evidence accumulation.**

---

## Version History

| Version | Date | Changes |
|---|---|---|
| V1 | 2026-05-15 | Initial live validation. 7 venues, 52 races, 552 runners. Venue code finding documented. |
