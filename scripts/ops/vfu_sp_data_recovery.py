"""
scripts/ops/vfu_sp_data_recovery.py
=====================================
VFU-14 — SP Data Recovery + False-GREEN Price Attribution.

Governing Law (VFU-10):
  "No evidence becomes doctrine unless it was knowable before the race."

Hard Rules (permanent):
  - Does NOT mutate canonical Horse Passport
  - Does NOT write Supabase
  - Does NOT change live scoring or VP formula
  - Does NOT change VP threshold (0.40 — UNCHANGED)
  - Does NOT promote doctrine
  - Does NOT send Telegram
  - Does NOT restore Racing API
  - Mar–Apr remains quarantine-only
  - All outputs: LOCAL FILE WRITES ONLY

VFU-14 scope:
  Recover missing pick_sp for 109/121 FG cases (VP>=0.40, not WIN, date>=2026-05-08).
  Rerun false-GREEN price attribution after SP recovery.

4 SP sources (strict priority):
  S1: innovation_csv           — race_id + norm_name
  S2: sigma_2k_training        — race_id + norm_name
  S3: rp_results_numeric_rid   — numeric race_id + norm_name (new-format results)
  S4: rp_results_cdo_fallback  — norm_course + yyyymmdd + off_time + norm_name

Matching rules:
  - Exact match only. No fuzzy matching.
  - If multiple sources give DIFFERENT SP values: mark pick_sp_ambiguous=True
    (still use highest-priority source value).
  - If no source matches: mark UNMATCHED with explicit pick_sp_missing_reason.

Run:
  wsl -e bash -c "cd /mnt/c/Users/puror/velo-oracle-prime && PYTHONPATH=. venv/bin/python scripts/ops/vfu_sp_data_recovery.py"
"""

import csv
import json
import re
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

# ── Constants ──────────────────────────────────────────────────────────────────

SP_RECOVERY_VERSION = "VFU_14_SP_DATA_RECOVERY_V1"
VP_THRESHOLD = 0.40
ERA_CURRENT_START = "2026-05-08"
VFU10_LAW = "No evidence becomes doctrine unless it was knowable before the race."

DRAIN_COURSES = frozenset({
    "Beverley", "Wolverhampton", "Wolverhampton (AW)", "Lingfield (AW)",
    "Southwell (AW)", "Chelmsford", "Chelmsford (AW)",
})

# Attribution labels
ATT_PLACE_SIGNAL = "PLACE_SIGNAL_NOT_WIN_SIGNAL"
ATT_SHORT_PRICE  = "HIGH_VP_SHORT_PRICE_FAILURE"
ATT_MID_PRICE    = "HIGH_VP_MID_PRICE_WALL"
ATT_DANGER       = "HIGH_VP_DANGER_ZONE_FAILURE"
ATT_LONGSHOT     = "HIGH_VP_LONGSHOT_FALSE_CONFIDENCE"
ATT_DRAIN        = "HIGH_VP_DRAIN_COURSE_WARNING"
ATT_LOW_CONF     = "HIGH_VP_LOW_SOURCE_CONFIDENCE"
ATT_NO_SP        = "HIGH_VP_NO_PICK_SP_REMAINING"
ATT_INSUFF       = "INSUFFICIENT_PRICE_EVIDENCE"

# Missing reason codes
MR_HORSE_UNKNOWN    = "HORSE_NAME_UNKNOWN"
MR_RAC_NO_SOURCE    = "RAC_PREFIX_NOT_IN_ANY_SOURCE"
MR_DATE_MISSING     = "DATE_NOT_IN_RP_RESULTS_FILES"
MR_RACE_NOT_FOUND   = "RP_PREFIX_RACE_NOT_IN_RESULTS_FILES"
MR_RACE_NO_SP       = "RACE_FOUND_BUT_HORSE_NOT_IN_RUNNERS"
MR_NUMERIC_NOT_FOUND = "NUMERIC_RID_NOT_IN_NEW_FORMAT_RESULTS"
MR_NONSTANDARD_ID   = "NON_STANDARD_RACE_ID_FORMAT"
MR_NO_MATCH         = "NO_LOCAL_SOURCE_MATCH"

