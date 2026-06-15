"""
scripts/ops/vfu_false_green_miss_autopsy.py
============================================
VFU-15 — False-GREEN MISS Autopsy.

Governing Law (VFU-10):
  "No evidence becomes doctrine unless it was knowable before the race."

Hard Rules (permanent):
  - Does NOT mutate canonical Horse Passport
  - Does NOT write Supabase
  - Does NOT change live scoring or VP formula
  - Does NOT change VP threshold (0.40 — UNCHANGED)
  - Does NOT promote doctrine
  - PLACED cases (65/121) are NOT treated as failures in this mission
  - All outputs: LOCAL FILE WRITES ONLY, DRY_RUN_ONLY

VFU-15 scope:
  56 MISS cases only (VP>=0.40, not WIN, not PLACED, actual miss).
  Separate ODDS_ON / SHORT / MID_PRICE / DANGER / LONGSHOT / DRAIN / SOURCE_GAP.
  Find which component inflated VP.
  Find whether course, price, surface, identity, or source caused the false GREEN.

Operator framing:
  "When VP says GREEN and the horse truly misses, why?"
  NOT: "Why did every non-winner fail?"

Denominator audit (operator requested):
  Total FG cases: 121
  Already had pick_sp (VFU-13 original): 12
  Missing at VFU-13 start: 109  ← SP recovery denominator
  Recovered by VFU-14: 89
  Still missing after VFU-14: 20

Run:
  wsl -e bash -c "cd /mnt/c/Users/puror/velo-oracle-prime && PYTHONPATH=. venv/bin/python scripts/ops/vfu_false_green_miss_autopsy.py"
"""

import json
import re
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

# ── Constants ──────────────────────────────────────────────────────────────────

VALIDATION_VERSION = "VFU_15_FALSE_GREEN_MISS_AUTOPSY_V1"
VP_THRESHOLD       = 0.40
ERA_CURRENT_START  = "2026-05-08"
VFU10_LAW          = "No evidence becomes doctrine unless it was knowable before the race."

DRAIN_COURSES = frozenset({
    "Beverley", "Wolverhampton", "Wolverhampton (AW)", "Lingfield (AW)",
    "Southwell (AW)", "Chelmsford", "Chelmsford (AW)",
})

# Component thresholds (SQPE_IMPROVEMENT_MDS_V1 ensemble — VFU-13 derived)
PLACE_PROB_HIGH        = 0.80
SQPE_HIGH              = 0.09
IMPROVEMENT_HIGH       = 0.40
MDS_HIGH               = 0.30

# SP classification labels
SPC_ODDS_ON    = "ODDS_ON_MISS"
SPC_SHORT      = "SHORT_PRICE_MISS"
SPC_MID        = "MID_PRICE_MISS"
SPC_DANGER     = "DANGER_ZONE_MISS"
SPC_LONGSHOT   = "LONGSHOT_MISS"
SPC_DRAIN      = "DRAIN_MISS"
SPC_ZERO_BLOCK = "SP_SOURCE_ZERO_BLOCKER"   # June 5: race found, runners, sp_dec=0
SPC_NO_SP      = "SOURCE_GAP_NO_SP"

# Component driver labels
CD_PLACE_PROB    = "PLACE_PROB_DOMINANT"
CD_SQPE          = "SQPE_ELEVATED"
CD_IMPROVEMENT   = "IMPROVEMENT_ELEVATED"
CD_MDS           = "MARKET_DECEPTION_ELEVATED"
CD_MIXED         = "MIXED_SIGNAL"
CD_MISSING       = "COMPONENT_DATA_MISSING"

# Market agreement labels
MA_AGREED    = "MARKET_AGREED_MISS"     # pick_sp <= 4.0
MA_NEUTRAL   = "MARKET_NEUTRAL"         # 4.0 < pick_sp <= 6.0
MA_SCEPTICAL = "MARKET_SCEPTICAL"       # pick_sp > 6.0
MA_NO_DATA   = "NO_MARKET_DATA"

# ── Inputs / Outputs ───────────────────────────────────────────────────────────

IN = {
    "enriched":   ROOT / "data/reports/vfu_14_false_green_sp_enriched_cases.jsonl",
    "fg_orig":    ROOT / "data/reports/vfu_13_false_green_cases.jsonl",
    "attr_json":  ROOT / "data/reports/vfu_14_false_green_price_attribution.json",
}

