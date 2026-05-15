# RACING POST ADAPTER V2 — DESIGN PROPOSAL

## Status

```
V1: COMMITTED, OPERATIONAL
V2: DESIGN PROPOSAL — code changes below, not yet committed
Scope: Adapter improvements only. No scoring integration. No DB writes.
Commit gate: Operator approval required before applying.
```

---

## V2 Goals

1. **Venue code normalisation** — adapter produces full venue names, not PDF short codes
2. **Coverage warnings** — missing Postdata, Spotlight, or field completeness flagged in output
3. **Runner identity confidence** — explicit field indicating how reliable the runner extraction is
4. **Stable output schema** — guarantee all runner feature fields are always present (null not absent)
5. **May 14 + May 15 dual validation** — confirm V2 produces consistent output across both dates

---

## Change 1 — Venue Code Map + `_norm_venue()`

**Problem:** `ingest_racecard_pdfs.py` writes venue codes (`AIN`, `HAM`, `NBY`) into merged racecard
JSONs. The adapter reads these verbatim. Downstream consumers get short codes instead of full names.

**Proposed fix:**

```python
# At module level, after imports:
_VENUE_CODE_MAP: dict[str, str] = {
    # Standard PDF filename codes → full venue names
    "AIN": "Aintree",       "Ain": "Aintree",
    "HAM": "Hamilton",
    "NBY": "Newbury",
    "YOR": "York",
    "CLO": "Clonmel",
    "FON": "Fontwell",
    "PER": "Perth",
    "SAL": "Salisbury",
    "KLB": "Kilbeggan",
    "LEO": "Leopardstown",
    "NMK": "Newmarket",
    "NCS": "Newcastle",
    "CHE": "Chester",
    "AYR": "Ayr",
    "DON": "Doncaster",
    "ESS": "Essex",           # Chelmsford (AW) sometimes coded ESS
    "CHM": "Chelmsford (AW)",
    "CHF": "Chelmsford (AW)",
    "KEM": "Kempton (AW)",
    "LIN": "Lingfield",
    "LIN-AW": "Lingfield (AW)",
    "SND": "Sandown",
    "WIN": "Windsor",
    "WOL": "Wolverhampton (AW)",
    "GOO": "Goodwood",
    "SLI": "Sligo",
    "NAA": "Naas",
    "NAS": "Naas",
    "CUR": "Curragh",
    "GAL": "Galway",
    "BAL": "Ballinrobe",
    "MUS": "Musselburgh",
    "BEV": "Beverley",
    "PON": "Pontefract",
    "CAR": "Carlisle",
    "REA": "Reading",
    "WRC": "Worcester",
    "CHT": "Chepstow",
    "HER": "Hereford",
    "STR": "Stratford",
    "LUD": "Ludlow",
    "TAU": "Taunton",
    "EXE": "Exeter",
    "WTH": "Wincanton",
    "PLU": "Plumpton",
    "FKE": "Ffos Las",
    "HUN": "Huntingdon",
    "NPT": "Newport",
    "UTT": "Uttoxeter",
    "SOU": "Southwell (AW)",
    "NAW": "Nottingham",
    "THP": "Thirsk",
    "REI": "Brighton",
    "BMT": "Bath",
    "MKT": "Market Rasen",
    "WEX": "Wexford",
    "TIP": "Tipperary",
    "NAV": "Navan",
}


def _norm_venue(code: str) -> str:
    """Normalise PDF venue code to full name. Returns code unchanged if not in map."""
    return _VENUE_CODE_MAP.get(code, _VENUE_CODE_MAP.get(code.upper(), code))
```

**Where to apply:** In `build_racing_post_features()`, change:
```python
venue = card.get("venue", path.stem.split("_")[1])
```
to:
```python
venue = _norm_venue(card.get("venue", path.stem.split("_")[1]))
```

**Impact:** Zero — purely normalises string output. No logic change.

---

## Change 2 — Coverage Warnings

**Problem:** V1 reports coverage counts but doesn't warn when fields are missing at race or runner level.

**Proposed addition:** Add `coverage_warnings` list to the root output object:

```python
# In build_racing_post_features(), collect:
coverage_warnings: list[str] = []

for path in ...:
    card = ...
    if not card.get("spotlight_verdict") and not any(
        h.get("spotlight_comment") for h in card.get("horses", [])
    ):
        coverage_warnings.append(f"{venue}: no Spotlight coverage")
    if not card.get("postdata_pick") and not card.get("topspeed_pick"):
        coverage_warnings.append(f"{venue}: no Postdata or Topspeed pick")

# Include in payload:
payload["coverage_warnings"] = coverage_warnings
```

**Threshold for alert:** > 20% of races missing Spotlight = operator investigation required.

---

## Change 3 — Runner Identity Confidence