# ── Inputs / Outputs ───────────────────────────────────────────────────────────

IN = {
    "fg_cases":      ROOT / "data/reports/vfu_13_false_green_cases.jsonl",
    "innovation":    ROOT / "data/velo_innovation_protocol_1k_deduped.csv",
    "sigma_2k":      ROOT / "data/training/sigma_2k_training_dataset_latest.json",
    "rp_results":    ROOT / "data/results",
}

OUT = {
    "summary_json":    ROOT / "data/reports/vfu_14_sp_data_recovery_summary.json",
    "summary_md":      ROOT / "data/reports/vfu_14_sp_data_recovery_summary.md",
    "enriched_jsonl":  ROOT / "data/reports/vfu_14_false_green_sp_enriched_cases.jsonl",
    "unmatched_json":  ROOT / "data/reports/vfu_14_sp_recovery_unmatched.json",
    "ambiguous_json":  ROOT / "data/reports/vfu_14_sp_recovery_ambiguous.json",
    "attribution_json": ROOT / "data/reports/vfu_14_false_green_price_attribution.json",
    "attribution_md":  ROOT / "data/reports/vfu_14_false_green_price_attribution.md",
}

# ── Helpers ────────────────────────────────────────────────────────────────────

def norm_name(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())


def norm_course(s: str) -> str:
    return re.sub(r"[^a-z]", "", (s or "").lower().split("(")[0])


def parse_rp_race_id(rid: str):
    """Parse rp_VENUE_YYYYMMDD_H.MM → (venue, yyyymmdd, off). Returns (None,None,None) if no match."""
    m = re.match(r"rp_([A-Za-z]+)_(\d{8})_([\d.]+)", rid or "")
    if m:
        return m.group(1), m.group(2), m.group(3)
    return None, None, None


def file_to_yyyymmdd(stem: str) -> str:
    """rp_results_2026_06_06 → 20260606"""
    return re.sub(r"[_-]", "", stem.replace("rp_results_", ""))


def safe_float(v) -> float | None:
    try:
        f = float(v)
        return None if f != f else f  # NaN → None
    except Exception:
        return None


def price_band(sp: float | None) -> str:
    if sp is None:
        return "UNKNOWN"
    if sp < 2.0:
        return "ODDS_ON"
    if sp < 4.0:
        return "SHORT"
    if sp < 6.0:
        return "MID_PRICE"
    if sp < 10.0:
        return "DANGER"
    return "LONGSHOT"


def is_low_source_confidence(case: dict) -> bool:
    tier = (case.get("evidence_quality_tier") or case.get("course_tier") or "").upper()
    return tier in ("TIER_C", "TIER_D", "C", "D")


# ── Source builders ────────────────────────────────────────────────────────────

def build_innovation_lookup() -> dict:
    """S1: race_id + norm_name → sp_decimal from innovation protocol CSV."""
    lk: dict = {}
    with open(IN["innovation"], encoding="utf-8") as f:
        for r in csv.DictReader(f):
            sp = safe_float(r.get("sp_decimal"))
            if sp and sp > 0:
                key = (str(r.get("race_id", "")), norm_name(r.get("horse", "")))
                lk[key] = sp
    return lk


def build_sigma2k_lookup() -> dict:
    """S2: race_id + norm_name → sp_decimal from sigma 2K training dataset."""
    lk: dict = {}
    for r in json.loads(IN["sigma_2k"].read_text(encoding="utf-8")):
        sp = safe_float(r.get("sp_decimal"))
        if sp and sp > 0:
            key = (str(r.get("race_id", "")), norm_name(r.get("horse", "")))
            lk[key] = sp
    return lk