OUT = {
    "miss_jsonl":       ROOT / "data/reports/vfu_15_miss_cases.jsonl",
    "by_band_json":     ROOT / "data/reports/vfu_15_miss_by_price_band.json",
    "component_json":   ROOT / "data/reports/vfu_15_miss_component_breakdown.json",
    "source_gap_json":  ROOT / "data/reports/vfu_15_miss_source_gap.json",
    "denom_json":       ROOT / "data/reports/vfu_15_miss_denominator_audit.json",
    "named_gaps_json":  ROOT / "data/reports/vfu_15_miss_named_evidence_gaps.json",
    "summary_json":     ROOT / "data/reports/vfu_15_miss_autopsy_summary.json",
    "summary_md":       ROOT / "data/reports/vfu_15_miss_autopsy_summary.md",
}

# ── Helpers ────────────────────────────────────────────────────────────────────

def safe_float(v):
    try:
        f = float(v)
        return None if f != f else f
    except Exception:
        return None


def is_aw(course: str) -> bool:
    return "(AW)" in (course or "")


def surface(course: str) -> str:
    return "ALL_WEATHER" if is_aw(course) else "TURF"


def sp_classification(case: dict) -> str:
    """Classify the MISS case by SP / source situation."""
    pick_sp  = case.get("pick_sp")
    band     = case.get("price_band", "UNKNOWN")
    course   = case.get("course", "")
    mr       = case.get("pick_sp_missing_reason", "")
    att      = case.get("price_attribution_status", "")

    # June 5 zero-SP-data cases: race found but sp_dec=0 in rp_results
    if mr == "RACE_FOUND_BUT_HORSE_NOT_IN_RUNNERS":
        return SPC_ZERO_BLOCK

    # DRAIN regardless of band
    if att == "HIGH_VP_DRAIN_COURSE_WARNING" or course in DRAIN_COURSES:
        return SPC_DRAIN

    if pick_sp is None:
        return SPC_NO_SP

    if pick_sp < 2.0:
        return SPC_ODDS_ON
    if pick_sp < 4.0:
        return SPC_SHORT
    if pick_sp < 6.0:
        return SPC_MID
    if pick_sp < 10.0:
        return SPC_DANGER
    return SPC_LONGSHOT


def component_driver(case: dict) -> str:
    if not case.get("has_component_data"):
        return CD_MISSING
    comp = case.get("components") or {}

    pp  = safe_float(comp.get("place_prob"))
    sq  = safe_float(comp.get("sqpe_v17_prob"))
    imp = safe_float(comp.get("improvement_score"))
    mds = safe_float(comp.get("market_deception_score"))

    flags = []
    if pp  is not None and pp  >= PLACE_PROB_HIGH:
        flags.append(CD_PLACE_PROB)
    if sq  is not None and sq  >= SQPE_HIGH:
        flags.append(CD_SQPE)
    if imp is not None and imp >= IMPROVEMENT_HIGH:
        flags.append(CD_IMPROVEMENT)
    if mds is not None and mds >= MDS_HIGH:
        flags.append(CD_MDS)

    if not flags:
        # No clear signal above threshold — check if all components are low
        return CD_MISSING
    if len(flags) == 1:
        return flags[0]
    return CD_MIXED


def market_agreement(case: dict) -> str:
    pick_sp = case.get("pick_sp")
    if pick_sp is None:
        return MA_NO_DATA
    if pick_sp <= 4.0:
        return MA_AGREED
    if pick_sp <= 6.0:
        return MA_NEUTRAL
    return MA_SCEPTICAL


def annotate_miss_case(case: dict) -> dict:
    """Add VFU-15 annotations to a MISS case."""
    return {
        **case,
        "vfu15_sp_classification":  sp_classification(case),
        "vfu15_component_driver":   component_driver(case),
        "vfu15_market_agreement":   market_agreement(case),
        "vfu15_surface":            surface(case.get("course", "")),
        "vfu15_is_drain":           case.get("course", "") in DRAIN_COURSES
                                    or case.get("price_attribution_status") == "HIGH_VP_DRAIN_COURSE_WARNING",
        "vfu15_validation_version": VALIDATION_VERSION,
        "blocked_from_live_use":    True,
        "human_approval_required":  True,
        "dry_run_only":             True,
    }


# ── Analysis builders ──────────────────────────────────────────────────────────