**Problem:** Some runners have null `current_or`, null `current_ts`, null `spotlight_comment`.
Downstream consumers can't tell if the runner is genuinely data-thin or if extraction failed.

**Proposed addition:** Per-runner `identity_confidence` field:

```python
def _identity_confidence(h: dict) -> str:
    """Classify data completeness for this runner."""
    score = 0
    if h.get("current_or"):
        score += 2
    if h.get("current_ts"):
        score += 2
    if h.get("current_rpr"):
        score += 1
    if h.get("spotlight_comment"):
        score += 2
    if h.get("going_flag") and h.get("going_flag") != "no_data":
        score += 1
    if h.get("or_trend") != "INSUFFICIENT":
        score += 1
    if h.get("ts_trend") != "INSUFFICIENT":
        score += 1
    if score >= 8:
        return "HIGH"
    if score >= 4:
        return "MEDIUM"
    return "LOW"
```

Add `"identity_confidence": _identity_confidence(h)` to each runner feature dict.

**Downstream use:** CASHRUN, convergence report, and learning can weight LOW-confidence
runners differently. Not used in V1 — stored only.

---

## Change 4 — Stable Schema (null-fill missing fields)

**Problem:** If a merged racecard is missing expected fields, the runner dict omits keys rather than
setting them to null. Downstream consumers break on `KeyError`.

**Proposed fix:** In `extract_race_features()`, ensure every runner dict always has every key:

```python
runner_template = {
    "horse": None,
    "or_rank": None,
    "current_or": None,
    "current_ts": None,
    "current_rpr": None,
    "or_trend": "INSUFFICIENT",
    "ts_trend": "INSUFFICIENT",
    "or_compression": 0,
    "going_flag": None,
    "distance_flag": None,
    "course_flag": None,
    "draw_flag": None,
    "ability_flag": None,
    "trainer_form": None,
    "trainer_form_signal": None,
    "plot_conviction": None,
    "handicap_plot_score": None,
    "stall": None,
    "days_since_last_run": None,
    "headgear": None,
    "spotlight_comment": None,
    "claim_tags": [],
    "consensus_signals": [],
    "postdata_pick": False,
    "topspeed_pick": False,
    "identity_confidence": "LOW",
}
# Then merge with extracted values:
runner_features.append({**runner_template, **extracted_dict})
```

This guarantees schema stability regardless of source data completeness.

---

## Change 5 — Schema Version Field

Add `"schema_version": "V2"` to the root output to allow consumers to detect which adapter
version produced an artifact without reading the generator timestamp.

---

## Dual Validation Plan (May 14 + May 15)

Before committing V2:

```bash
# Run V2 adapter on both dates
python scripts/build_racing_post_features.py --date 2026-05-14
python scripts/build_racing_post_features.py --date 2026-05-15

# Check venue names are normalised in output
python3 -c "
import json
d = json.load(open('data/racing_post_features/2026-05-15.json'))
venues = sorted({r['venue'] for r in d['races']})
print('Venues:', venues)
"
# Expected: ['Aintree', 'Hamilton', 'Kilbeggan', 'Leopardstown', 'Newbury', 'Newmarket', 'York']
# Not: ['AIN', 'HAM', ...]

# Check identity_confidence is present
python3 -c "
import json
d = json.load(open('data/racing_post_features/2026-05-15.json'))
runners = d['races'][0]['rp_runner_features']
print('First runner confidence:', runners[0].get('identity_confidence'))
"

# Check coverage_warnings field exists
python3 -c "
import json
d = json.load(open('data/racing_post_features/2026-05-15.json'))
print('Coverage warnings:', d.get('coverage_warnings', 'MISSING'))
"
```

---

## Files to Change

| File | Change type | Risk |
|---|---|---|
| `app/services/racing_post_adapter.py` | Add `_VENUE_CODE_MAP`, `_norm_venue()`, `_identity_confidence()`, schema template | Very low |
| `scripts/build_racing_post_features.py` | No changes needed | — |
| `docs/engineering/RACING_POST_ADAPTER_V1.md` | Update to V2 reference | Very low |

---

## What V2 Does NOT Do

```
Does not write to Supabase
Does not modify CASHRUN scoring
Does not integrate with scoring pipeline
Does not change any model weights
Does not touch sentient_state.json
Does not modify ingest_racecard_pdfs.py (upstream, not adapter responsibility)
```

---

## Commit Readiness

V2 changes are purely additive and read-only. Risk is very low.
Ready to commit as `feat(rp): RacingPostAdapter V2 — venue normalisation and schema hardening`
on operator approval.

---

## Version History

| Version | Date | Notes |
|---|---|---|
| V1 | 2026-05-15 | Design proposal written. Code not yet applied. Awaiting approval. |