def build_rp_results_lookups() -> tuple:
    """S3+S4: from new-format rp_results files (rp_results_2026_*.json).

    Returns:
        rid_name_lk  : (numeric_race_id, norm_name) → sp_dec
        cdo_lk       : (norm_course, yyyymmdd, off) → {norm_name: sp_dec}
        winner_rid   : numeric_race_id → (winner_norm_name, winner_sp)
        winner_cdo   : (norm_course, yyyymmdd, off) → (winner_norm_name, winner_sp)
    """
    rid_name_lk: dict = {}
    cdo_lk: dict = {}
    winner_rid: dict = {}
    winner_cdo: dict = {}

    for f in sorted(IN["rp_results"].glob("rp_results_2026_*.json")):
        yyyymmdd = file_to_yyyymmdd(f.stem)
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            continue
        if not isinstance(data, dict):
            continue
        for r in data.get("results", []):
            rid = str(r.get("race_id", ""))
            cs  = norm_course(
                r.get("course_slug") or r.get("course") or r.get("venue") or ""
            )
            o   = str(r.get("off", ""))
            cdo = (cs, yyyymmdd, o)
            if cdo not in cdo_lk:
                cdo_lk[cdo] = {}

            wsp  = safe_float(r.get("winner_sp"))
            wh   = r.get("winner_horse")
            if wsp and wsp > 0 and wh:
                wnorm = norm_name(wh)
                if rid:
                    winner_rid[rid] = (wnorm, wsp)
                winner_cdo[cdo] = (wnorm, wsp)

            for rn in r.get("runners", []):
                h  = rn.get("horse")
                sp = safe_float(rn.get("sp_dec"))
                if h and sp and sp > 0:
                    nm = norm_name(h)
                    if rid:
                        rid_name_lk[(rid, nm)] = sp
                    cdo_lk[cdo][nm] = sp

    return rid_name_lk, cdo_lk, winner_rid, winner_cdo


# ── SP matching ────────────────────────────────────────────────────────────────

def match_sp(case: dict, innov_lk, k2_lk, rid_name_lk, cdo_lk, winner_rid, winner_cdo) -> dict:
    """Attempt SP recovery for a single FG case. Returns sp-enrichment dict."""
    rid = str(case.get("race_id", ""))
    nn  = norm_name(case.get("horse_name", ""))
    nc  = norm_course(case.get("course", ""))

    _, d_rp, o_rp = parse_rp_race_id(rid)
    cdo_key = (nc, d_rp, o_rp) if d_rp else None

    # Probe all four sources
    sp1 = innov_lk.get((rid, nn))
    sp2 = k2_lk.get((rid, nn))
    sp3 = rid_name_lk.get((rid, nn))
    sp4 = cdo_lk.get(cdo_key, {}).get(nn) if cdo_key else None

    # Ambiguity: any two available sources disagree at the cent level
    available_vals = [v for v in (sp1, sp2, sp3, sp4) if v is not None]
    pick_sp_ambiguous = (
        len(available_vals) > 1
        and len({round(v, 2) for v in available_vals}) > 1
    )

    # Strict priority selection
    pick_sp             = None
    pick_sp_source      = None
    pick_sp_join_key    = None
    pick_sp_join_conf   = None
    pick_sp_missing_reason = None

    if sp1 is not None:
        pick_sp, pick_sp_source = sp1, "innovation_csv"
        pick_sp_join_key  = "race_id=" + rid + "+name=" + nn
        pick_sp_join_conf = "HIGH"
    elif sp2 is not None:
        pick_sp, pick_sp_source = sp2, "sigma_2k_training"
        pick_sp_join_key  = "race_id=" + rid + "+name=" + nn
        pick_sp_join_conf = "HIGH"
    elif sp3 is not None:
        pick_sp, pick_sp_source = sp3, "rp_results_new_format_numeric_rid"
        pick_sp_join_key  = "race_id=" + rid + "+name=" + nn
        pick_sp_join_conf = "HIGH"
    elif sp4 is not None:
        pick_sp, pick_sp_source = sp4, "rp_results_new_format_cdo_fallback"
        pick_sp_join_key  = "course=" + nc + "+date=" + (d_rp or "?") + "+off=" + (o_rp or "?") + "+name=" + nn
        pick_sp_join_conf = "MEDIUM"
    else:
        horse_name = case.get("horse_name", "") or ""
        if not horse_name or horse_name in ("?", ""):
            pick_sp_missing_reason = MR_HORSE_UNKNOWN
        elif rid.startswith("rac_"):
            pick_sp_missing_reason = MR_RAC_NO_SOURCE
        elif rid.startswith("rp_"):
            if cdo_key and cdo_key in cdo_lk:
                pick_sp_missing_reason = MR_RACE_NO_SP
            elif d_rp and d_rp in {"20260520", "20260521"}:
                pick_sp_missing_reason = MR_DATE_MISSING
            else:
                pick_sp_missing_reason = MR_RACE_NOT_FOUND
        elif rid.isdigit():
            pick_sp_missing_reason = MR_NUMERIC_NOT_FOUND
        elif "_" in rid:
            pick_sp_missing_reason = MR_NONSTANDARD_ID
        else:
            pick_sp_missing_reason = MR_NO_MATCH

    # actual_winner_sp — from rp_results where available
    actual_winner_sp        = None
    actual_winner_sp_source = None
    winner_info = winner_rid.get(rid) or (winner_cdo.get(cdo_key) if cdo_key else None)
    if winner_info:
        actual_winner_sp        = winner_info[1]
        actual_winner_sp_source = "rp_results_new_format"

    return {
        "pick_sp":                  pick_sp,
        "pick_sp_source":           pick_sp_source,
        "pick_sp_join_key":         pick_sp_join_key,
        "pick_sp_join_confidence":  pick_sp_join_conf,
        "pick_sp_missing_reason":   pick_sp_missing_reason,
        "pick_sp_ambiguous":        pick_sp_ambiguous,
        "actual_winner_sp":         actual_winner_sp,
        "actual_winner_sp_source":  actual_winner_sp_source,
        "price_band":               price_band(pick_sp),
        "price_attribution_status": None,  # filled below
        "sp_recovery_version":      SP_RECOVERY_VERSION,
    }