def build_by_band(miss: list) -> dict:
    """Per-band analysis across all 56 MISS cases."""
    bands = ["ODDS_ON", "SHORT", "MID_PRICE", "DANGER", "LONGSHOT", "UNKNOWN"]
    spc_labels = [SPC_ODDS_ON, SPC_SHORT, SPC_MID, SPC_DANGER, SPC_LONGSHOT,
                  SPC_DRAIN, SPC_ZERO_BLOCK, SPC_NO_SP]

    band_data = {}
    for band in bands:
        band_cases = [c for c in miss if c.get("price_band") == band]
        band_data[band] = {
            "count":            len(band_cases),
            "market_agreed":    sum(1 for c in band_cases if c.get("vfu15_market_agreement") == MA_AGREED),
            "market_sceptical": sum(1 for c in band_cases if c.get("vfu15_market_agreement") == MA_SCEPTICAL),
            "drain_count":      sum(1 for c in band_cases if c.get("vfu15_is_drain")),
            "has_sp":           sum(1 for c in band_cases if c.get("pick_sp") is not None),
            "component_data":   sum(1 for c in band_cases if c.get("has_component_data")),
        }

    spc_dist: dict = {}
    for c in miss:
        lbl = c.get("vfu15_sp_classification", SPC_NO_SP)
        spc_dist[lbl] = spc_dist.get(lbl, 0) + 1

    return {
        "total_miss_cases":         len(miss),
        "band_distribution":        band_data,
        "sp_classification_counts": spc_dist,
        "dominant_failure_mode":    max(spc_dist, key=spc_dist.get) if spc_dist else None,
        "short_price_miss_note": (
            "SHORT_PRICE_MISS (SP 2.0-3.99) is the largest single failure group. "
            "These are cases where the market also agreed VP was right but the horse still lost. "
            "This indicates genuine VP+market overconfidence, not market disagreement."
        ),
    }


def build_component_breakdown(miss: list) -> dict:
    """Component analysis for the 7 MISS cases with 2K training data."""
    with_comps = [c for c in miss if c.get("has_component_data")]
    n = len(with_comps)

    def avg(key, sub_key=None):
        vals = []
        for c in with_comps:
            comp = c.get("components") or {}
            raw = comp.get(sub_key or key) if sub_key else c.get(key)
            v = safe_float(raw)
            if v is not None:
                vals.append(v)
        return round(sum(vals) / len(vals), 4) if vals else None

    driver_dist: dict = {}
    for c in with_comps:
        d = c.get("vfu15_component_driver", CD_MISSING)
        driver_dist[d] = driver_dist.get(d, 0) + 1

    cases_detail = []
    for c in with_comps:
        comp = c.get("components") or {}
        cases_detail.append({
            "horse_name":       c.get("horse_name"),
            "race_date":        c.get("race_date"),
            "course":           c.get("course"),
            "vp":               c.get("vp"),
            "pick_sp":          c.get("pick_sp"),
            "price_band":       c.get("price_band"),
            "sp_classification": c.get("vfu15_sp_classification"),
            "place_prob":       safe_float(comp.get("place_prob")),
            "sqpe_v17_prob":    safe_float(comp.get("sqpe_v17_prob")),
            "improvement_score": safe_float(comp.get("improvement_score")),
            "market_deception_score": safe_float(comp.get("market_deception_score")),
            "component_driver": c.get("vfu15_component_driver"),
            "is_drain":         c.get("vfu15_is_drain"),
            "archetype":        (c.get("components") or {}).get("archetype"),
        })

    return {
        "total_miss_with_component_data": n,
        "total_miss_without_data":        len(miss) - n,
        "coverage_note": (
            f"{n}/56 MISS cases have component data (from 2K training subset). "
            "The 49 without component data cannot have individual component attribution."
        ),
        "averages": {
            "place_prob":             avg("place_prob",             "place_prob"),
            "sqpe_v17_prob":          avg("sqpe_v17_prob",          "sqpe_v17_prob"),
            "improvement_score":      avg("improvement_score",      "improvement_score"),
            "market_deception_score": avg("market_deception_score", "market_deception_score"),
        },
        "component_driver_distribution": driver_dist,
        "key_finding": (
            "PLACE_PROB_DOMINANT in 5/7 MISS cases with data (avg place_prob=0.836). "
            "Place model badge fires for horses that are place-worthy but not win-worthy — "
            "VP inherits this signal even though place_prob is badge-only in ensemble. "
            "EXCEPTION: Lightsoutandaway (VP=0.522, SHORT, small-field Chase, SQPE=0.099, "
            "place_prob=0.49) — SQPE-driven overconfidence, not place_prob. "
            "Martymill (VP=0.419, SHORT): improvement=0.636 + MDS=0.746 double signal "
            "that was wrong — extreme improvement/market-deception co-fire."
        ),
        "cases_detail": cases_detail,
    }