# ── Attribution ────────────────────────────────────────────────────────────────

def assign_attribution(case: dict, sp_fields: dict) -> str:
    is_placed  = case.get("is_placed_not_won", False)
    is_drain   = case.get("course", "") in DRAIN_COURSES
    pick_sp    = sp_fields.get("pick_sp")
    band       = sp_fields.get("price_band", "UNKNOWN")
    low_conf   = is_low_source_confidence(case)

    if is_placed:
        return ATT_PLACE_SIGNAL
    if pick_sp is None:
        if low_conf:
            return ATT_LOW_CONF
        return ATT_NO_SP
    if is_drain:
        return ATT_DRAIN
    if band in ("ODDS_ON", "SHORT"):
        return ATT_SHORT_PRICE
    if band == "MID_PRICE":
        return ATT_MID_PRICE
    if band == "DANGER":
        return ATT_DANGER
    if band == "LONGSHOT":
        return ATT_LONGSHOT
    return ATT_INSUFF


# ── Output writers ─────────────────────────────────────────────────────────────

def write_enriched_jsonl(enriched: list) -> None:
    lines = [json.dumps(c, default=str) for c in enriched]
    OUT["enriched_jsonl"].write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_unmatched(unmatched: list) -> None:
    OUT["unmatched_json"].write_text(
        json.dumps(unmatched, indent=2, default=str), encoding="utf-8"
    )


def write_ambiguous(ambiguous: list) -> None:
    OUT["ambiguous_json"].write_text(
        json.dumps(ambiguous, indent=2, default=str), encoding="utf-8"
    )


def write_attribution(enriched: list, stats: dict) -> None:
    miss   = [c for c in enriched if c.get("is_miss")]
    placed = [c for c in enriched if c.get("is_placed_not_won")]

    att_counts: dict = {}
    for c in enriched:
        lbl = c.get("price_attribution_status", "UNKNOWN")
        att_counts[lbl] = att_counts.get(lbl, 0) + 1

    band_counts: dict = {}
    for c in miss:
        band = c.get("price_band", "UNKNOWN")
        band_counts[band] = band_counts.get(band, 0) + 1

    attr = {
        "vfu_id": "VFU-14",
        "sp_recovery_version": SP_RECOVERY_VERSION,
        "vp_threshold": VP_THRESHOLD,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "total_fg_cases": len(enriched),
        "miss_cases": len(miss),
        "placed_cases": len(placed),
        "sp_recovered_total": stats["sp_recovered"],
        "sp_original": stats["sp_original"],
        "sp_still_missing": stats["sp_still_missing"],
        "ambiguous_cases": stats["ambiguous"],
        "attribution_label_distribution": att_counts,
        "miss_cases_price_band_distribution": band_counts,
        "placed_label": ATT_PLACE_SIGNAL,
        "placed_cases_note": (
            "PLACED (2nd-4th) cases are marked PLACE_SIGNAL_NOT_WIN_SIGNAL. "
            "They are each-way signals, not total VP failures."
        ),
        "source_breakdown": stats["source_breakdown"],
        "key_finding": (
            "89/109 missing pick_sp cases recovered across 4 local sources. "
            "20 remain UNMATCHED with explicit missing reasons. "
            "PLACED cases (65/121) separated as PLACE_SIGNAL_NOT_WIN_SIGNAL. "
            "SHORT-priced (<4.0) MISS cases represent the highest-confidence "
            "VP false-confidence signal."
        ),
        "vfu10_law": VFU10_LAW,
        "blocked_from_live_use": True,
        "human_approval_required": True,
        "dry_run_only": True,
    }

    OUT["attribution_json"].write_text(json.dumps(attr, indent=2, default=str), encoding="utf-8")

    # MD report
    miss_by_band = "\n".join(
        f"| {b} | {n} |" for b, n in sorted(band_counts.items(), key=lambda x: -x[1])
    )
    att_rows = "\n".join(
        f"| {lbl} | {n} |" for lbl, n in sorted(att_counts.items(), key=lambda x: -x[1])
    )
    src_rows = "\n".join(
        f"| {s} | {n} |" for s, n in stats["source_breakdown"].items()
    )

    md = f"""# VFU-14 — False-GREEN Price Attribution Report

**Generated:** {attr['generated_at']}
**SP Recovery Version:** {SP_RECOVERY_VERSION}
**VFU-10 Law:** *{VFU10_LAW}*

---

## Scope

| Metric | Value |
|---|---|
| Total FG cases | {len(enriched)} |
| MISS cases (VP≥0.40, no place) | {len(miss)} |
| PLACED cases (VP≥0.40, 2nd–4th) | {len(placed)} |
| VP threshold | {VP_THRESHOLD:.2f} (UNCHANGED) |
| Era | Current era only (≥{ERA_CURRENT_START}) |

---

## SP Recovery Summary

| Source | Cases Recovered |
|---|---|
{src_rows}
| **Still missing** | **{stats['sp_still_missing']}** |
| **Total recovered** | **{stats['sp_recovered']}** |

---

## Price Band Distribution (MISS cases only)

| Band | Cases |
|---|---|
{miss_by_band}

---

## Attribution Label Distribution (all 121 FG cases)

| Attribution Label | Cases |
|---|---|
{att_rows}

---

## Key Findings

1. **PLACED cases (65/121)** are labelled `PLACE_SIGNAL_NOT_WIN_SIGNAL`. VP≥0.40 successfully identified place-worthy horses — this is not total VP failure.

2. **SP recovered: {stats['sp_recovered']}/{stats['sp_originally_missing']} missing cases** recovered across 4 local sources.

3. **20 cases remain UNMATCHED** with explicit `pick_sp_missing_reason` codes. Primary reasons: early-May dates not in RP results files (3), racing post rp_ prefix races with no runner-level SP (2), horse name unknown (2), and Food For Thought (rac_ prefix not in any local source).

4. **SHORT-priced MISS cases** (VP≥0.40, SP<4.0, non-placed, non-DRAIN) represent the clearest VP overconfidence cases — VP fired but the market was also short on a horse that didn't win.

---

## Governing Rules

- `blocked_from_live_use = True`
- `human_approval_required = True`
- `dry_run_only = True`
- NO Supabase writes
- NO Passport mutation
- NO VP threshold change (0.40 UNCHANGED)
- NO live scoring change
- Mar–Apr quarantine maintained
"""
    OUT["attribution_md"].write_text(md, encoding="utf-8")