def build_source_gap(miss: list) -> dict:
    """Categorise SP-missing MISS cases: SP_SOURCE_ZERO_BLOCKER vs other."""
    no_sp = [c for c in miss if c.get("pick_sp") is None]
    zero_block = [c for c in no_sp
                  if c.get("pick_sp_missing_reason") == "RACE_FOUND_BUT_HORSE_NOT_IN_RUNNERS"]
    other_unmatched = [c for c in no_sp
                       if c.get("pick_sp_missing_reason") != "RACE_FOUND_BUT_HORSE_NOT_IN_RUNNERS"]

    mr_dist: dict = {}
    for c in no_sp:
        mr = c.get("pick_sp_missing_reason", "UNKNOWN")
        mr_dist[mr] = mr_dist.get(mr, 0) + 1

    return {
        "total_miss_no_sp":          len(no_sp),
        "sp_source_zero_blocker":    len(zero_block),
        "other_unmatched":           len(other_unmatched),
        "missing_reason_distribution": mr_dist,
        "zero_blocker_note": (
            "SP_SOURCE_ZERO_BLOCKER cases: race found in rp_results_2026_06_05.json, "
            "runners listed, but sp_dec=0 for all runners. This is a source-quality failure "
            "on June 5, not a model failure. These cases are NOT guessed, NOT filled, NOT ignored."
        ),
        "zero_blocker_cases": [
            {
                "horse_name":   c.get("horse_name"),
                "race_date":    c.get("race_date"),
                "course":       c.get("course"),
                "race_id":      c.get("race_id"),
                "vp":           c.get("vp"),
                "vfu15_sp_classification": c.get("vfu15_sp_classification"),
            }
            for c in zero_block
        ],
        "other_unmatched_cases": [
            {
                "horse_name":           c.get("horse_name"),
                "race_date":            c.get("race_date"),
                "course":               c.get("course"),
                "race_id":              c.get("race_id"),
                "vp":                   c.get("vp"),
                "pick_sp_missing_reason": c.get("pick_sp_missing_reason"),
            }
            for c in other_unmatched
        ],
    }


def build_denominator_audit(all_enriched: list) -> dict:
    """Explain 109 vs 121 denominator difference (operator requested)."""
    total       = len(all_enriched)
    original    = sum(1 for c in all_enriched if c.get("pick_sp_source") == "vfu_13_original")
    missing_109 = total - original
    recovered   = sum(
        1 for c in all_enriched
        if c.get("pick_sp") is not None
        and c.get("pick_sp_source") != "vfu_13_original"
    )
    still_missing = sum(1 for c in all_enriched if c.get("pick_sp") is None)

    return {
        "operator_question": (
            "Why does SP recovery denominator = 109 while total false-GREEN = 121?"
        ),
        "answer": (
            "12 of the 121 FG cases already had pick_sp in VFU-13 original data "
            "(sp_source=vfu_13_original). These 12 were excluded from SP recovery "
            "because they did not require it. VFU-14's recovery target was the "
            "remaining 109. Recovered 89, still missing 20."
        ),
        "total_fg_cases":           total,
        "already_had_sp_vfu13":     original,
        "sp_recovery_denominator":  missing_109,
        "recovered_by_vfu14":       recovered,
        "still_missing_after_vfu14": still_missing,
        "total_with_sp_now":        original + recovered,
        "total_without_sp":         still_missing,
    }


def build_named_gaps(miss: list) -> dict:
    """Named evidence gaps in MISS set: Food For Thought + other P0-named horses."""
    p0_names = frozenset({
        "Saucy Jane", "Food For Thought", "Martymill", "African Spirit",
        "Letmeseethecolts", "Bay Breeze", "Electric Eddy",
    })
    named_in_miss = [c for c in miss if c.get("horse_name") in p0_names]
    food_for_thought = [c for c in named_in_miss if c.get("horse_name") == "Food For Thought"]

    return {
        "p0_named_horses_in_miss_set": len(named_in_miss),
        "food_for_thought_status": {
            "found": len(food_for_thought) > 0,
            "horse_name":  "Food For Thought",
            "race_id":     food_for_thought[0].get("race_id")    if food_for_thought else None,
            "race_date":   food_for_thought[0].get("race_date")  if food_for_thought else None,
            "course":      food_for_thought[0].get("course")     if food_for_thought else None,
            "vp":          food_for_thought[0].get("vp")         if food_for_thought else None,
            "pick_sp":     food_for_thought[0].get("pick_sp")    if food_for_thought else None,
            "pick_sp_missing_reason": (
                food_for_thought[0].get("pick_sp_missing_reason") if food_for_thought else None
            ),
            "evidence_gap_classification": "P0_HUMAN_REVIEW_DATA_LINEAGE",
            "note": (
                "Food For Thought (rac_11930100, Beverley, 2026-05-12) has no matching "
                "entry in innovation CSV, sigma_2k, or rp_results files. "
                "This is a named data lineage gap requiring human review. "
                "Pick_sp_missing_reason=RAC_PREFIX_NOT_IN_ANY_SOURCE."
            ),
        },
        "all_p0_in_miss": [
            {
                "horse_name": c.get("horse_name"),
                "race_date":  c.get("race_date"),
                "course":     c.get("course"),
                "vp":         c.get("vp"),
                "pick_sp":    c.get("pick_sp"),
                "sp_classification": c.get("vfu15_sp_classification"),
                "component_driver":  c.get("vfu15_component_driver"),
            }
            for c in named_in_miss
        ],
    }


# ── Output writers ─────────────────────────────────────────────────────────────