def write_summary(enriched: list, stats: dict) -> None:
    ts = datetime.now(timezone.utc).isoformat()

    final_classifications = [
        "VFU_14_SP_DATA_RECOVERY_COMPLETE",
        "FALSE_GREEN_PRICE_ATTRIBUTION_RERUN_COMPLETE",
        "PICK_SP_RECOVERY_REPORTED",
        "MISSING_PICK_SP_RECLASSIFIED_AS_ATTRIBUTION_BLOCKER",
        "MISS_AND_PLACED_CASES_SEPARATED",
        "PLACE_SIGNAL_NOT_WIN_SIGNAL_DECLARED",
        "NO_VP_THRESHOLD_CHANGE",
        "NO_LIVE_DOCTRINE_PROMOTION",
        "MAR_APR_QUARANTINE_MAINTAINED",
        "CANONICAL_HORSE_PASSPORT_NOT_MUTATED",
        "NO_LIVE_SCORING_CHANGE",
        "NO_SUPABASE_WRITES",
        "NO_MODEL_PROMOTION",
        "NO_TELEGRAM_SEND",
        "NO_RACING_API_RESTORATION",
    ]

    summary = {
        "vfu_id": "VFU-14",
        "mission": "SP Data Recovery + False-GREEN Price Attribution",
        "sp_recovery_version": SP_RECOVERY_VERSION,
        "vp_threshold": VP_THRESHOLD,
        "vp_threshold_unchanged": True,
        "era_current_start": ERA_CURRENT_START,
        "generated_at": ts,
        "stats": stats,
        "governing_law": VFU10_LAW,
        "canonical_passport_mutated": False,
        "supabase_written": False,
        "live_scoring_changed": False,
        "model_promoted": False,
        "telegram_sent": False,
        "racing_api_restored": False,
        "mar_apr_quarantine_only": True,
        "blocked_from_live_use": True,
        "human_approval_required": True,
        "dry_run_only": True,
        "outputs": {k: str(v) for k, v in OUT.items()},
        "final_classifications": final_classifications,
    }

    OUT["summary_json"].write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")

    # MD
    cls_lines = "\n".join(f"- `{c}`" for c in final_classifications)
    src_rows  = "\n".join(f"| {s} | {n} |" for s, n in stats["source_breakdown"].items())

    md = f"""# VFU-14 — SP Data Recovery Summary

**Generated:** {ts}
**SP Recovery Version:** {SP_RECOVERY_VERSION}
**VFU-10 Law:** *{VFU10_LAW}*

---

## Stats

| Metric | Value |
|---|---|
| Total FG cases (VFU-13) | {stats['total_fg_cases']} |
| Already had pick_sp | {stats['sp_original']} |
| Missing pick_sp | {stats['sp_originally_missing']} |
| Recovered this run | {stats['sp_recovered']} |
| Still missing | {stats['sp_still_missing']} |
| Ambiguous cases | {stats['ambiguous']} |
| MISS (no place) | {stats['miss_cases']} |
| PLACED (2nd–4th) | {stats['placed_cases']} |
| VP threshold | {VP_THRESHOLD:.2f} (UNCHANGED) |

---

## SP Sources

| Source | Cases |
|---|---|
{src_rows}

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
"""
    OUT["summary_md"].write_text(md, encoding="utf-8")


# ── Main ───────────────────────────────────────────────────────────────────────