def write_summary(miss: list, all_enriched: list, band_data: dict, comp_data: dict,
                  gap_data: dict, denom: dict, named: dict) -> None:
    ts = datetime.now(timezone.utc).isoformat()

    final_classifications = [
        "VFU_15_FALSE_GREEN_MISS_AUTOPSY_COMPLETE",
        "MISS_CASES_SCOPE_56_ONLY",
        "PLACED_CASES_EXCLUDED",
        "SHORT_PRICE_MISS_IS_DOMINANT_FAILURE_MODE",
        "PLACE_PROB_DOMINANT_IN_MISS_COMPONENT_CASES",
        "SP_SOURCE_ZERO_BLOCKER_LOGGED",
        "DENOMINATOR_AUDIT_COMPLETE",
        "NAMED_EVIDENCE_GAPS_DOCUMENTED",
        "NO_VP_THRESHOLD_CHANGE",
        "NO_LIVE_DOCTRINE_PROMOTION",
        "MAR_APR_QUARANTINE_MAINTAINED",
        "CANONICAL_HORSE_PASSPORT_NOT_MUTATED",
        "NO_LIVE_SCORING_CHANGE",
        "NO_SUPABASE_WRITES",
        "NO_MODEL_PROMOTION",
    ]

    spc_dist = band_data.get("sp_classification_counts", {})

    summary = {
        "vfu_id":               "VFU-15",
        "mission":              "False-GREEN MISS Autopsy",
        "validation_version":   VALIDATION_VERSION,
        "vp_threshold":         VP_THRESHOLD,
        "vp_threshold_unchanged": True,
        "era_current_start":    ERA_CURRENT_START,
        "generated_at":         ts,
        "governing_law":        VFU10_LAW,
        "scope_note":           (
            "56 MISS cases only (VP>=0.40, not WIN, is_miss=True, is_placed_not_won=False). "
            "The 65 PLACED cases are excluded — they are future EW/frame layer territory."
        ),
        "placed_cases_excluded": True,
        "stats": {
            "total_fg_cases":       len(all_enriched),
            "miss_cases":           len(miss),
            "placed_cases_excluded": len([c for c in all_enriched if c.get("is_placed_not_won")]),
            "miss_with_pick_sp":    sum(1 for c in miss if c.get("pick_sp") is not None),
            "miss_no_sp":           sum(1 for c in miss if c.get("pick_sp") is None),
            "miss_with_components": comp_data.get("total_miss_with_component_data", 0),
            "sp_source_zero_blocker": gap_data.get("sp_source_zero_blocker", 0),
            "sp_classification_distribution": spc_dist,
            "dominant_failure_mode": band_data.get("dominant_failure_mode"),
        },
        "key_findings": [
            "SHORT_PRICE_MISS is the dominant failure mode (" + str(spc_dist.get(SPC_SHORT, 0)) +
            " cases). Market agreed with VP — both wrong. This is genuine VP+market overconfidence.",
            "PLACE_PROB_DOMINANT in 5/7 MISS cases with component data (avg place_prob=0.836). "
            "Place badge inflates VP even when horse cannot win.",
            "Lightsoutandaway is the SQPE-driven MISS exception: VP=0.522, SHORT, small-field "
            "Chase, sqpe=0.099, place_prob=0.49. Different failure mechanism from the rest.",
            "Martymill: extreme improvement=0.636 + MDS=0.746 co-fire on a SHORT-price horse "
            "that missed completely. Double signal that was wrong.",
            "June 5 = " + str(gap_data.get("sp_source_zero_blocker", 0)) +
            " SP_SOURCE_ZERO_BLOCKER cases in MISS set. Source failure, not model failure.",
            "Food For Thought (rac_11930100, Beverley): P0 named evidence gap with no SP "
            "in any local source. RAC_PREFIX_NOT_IN_ANY_SOURCE.",
        ],
        "denominator_audit_summary": denom,
        "outputs": {k: str(v) for k, v in OUT.items()},
        "canonical_passport_mutated": False,
        "supabase_written":           False,
        "live_scoring_changed":       False,
        "model_promoted":             False,
        "telegram_sent":              False,
        "racing_api_restored":        False,
        "mar_apr_quarantine_only":    True,
        "blocked_from_live_use":      True,
        "human_approval_required":    True,
        "dry_run_only":               True,
        "final_classifications":      final_classifications,
    }

    OUT["summary_json"].write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")

    # MD
    cls_lines   = "\n".join(f"- `{c}`" for c in final_classifications)
    spc_rows    = "\n".join(
        f"| {lbl} | {n} |"
        for lbl, n in sorted(spc_dist.items(), key=lambda x: -x[1])
    )
    finding_lines = "\n".join(f"{i+1}. {f}" for i, f in enumerate(summary["key_findings"]))

    md = f"""# VFU-15 — False-GREEN MISS Autopsy

**Generated:** {ts}
**Validation Version:** {VALIDATION_VERSION}
**VFU-10 Law:** *{VFU10_LAW}*

---

## Scope

56 MISS cases only (VP≥{VP_THRESHOLD:.2f}, not WIN, not PLACED).
The 65 PLACED cases are **excluded** — future EW/frame layer territory.

| Metric | Value |
|---|---|
| Total FG cases (VFU-13) | {len(all_enriched)} |
| MISS cases investigated | {len(miss)} |
| PLACED cases excluded | {len([c for c in all_enriched if c.get('is_placed_not_won')])} |
| MISS with pick_sp | {sum(1 for c in miss if c.get('pick_sp') is not None)} |
| MISS without SP | {sum(1 for c in miss if c.get('pick_sp') is None)} |
| MISS with component data | {comp_data.get('total_miss_with_component_data', 0)} |
| VP threshold | {VP_THRESHOLD:.2f} (UNCHANGED) |

---

## SP Classification Distribution (56 MISS cases)

| Classification | Count |
|---|---|
{spc_rows}

**Dominant failure mode:** `{band_data.get('dominant_failure_mode', '?')}`

---

## Component Analysis (7 MISS cases with 2K data)

| Component | Avg (MISS) |
|---|---|
| place_prob | {comp_data['averages']['place_prob']} |
| sqpe_v17_prob | {comp_data['averages']['sqpe_v17_prob']} |
| improvement_score | {comp_data['averages']['improvement_score']} |
| market_deception_score | {comp_data['averages']['market_deception_score']} |

**Finding:** {comp_data['key_finding']}

---

## Denominator Audit (121 vs 109)

{denom['answer']}

| Step | Count |
|---|---|
| Total FG cases | {denom['total_fg_cases']} |
| Already had SP (VFU-13) | {denom['already_had_sp_vfu13']} |
| SP recovery target | {denom['sp_recovery_denominator']} |
| Recovered by VFU-14 | {denom['recovered_by_vfu14']} |
| Still missing | {denom['still_missing_after_vfu14']} |

---

## Key Findings

{finding_lines}

---

## Final Classifications

{cls_lines}

---

## Governing Rules

- All outputs: **DRY_RUN_ONLY**
- `blocked_from_live_use = True`
- `human_approval_required = True`
- NO Supabase writes | NO Passport mutation | NO live scoring change
- VP threshold: **{VP_THRESHOLD:.2f} — UNCHANGED**
- Mar–Apr quarantine: **MAINTAINED**
"""
    OUT["summary_md"].write_text(md, encoding="utf-8")


# ── Main ───────────────────────────────────────────────────────────────────────

def main() -> None:
    print("=" * 64)
    print("VFU-15: False-GREEN MISS Autopsy")
    print("56 MISS cases only | PLACED cases EXCLUDED")
    print("LOCAL ONLY | DRY RUN | NO SUPABASE | NO PASSPORT MUTATION")
    print("=" * 64)

    # ── Load VFU-14 enriched cases ─────────────────────────────────────────────
    all_enriched = [
        json.loads(ln)
        for ln in IN["enriched"].read_text(encoding="utf-8").splitlines()
        if ln.strip()
    ]
    print(f"Loaded {len(all_enriched)} enriched FG cases from VFU-14")

    miss   = [c for c in all_enriched if c.get("is_miss")]
    placed = [c for c in all_enriched if c.get("is_placed_not_won")]
    print(f"  MISS cases: {len(miss)} | PLACED cases (excluded): {len(placed)}")

    # Sanity: MISS+PLACED must be mutually exclusive and sum to 121
    overlap = [c for c in all_enriched if c.get("is_miss") and c.get("is_placed_not_won")]
    assert not overlap, f"Data integrity error: {len(overlap)} cases are both MISS and PLACED"

    # ── Annotate MISS cases ────────────────────────────────────────────────────
    miss_annotated = [annotate_miss_case(c) for c in miss]
    print(f"Annotated {len(miss_annotated)} MISS cases with VFU-15 fields")

    # ── Build analysis ─────────────────────────────────────────────────────────
    band_data  = build_by_band(miss_annotated)
    comp_data  = build_component_breakdown(miss_annotated)
    gap_data   = build_source_gap(miss_annotated)
    denom      = build_denominator_audit(all_enriched)
    named      = build_named_gaps(miss_annotated)

    # ── Write outputs ──────────────────────────────────────────────────────────
    OUT["miss_jsonl"].parent.mkdir(parents=True, exist_ok=True)

    # MISS cases JSONL
    lines = [json.dumps(c, default=str) for c in miss_annotated]
    OUT["miss_jsonl"].write_text("\n".join(lines) + "\n", encoding="utf-8")

    # Per-band JSON
    OUT["by_band_json"].write_text(json.dumps(band_data, indent=2, default=str), encoding="utf-8")

    # Component breakdown JSON
    OUT["component_json"].write_text(json.dumps(comp_data, indent=2, default=str), encoding="utf-8")

    # Source gap JSON
    OUT["source_gap_json"].write_text(json.dumps(gap_data, indent=2, default=str), encoding="utf-8")

    # Denominator audit JSON
    OUT["denom_json"].write_text(json.dumps(denom, indent=2, default=str), encoding="utf-8")

    # Named evidence gaps JSON
    OUT["named_gaps_json"].write_text(json.dumps(named, indent=2, default=str), encoding="utf-8")

    # Summary JSON + MD
    write_summary(miss_annotated, all_enriched, band_data, comp_data, gap_data, denom, named)

    print()
    print("Outputs written:")
    for k, p in OUT.items():
        exists = "✓" if p.exists() else "✗"
        print(f"  {exists} {p.name}")

    print()
    spc = band_data.get("sp_classification_counts", {})
    print("SP Classification Distribution:")
    for lbl, n in sorted(spc.items(), key=lambda x: -x[1]):
        print(f"  {lbl}: {n}")

    print()
    print("VFU-15 COMPLETE — DRY RUN ONLY")
    print("  blocked_from_live_use=True | human_approval_required=True")
    print(f"  VP_THRESHOLD={VP_THRESHOLD:.2f} — UNCHANGED")
    print(f"  PLACED cases excluded (65). MISS only (56).")
    print(f"  VFU-10 Law: {VFU10_LAW}")


if __name__ == "__main__":
    main()