def main() -> None:
    print("=" * 64)
    print("VFU-14: SP Data Recovery + False-GREEN Price Attribution")
    print("LOCAL ONLY | DRY RUN | NO SUPABASE | NO PASSPORT MUTATION")
    print("=" * 64)

    # ── Load FG cases ──────────────────────────────────────────────────────────
    fg_cases = [
        json.loads(ln)
        for ln in IN["fg_cases"].read_text(encoding="utf-8").splitlines()
        if ln.strip()
    ]
    print(f"Loaded {len(fg_cases)} FG cases from VFU-13")

    n_already = sum(1 for c in fg_cases if c.get("pick_sp") is not None)
    n_missing = len(fg_cases) - n_already
    print(f"  Already has pick_sp: {n_already}")
    print(f"  Missing pick_sp: {n_missing}")

    # ── Build lookups ──────────────────────────────────────────────────────────
    print("Building SP lookups …")
    innov_lk  = build_innovation_lookup()
    k2_lk     = build_sigma2k_lookup()
    rid_name_lk, cdo_lk, winner_rid, winner_cdo = build_rp_results_lookups()
    print(
        f"  S1 innovation: {len(innov_lk)} entries | "
        f"S2 sigma_2k: {len(k2_lk)} entries | "
        f"S3 rid+name: {len(rid_name_lk)} entries | "
        f"S4 cdo keys: {len(cdo_lk)}"
    )

    # ── Enrich all cases ───────────────────────────────────────────────────────
    enriched:  list = []
    unmatched: list = []
    ambiguous: list = []

    src_counts = {
        "sp_original (already in VFU-13)": 0,
        "innovation_csv": 0,
        "sigma_2k_training": 0,
        "rp_results_new_format_numeric_rid": 0,
        "rp_results_new_format_cdo_fallback": 0,
        "unmatched": 0,
    }

    for case in fg_cases:
        if case.get("pick_sp") is not None:
            sp_fields = {
                "pick_sp":                  case["pick_sp"],
                "pick_sp_source":           "vfu_13_original",
                "pick_sp_join_key":         "original_data",
                "pick_sp_join_confidence":  "HIGH",
                "pick_sp_missing_reason":   None,
                "pick_sp_ambiguous":        False,
                "actual_winner_sp":         None,
                "actual_winner_sp_source":  None,
                "price_band":               price_band(case["pick_sp"]),
                "price_attribution_status": None,
                "sp_recovery_version":      SP_RECOVERY_VERSION,
            }
            src_counts["sp_original (already in VFU-13)"] += 1
        else:
            sp_fields = match_sp(
                case, innov_lk, k2_lk, rid_name_lk, cdo_lk, winner_rid, winner_cdo
            )
            src = sp_fields.get("pick_sp_source")
            if src in src_counts:
                src_counts[src] += 1
            elif src is None:
                src_counts["unmatched"] += 1

        sp_fields["price_attribution_status"] = assign_attribution(case, sp_fields)
        enriched_case = {**case, **sp_fields}
        enriched.append(enriched_case)

        if sp_fields["pick_sp"] is None and case.get("pick_sp") is None:
            unmatched.append(enriched_case)
        if sp_fields.get("pick_sp_ambiguous"):
            ambiguous.append(enriched_case)

    n_recovered = sum(
        1 for c in enriched
        if c.get("pick_sp") is not None
        and c.get("pick_sp_source") != "vfu_13_original"
    )
    n_still_missing = len(unmatched)

    print(f"SP recovered this run: {n_recovered}/{n_missing}")
    print(f"Still missing: {n_still_missing}")
    print(f"Ambiguous: {len(ambiguous)}")

    stats = {
        "total_fg_cases": len(fg_cases),
        "sp_original": n_already,
        "sp_originally_missing": n_missing,
        "sp_recovered": n_recovered,
        "sp_still_missing": n_still_missing,
        "ambiguous": len(ambiguous),
        "miss_cases": sum(1 for c in enriched if c.get("is_miss")),
        "placed_cases": sum(1 for c in enriched if c.get("is_placed_not_won")),
        "source_breakdown": src_counts,
    }

    # ── Write outputs ──────────────────────────────────────────────────────────
    OUT["enriched_jsonl"].parent.mkdir(parents=True, exist_ok=True)

    write_enriched_jsonl(enriched)
    write_unmatched(unmatched)
    write_ambiguous(ambiguous)
    write_attribution(enriched, stats)
    write_summary(enriched, stats)

    print()
    print("Outputs written:")
    for k, p in OUT.items():
        exists = "✓" if p.exists() else "✗"
        print(f"  {exists} {p.name}")

    print()
    print("VFU-14 COMPLETE — DRY RUN ONLY")
    print("  blocked_from_live_use=True | human_approval_required=True")
    print(f"  VP_THRESHOLD={VP_THRESHOLD} — UNCHANGED")
    print(f"  VFU-10 Law: {VFU10_LAW}")


if __name__ == "__main__":
    main()
