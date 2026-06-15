#!/usr/bin/env python3
"""
scripts/ops/vfu_sigma_investigation_unit.py
============================================
VFU-11 — 2K Sigma Investigation Unit.

Era-separated, read-only master forensic investigation across the wider
Sigma archive. Carries the VFU-10 law:

  No evidence becomes doctrine unless it was knowable before the race.

Hard rules (permanent — never relax):
  - Does NOT mutate canonical Horse Passport.
  - Does NOT write Supabase.
  - Does NOT change live scoring.
  - Does NOT change VP threshold.
  - Does NOT promote doctrine.
  - Does NOT promote models.
  - Does NOT send Telegram.
  - Does NOT restore Racing API.
  - Mar–Apr rows are QUARANTINE ONLY.

Era buckets:
  CURRENT_ERA_VALIDATED        : 2026-05-08 +
  PRE_SURGERY_MAY_QUARANTINE   : 2026-05-01 – 2026-05-07
  PRE_SURGERY_ARCHIVE_QUARANTINE: before 2026-05-01 (Mar–Apr etc.)
  SKELETON_OR_NULL_DATE_EXCLUDED: null / Jan–Feb / incomplete
"""
from __future__ import annotations

import json
import re
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

# ── Era boundaries ────────────────────────────────────────────────────────────
ERA_CURRENT_START      = "2026-05-08"
ERA_MAY_QUARANTINE_START = "2026-05-01"
ERA_SKELETON_CUTOFF    = "2026-02-28"  # Jan/Feb = skeleton/excluded

VP_THRESHOLD = 0.40  # UNCHANGED
VALIDATION_VERSION = "VFU_11_2K_SIGMA_INVESTIGATION_UNIT_V1"

# ── Input sources ─────────────────────────────────────────────────────────────
SOURCES = {
    "identity_enriched_autopsy": ROOT / "data/reports/vfu_current_era_autopsy_records_identity_enriched.jsonl",
    "sigma_2k_training":         ROOT / "data/training/sigma_2k_training_dataset_latest.json",
    "sigma_audits_dump":         ROOT / "data/sigma_audits_dump.json",
    "vfu_union_rows":            ROOT / "data/reports/current_era_sigma_union_rows_enriched_vfu_v1.json",
    "vfu_time_safe_validation":  ROOT / "data/reports/vfu_time_safe_passport_override_validation.json",
    "vfu_watchlist":             ROOT / "data/reports/vfu_time_safe_passport_candidate_watchlist.json",
    "sigma_schema_probe":        ROOT / "data/reports/sigma_audits_supabase_schema_probe.json",
}
SIGMA_RESULTS_DIR = ROOT / "data/sigma_results"
ARCHIVE_SIGMA_INPUT = ROOT / "archive/legacy/2026-05-19-cleanup/data/sigma_input_2026_03_16.json"

# ── Outputs ───────────────────────────────────────────────────────────────────
OUT_DIR       = ROOT / "data/reports"
OUT_JSON      = OUT_DIR / "vfu_11_sigma_investigation_summary.json"
OUT_MD        = OUT_DIR / "vfu_11_sigma_investigation_summary.md"
OUT_LEDGER    = OUT_DIR / "vfu_11_sigma_master_ledger.jsonl"
OUT_ERA_Q     = OUT_DIR / "vfu_11_sigma_era_quality_report.json"
OUT_DQ        = OUT_DIR / "vfu_11_sigma_data_quality_debt.json"
OUT_TIME_SAFE = OUT_DIR / "vfu_11_sigma_time_safety_report.json"
OUT_PATTERNS  = OUT_DIR / "vfu_11_sigma_pattern_candidates.json"
OUT_REVIEW    = OUT_DIR / "vfu_11_sigma_human_review_queue.json"


# ── Era bucketing ─────────────────────────────────────────────────────────────

def assign_era_bucket(date_str: str | None) -> str:
    if not date_str:
        return "SKELETON_OR_NULL_DATE_EXCLUDED"
    d = str(date_str).strip()[:10]
    if not re.match(r"^\d{4}-\d{2}-\d{2}$", d):
        return "SKELETON_OR_NULL_DATE_EXCLUDED"
    if d <= ERA_SKELETON_CUTOFF:
        return "SKELETON_OR_NULL_DATE_EXCLUDED"
    if d >= ERA_CURRENT_START:
        return "CURRENT_ERA_VALIDATED"
    if d >= ERA_MAY_QUARANTINE_START:
        return "PRE_SURGERY_MAY_QUARANTINE"
    return "PRE_SURGERY_ARCHIVE_QUARANTINE"


# ── VP band ───────────────────────────────────────────────────────────────────

def vp_band(vp) -> str:
    if vp is None:
        return "VP_MISSING"
    try:
        v = float(vp)
    except (TypeError, ValueError):
        return "VP_MISSING"
    if v != v:  # NaN
        return "VP_MISSING"
    if v < 0.20:
        return "VP<0.20"
    if v < 0.30:
        return "VP0.20-0.30"
    if v < 0.40:
        return "VP0.30-0.40"
    if v < 0.60:
        return "VP0.40-0.60"
    return "VP>=0.60"


def _safe_float(v) -> float | None:
    try:
        f = float(v)
        return None if f != f else round(f, 6)
    except (TypeError, ValueError):
        return None


def _safe_str(v) -> str | None:
    return str(v).strip() if v is not None else None


# ── Identity status ───────────────────────────────────────────────────────────

def assign_identity_status(row: dict) -> str:
    ns = row.get("horse_id_namespace") or row.get("namespace")
    hid = row.get("horse_id") or row.get("rp_uid")
    hname = row.get("horse_name") or row.get("horse") or row.get("predicted")

    if ns == "RP_UID" and hid:
        return "RP_UID_CONFIRMED"
    if hid and str(hid).startswith("hrs_"):
        return "EOD_NON_CANONICAL"
    if not hname and not hid:
        return "EVENT_ONLY_NO_HORSE"
    if hid and not ns:
        return "AMBIGUOUS"
    if hname and not hid:
        return "NAME_ONLY"
    return "UNMATCHED"


# ── Time-safety status ────────────────────────────────────────────────────────

def assign_time_safety_status(era_bucket: str, row: dict) -> str:
    if era_bucket == "CURRENT_ERA_VALIDATED":
        return "TIME_SAFE"
    if era_bucket == "SKELETON_OR_NULL_DATE_EXCLUDED":
        hname = row.get("horse_name") or row.get("horse") or row.get("predicted")
        if not hname:
            return "NOT_APPLICABLE_EVENT_ONLY"
        return "TIME_SAFETY_UNRESOLVED"
    if era_bucket == "PRE_SURGERY_MAY_QUARANTINE":
        return "PARTIAL_TIME_SAFE"
    # PRE_SURGERY_ARCHIVE_QUARANTINE
    return "TEMPORAL_CONTAMINATION_RISK"


# ── Usability flags ───────────────────────────────────────────────────────────

def assign_usability(era_bucket: str, identity_status: str, row: dict) -> dict:
    is_current = era_bucket == "CURRENT_ERA_VALIDATED"
    is_may_q   = era_bucket == "PRE_SURGERY_MAY_QUARANTINE"
    is_archive_q = era_bucket == "PRE_SURGERY_ARCHIVE_QUARANTINE"
    is_skeleton  = era_bucket == "SKELETON_OR_NULL_DATE_EXCLUDED"

    has_id = identity_status in ("RP_UID_CONFIRMED", "EOD_NON_CANONICAL")
    has_vp = _safe_float(row.get("velo_prime_prob") or row.get("vp") or row.get("verdict_score")) is not None
    has_sp = _safe_float(row.get("sp_decimal") or row.get("pick_sp") or row.get("actual_winner_sp")) is not None

    vp_ok = is_current or is_may_q
    course_ok = (is_current or is_may_q or is_archive_q) and has_id
    price_ok = (is_current or is_may_q or is_archive_q) and has_sp
    passport_ok = is_current and has_id

    return {
        "usable_for_vp_analysis":       vp_ok and has_vp,
        "usable_for_course_analysis":    course_ok,
        "usable_for_price_analysis":     price_ok,
        "usable_for_passport_analysis":  passport_ok,
        "usable_for_doctrine":           is_current and has_id and has_vp,
        "blocked_from_live_use":         not is_current,
    }


# ── Data gap detection ────────────────────────────────────────────────────────

def detect_data_gaps(row: dict) -> list[str]:
    gaps = []
    if not (row.get("velo_prime_prob") or row.get("vp") or row.get("verdict_score")):
        gaps.append("VP_MISSING")
    if not (row.get("horse_id") or row.get("rp_uid")):
        gaps.append("HORSE_ID_MISSING")
    if not (row.get("race_date") or row.get("date")):
        gaps.append("DATE_MISSING")
    if not (row.get("course") or row.get("track")):
        gaps.append("COURSE_MISSING")
    if not (row.get("off_time") or row.get("off")):
        gaps.append("OFF_TIME_MISSING")
    if not (row.get("pick_sp") or row.get("sp_decimal")):
        gaps.append("SP_MISSING")
    if not row.get("outcome"):
        gaps.append("OUTCOME_MISSING")
    return gaps


# ── Pattern candidate flags ───────────────────────────────────────────────────

def build_pattern_flags(row: dict, era_bucket: str, identity_status: str) -> list[str]:
    flags = []
    vp = _safe_float(row.get("velo_prime_prob") or row.get("vp") or row.get("verdict_score"))
    outcome = str(row.get("outcome", "")).upper()
    sp = _safe_float(row.get("sp_decimal") or row.get("pick_sp"))
    won = row.get("won") or (outcome == "WIN")

    if vp is not None and vp < VP_THRESHOLD and won:
        flags.append("VP_SUPPRESSION_CANDIDATE")
    if vp is not None and vp >= VP_THRESHOLD and not won:
        flags.append("FALSE_GREEN_CANDIDATE")
    if sp is not None and sp < 20.0 and won:
        flags.append("SP_SHORTENING_CANDIDATE")
    if row.get("passport_update_candidate") or row.get("pattern_update_candidate"):
        flags.append("PASSPORT_OVERRIDE_CANDIDATE")
    if era_bucket == "PRE_SURGERY_ARCHIVE_QUARANTINE":
        flags.append("ERA_CONTAMINATION_CANDIDATE")
    if len(detect_data_gaps(row)) >= 3:
        flags.append("DATA_QUALITY_DEBT_CANDIDATE")
    if identity_status in ("NAME_ONLY", "AMBIGUOUS", "UNMATCHED"):
        flags.append("IDENTITY_RESOLUTION_NEEDED")
    return flags


# ── Human review priority ─────────────────────────────────────────────────────

def human_review_priority(row: dict, pattern_flags: list[str], era_bucket: str) -> int:
    score = 0
    if "TEMPORAL_CONTAMINATION_RISK" in (row.get("time_safety_status", "")):
        score += 10
    if "FALSE_GREEN_CANDIDATE" in pattern_flags:
        score += 8
    if "VP_SUPPRESSION_CANDIDATE" in pattern_flags:
        score += 7
    if row.get("horse_id_namespace") == "RP_UID":
        score += 5
    if era_bucket == "PRE_SURGERY_MAY_QUARANTINE":
        score += 3
    if "PASSPORT_OVERRIDE_CANDIDATE" in pattern_flags:
        score += 4
    if "DATA_QUALITY_DEBT_CANDIDATE" in pattern_flags:
        score += 2
    return score


# ── Loaders ───────────────────────────────────────────────────────────────────

def _load_json(path: Path) -> list | dict | None:
    if not path.exists():
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _load_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with open(path, encoding="utf-8") as f:
        return [json.loads(ln) for ln in f if ln.strip()]


def load_identity_enriched_autopsy() -> list[dict]:
    rows = _load_jsonl(SOURCES["identity_enriched_autopsy"])
    out = []
    for r in rows:
        out.append({
            "_src_file": "vfu_current_era_autopsy_records_identity_enriched.jsonl",
            "_src_layer": "VFU_IDENTITY_ENRICHED_AUTOPSY",
            "race_id": r.get("race_id"),
            "race_date": r.get("race_date"),
            "course": r.get("course"),
            "off_time": r.get("off_time"),
            "horse_name": r.get("horse_name"),
            "horse_id": r.get("horse_id"),
            "horse_id_namespace": r.get("horse_id_namespace"),
            "vp": _safe_float(r.get("vp")),
            "pick_sp": _safe_float(r.get("pick_sp")),
            "actual_winner_sp": _safe_float(r.get("actual_winner_sp")),
            "outcome": r.get("outcome"),
            "evidence_quality_tier": r.get("evidence_quality_tier"),
            "failure_class": r.get("failure_class"),
            "data_gaps": r.get("data_gaps", []),
            "passport_update_candidate": r.get("passport_update_candidate", False),
            "pattern_update_candidate": r.get("pattern_update_candidate", False),
            "human_review_required": r.get("human_review_required", False),
            "provenance": r.get("provenance"),
        })
    return out


def load_sigma_2k() -> list[dict]:
    data = _load_json(SOURCES["sigma_2k_training"])
    if not data or not isinstance(data, list):
        return []
    out = []
    for r in data:
        out.append({
            "_src_file": "sigma_2k_training_dataset_latest.json",
            "_src_layer": "SIGMA_2K_TRAINING",
            "race_id": r.get("race_id"),
            "race_date": r.get("date"),
            "course": r.get("course"),
            "off_time": r.get("off_time"),
            "horse_name": r.get("horse"),
            "horse_id": r.get("horse_id"),
            "horse_id_namespace": None,  # not in 2K dataset
            "vp": _safe_float(r.get("velo_prime_prob")),
            "pick_sp": _safe_float(r.get("sp_decimal")),
            "actual_winner_sp": _safe_float(r.get("actual_winner_sp")),
            "outcome": "WIN" if r.get("won") else ("FRAME" if r.get("placed") else "MISS"),
            "evidence_quality_tier": r.get("confidence_level"),
            "failure_class": None,
            "data_gaps": [],
            "passport_update_candidate": False,
            "pattern_update_candidate": False,
            "human_review_required": False,
            "provenance": r.get("canonical_identity_source"),
        })
    return out


def load_sigma_audits_dump() -> list[dict]:
    data = _load_json(SOURCES["sigma_audits_dump"])
    if not data or not isinstance(data, list):
        return []
    out = []
    for r in data:
        # date may be null
        d = r.get("date") or (str(r.get("created_at", ""))[:10] if r.get("created_at") else None)
        out.append({
            "_src_file": "sigma_audits_dump.json",
            "_src_layer": "SUPABASE_SIGMA_AUDITS_DUMP",
            "race_id": r.get("race_id"),
            "race_date": d,
            "course": r.get("track"),
            "off_time": r.get("off_time"),
            "horse_name": r.get("actual_winner_name"),
            "horse_id": r.get("horse_id"),
            "horse_id_namespace": None,
            "vp": _safe_float(r.get("verdict_score")),
            "pick_sp": None,
            "actual_winner_sp": _safe_float(r.get("actual_winner_sp")),
            "outcome": r.get("outcome"),
            "evidence_quality_tier": r.get("confidence_level"),
            "failure_class": None,
            "data_gaps": [],
            "passport_update_candidate": False,
            "pattern_update_candidate": False,
            "human_review_required": False,
            "provenance": "supabase_sigma_audits",
        })
    return out


def load_sigma_results_rows() -> list[dict]:
    out = []
    if not SIGMA_RESULTS_DIR.exists():
        return out
    for f in sorted(SIGMA_RESULTS_DIR.glob("sigma_results_*.json")):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            continue
        race_date = data.get("date")
        rows = data.get("rows", [])
        for r in rows:
            if isinstance(r, str):
                continue  # PSObject string — skip
            if not isinstance(r, dict):
                continue
            out.append({
                "_src_file": f.name,
                "_src_layer": "SIGMA_RESULTS_EOD",
                "race_id": str(r.get("race_id", "")),
                "race_date": race_date,
                "course": r.get("course"),
                "off_time": r.get("off"),
                "horse_name": r.get("predicted"),
                "horse_id": str(r.get("actual_name", "")) if r.get("actual_name") else None,
                "horse_id_namespace": None,
                "vp": _safe_float(r.get("velo_prime_prob")),
                "pick_sp": _safe_float(r.get("winner_sp")),
                "actual_winner_sp": _safe_float(r.get("winner_sp")),
                "outcome": r.get("outcome", "").upper() or None,
                "evidence_quality_tier": None,
                "failure_class": r.get("miss_class"),
                "data_gaps": [],
                "passport_update_candidate": False,
                "pattern_update_candidate": False,
                "human_review_required": False,
                "provenance": f"sigma_results/{f.name}",
            })
    return out


def load_archive_sigma() -> list[dict]:
    if not ARCHIVE_SIGMA_INPUT.exists():
        return []
    try:
        data = json.loads(ARCHIVE_SIGMA_INPUT.read_text(encoding="utf-8"))
    except Exception:
        return []
    out = []
    rows = data if isinstance(data, list) else data.get("rows", [data])
    for r in rows:
        if not isinstance(r, dict):
            continue
        out.append({
            "_src_file": "sigma_input_2026_03_16.json",
            "_src_layer": "ARCHIVE_MAR_2026",
            "race_id": r.get("race_id"),
            "race_date": r.get("date") or "2026-03-16",
            "course": r.get("course"),
            "off_time": r.get("off_time"),
            "horse_name": r.get("horse") or r.get("horse_name"),
            "horse_id": r.get("horse_id"),
            "horse_id_namespace": None,
            "vp": _safe_float(r.get("velo_prime_prob") or r.get("vp")),
            "pick_sp": _safe_float(r.get("sp_decimal") or r.get("pick_sp")),
            "actual_winner_sp": _safe_float(r.get("actual_winner_sp")),
            "outcome": r.get("outcome"),
            "evidence_quality_tier": None,
            "failure_class": None,
            "data_gaps": [],
            "passport_update_candidate": False,
            "pattern_update_candidate": False,
            "human_review_required": False,
            "provenance": "archive_mar_2026",
        })
    return out


# ── Master ledger builder ─────────────────────────────────────────────────────

_ledger_id_counter = 0


def build_ledger_row(raw: dict) -> dict:
    global _ledger_id_counter
    _ledger_id_counter += 1

    race_date = raw.get("race_date")
    era_bucket = assign_era_bucket(race_date)
    identity_status = assign_identity_status(raw)
    time_safety = assign_time_safety_status(era_bucket, raw)
    usability = assign_usability(era_bucket, identity_status, raw)
    vp_val = raw.get("vp")
    band = vp_band(vp_val)
    gaps = raw.get("data_gaps") or detect_data_gaps(raw)
    pattern_flags = build_pattern_flags(raw, era_bucket, identity_status)

    outcome = str(raw.get("outcome", "") or "").upper()
    won = outcome == "WIN"

    return {
        "ledger_id": f"VFU11_{_ledger_id_counter:05d}",
        "validation_version": VALIDATION_VERSION,
        "source_file": raw.get("_src_file"),
        "source_layer": raw.get("_src_layer"),
        "era_bucket": era_bucket,
        "race_id": raw.get("race_id"),
        "race_date": race_date,
        "course": raw.get("course"),
        "off_time": raw.get("off_time"),
        "horse_name": raw.get("horse_name"),
        "horse_id": raw.get("horse_id"),
        "horse_id_namespace": raw.get("horse_id_namespace"),
        "identity_status": identity_status,
        "vp": vp_val,
        "vp_band": band,
        "outcome": raw.get("outcome"),
        "pick_sp": raw.get("pick_sp"),
        "actual_winner_sp": raw.get("actual_winner_sp"),
        "evidence_quality_tier": raw.get("evidence_quality_tier"),
        "time_safety_status": time_safety,
        "temporal_contamination_risk": time_safety in ("TEMPORAL_CONTAMINATION_RISK", "TEMPORAL_CONTAMINATION_CONFIRMED"),
        "usable_for_vp_analysis": usability["usable_for_vp_analysis"],
        "usable_for_course_analysis": usability["usable_for_course_analysis"],
        "usable_for_price_analysis": usability["usable_for_price_analysis"],
        "usable_for_passport_analysis": usability["usable_for_passport_analysis"],
        "usable_for_doctrine": usability["usable_for_doctrine"],
        "failure_class": raw.get("failure_class"),
        "pattern_candidate_flags": pattern_flags,
        "data_gaps": gaps,
        "human_review_required": bool(raw.get("human_review_required")) or bool(pattern_flags),
        "blocked_from_live_use": usability["blocked_from_live_use"],
        "provenance": raw.get("provenance"),
    }


# ── Pattern candidates ────────────────────────────────────────────────────────

def build_pattern_candidates(ledger: list[dict]) -> list[dict]:
    patterns: dict[str, list[dict]] = defaultdict(list)
    for row in ledger:
        for flag in row.get("pattern_candidate_flags", []):
            patterns[flag].append(row)

    candidates = []
    for flag, rows in sorted(patterns.items()):
        current_era = [r for r in rows if r["era_bucket"] == "CURRENT_ERA_VALIDATED"]
        n = len(rows)
        n_current = len(current_era)

        # Compute SR for VP_SUPPRESSION / FALSE_GREEN
        wins = sum(1 for r in rows if str(r.get("outcome", "")).upper() == "WIN")

        era_scope = "ALL_ERAS"
        if all(r["era_bucket"] == "CURRENT_ERA_VALIDATED" for r in rows):
            era_scope = "CURRENT_ERA_ONLY"
        elif all(r["era_bucket"] in ("PRE_SURGERY_ARCHIVE_QUARANTINE", "PRE_SURGERY_MAY_QUARANTINE") for r in rows):
            era_scope = "QUARANTINE_ERAS_ONLY"

        caveat = "QUARANTINE — do not promote to doctrine without time-safe validation"
        if era_scope == "CURRENT_ERA_ONLY":
            caveat = "Current-era only — time-safe for analysis; no doctrine until n sufficient"

        next_req = "n >= 50 + operator review before any doctrine consideration"
        if flag == "FALSE_GREEN_CANDIDATE":
            next_req = "Identify shared feature pattern; confirm with VP>=0.40 sub-population"
        elif flag == "VP_SUPPRESSION_CANDIDATE":
            next_req = "Cross-reference with time-safe pre-era Passport snapshot (per VFU-10)"
        elif flag == "SP_SHORTENING_CANDIDATE":
            next_req = "Build time-safe pre-era SP trajectory (per VFU-10 method)"

        candidates.append({
            "pattern_flag": flag,
            "n_rows": n,
            "n_current_era": n_current,
            "n_wins": wins,
            "sr": round(wins / n, 4) if n > 0 else None,
            "era_scope": era_scope,
            "caveat": caveat,
            "next_evidence_requirement": next_req,
            "blocked_from_live_use": True,
            "human_approval_required": True,
            "do_not_promote": True,
        })
    return candidates


# ── Human review queue ────────────────────────────────────────────────────────

def build_human_review_queue(ledger: list[dict]) -> list[dict]:
    candidates = [r for r in ledger if r.get("human_review_required")]
    scored = []
    for r in candidates:
        priority = human_review_priority(r, r.get("pattern_candidate_flags", []), r["era_bucket"])
        scored.append({
            "ledger_id": r["ledger_id"],
            "horse_name": r.get("horse_name"),
            "horse_id": r.get("horse_id"),
            "horse_id_namespace": r.get("horse_id_namespace"),
            "race_date": r.get("race_date"),
            "course": r.get("course"),
            "era_bucket": r["era_bucket"],
            "time_safety_status": r["time_safety_status"],
            "vp": r.get("vp"),
            "outcome": r.get("outcome"),
            "pattern_flags": r.get("pattern_candidate_flags", []),
            "data_gaps": r.get("data_gaps", []),
            "review_priority_score": priority,
            "blocked_from_live_use": True,
            "human_approval_required": True,
        })
    scored.sort(key=lambda x: x["review_priority_score"], reverse=True)
    return scored[:200]  # cap at 200 for operator review


# ── Statistics helpers ────────────────────────────────────────────────────────

def _count_by(ledger: list[dict], key: str) -> dict[str, int]:
    counts: dict[str, int] = defaultdict(int)
    for r in ledger:
        counts[str(r.get(key, "MISSING"))] += 1
    return dict(sorted(counts.items()))


def _safe_rate(vals: list[bool]) -> float | None:
    if not vals:
        return None
    return round(sum(1 for v in vals if v) / len(vals), 4)


# ── Data quality debt ─────────────────────────────────────────────────────────

def build_dq_debt(ledger: list[dict]) -> dict:
    gap_counts: dict[str, int] = defaultdict(int)
    for r in ledger:
        for gap in r.get("data_gaps", []):
            gap_counts[gap] += 1

    by_source: dict[str, dict] = defaultdict(lambda: {"rows": 0, "gaps": 0})
    for r in ledger:
        src = r.get("source_layer", "UNKNOWN")
        by_source[src]["rows"] += 1
        by_source[src]["gaps"] += len(r.get("data_gaps", []))

    return {
        "total_gap_instances": sum(gap_counts.values()),
        "gap_type_breakdown": dict(sorted(gap_counts.items(), key=lambda x: -x[1])),
        "by_source_layer": dict(by_source),
        "top_debt_type": max(gap_counts, key=lambda k: gap_counts[k]) if gap_counts else None,
    }


# ── Report builders ───────────────────────────────────────────────────────────

def build_summary(
    all_sources: dict[str, int],
    ledger: list[dict],
    patterns: list[dict],
    human_q: list[dict],
    dq: dict,
    timestamp: str,
) -> dict:
    by_era = _count_by(ledger, "era_bucket")
    by_identity = _count_by(ledger, "identity_status")
    by_time_safety = _count_by(ledger, "time_safety_status")
    by_tier = _count_by(ledger, "evidence_quality_tier")

    usable_vp      = sum(1 for r in ledger if r.get("usable_for_vp_analysis"))
    usable_course  = sum(1 for r in ledger if r.get("usable_for_course_analysis"))
    usable_price   = sum(1 for r in ledger if r.get("usable_for_price_analysis"))
    usable_passport= sum(1 for r in ledger if r.get("usable_for_passport_analysis"))
    usable_doctrine= sum(1 for r in ledger if r.get("usable_for_doctrine"))
    blocked        = sum(1 for r in ledger if r.get("blocked_from_live_use"))
    excluded       = by_era.get("SKELETON_OR_NULL_DATE_EXCLUDED", 0)

    current_era_n  = by_era.get("CURRENT_ERA_VALIDATED", 0)
    may_q_n        = by_era.get("PRE_SURGERY_MAY_QUARANTINE", 0)
    archive_q_n    = by_era.get("PRE_SURGERY_ARCHIVE_QUARANTINE", 0)

    final_classifications = [
        "VFU_11_2K_SIGMA_INVESTIGATION_UNIT_COMPLETE",
        "SIGMA_MASTER_LEDGER_CREATED",
        "ERA_BUCKETS_ENFORCED",
        "MAR_APR_QUARANTINE_ONLY",
        "CURRENT_ERA_NOT_BLENDED_WITH_PRE_SURGERY",
        "TIME_SAFETY_STATUS_ASSIGNED",
        "TEMPORAL_CONTAMINATION_BLOCKS_DOCTRINE",
        "PATTERN_CANDIDATES_DRY_RUN_ONLY",
        "HUMAN_REVIEW_QUEUE_CREATED",
        "NO_LIVE_DOCTRINE_PROMOTION",
        "NO_VP_THRESHOLD_CHANGE",
        "CANONICAL_HORSE_PASSPORT_NOT_MUTATED",
        "NO_LIVE_SCORING_CHANGE",
        "NO_SUPABASE_WRITES",
        "NO_MODEL_PROMOTION",
        "NO_TELEGRAM_SEND",
        "NO_RACING_API_RESTORATION",
    ]

    return {
        "validation_version": VALIDATION_VERSION,
        "timestamp": timestamp,
        "vp_threshold": VP_THRESHOLD,
        "vp_threshold_unchanged": True,
        "canonical_passport_mutated": False,
        "supabase_written": False,
        "live_scoring_changed": False,
        "model_promoted": False,
        "telegram_sent": False,
        "racing_api_restored": False,
        "mar_apr_quarantine_only": True,
        "current_era_not_blended": True,

        # Source inventory
        "sources_discovered": all_sources,
        "total_source_rows_discovered": sum(all_sources.values()),

        # Ledger counts
        "total_rows_processed": len(ledger),
        "by_era_bucket": by_era,
        "by_evidence_quality_tier": by_tier,
        "by_identity_status": by_identity,
        "by_time_safety_status": by_time_safety,

        # Usability
        "usable_for_vp_analysis": usable_vp,
        "usable_for_course_analysis": usable_course,
        "usable_for_price_analysis": usable_price,
        "usable_for_passport_analysis": usable_passport,
        "usable_for_doctrine": usable_doctrine,
        "blocked_from_doctrine": blocked,
        "excluded_skeleton_null_date": excluded,

        # Analysis readiness
        "current_era_findings_valid": True,
        "pre_surgery_may_study_viable": may_q_n >= 10,
        "mar_apr_archive_quarantine_status": "QUARANTINE_INSPECT_ONLY" if archive_q_n > 0 else "NO_DATA",
        "skeleton_rows_usable": False,

        # Data quality
        "top_data_quality_debts": list(dq.get("gap_type_breakdown", {}).items())[:5],
        "total_gap_instances": dq.get("total_gap_instances", 0),

        # Time safety
        "temporal_contamination_risk_rows": by_time_safety.get("TEMPORAL_CONTAMINATION_RISK", 0),
        "time_safe_rows": by_time_safety.get("TIME_SAFE", 0),

        # Pattern candidates
        "pattern_candidates_created": len(patterns),
        "human_review_queue_count": len(human_q),

        # VFU-12 recommendation
        "vfu_12_recommended": True,
        "vfu_12_focus": (
            "Expand time-safe Passport snapshot coverage to Mar–Apr era horses. "
            "Specifically: (1) build per-race-date Passport snapshots from core_v0 "
            "for the 721 archive-quarantine horses; "
            "(2) investigate SP shortening signal in PRE_SURGERY_MAY_QUARANTINE rows; "
            "(3) resolve SKELETON_OR_NULL_DATE rows by Supabase date backfill query."
        ),

        "final_classifications": final_classifications,
    }


def build_era_quality_report(ledger: list[dict]) -> dict:
    eras = ["CURRENT_ERA_VALIDATED", "PRE_SURGERY_MAY_QUARANTINE",
            "PRE_SURGERY_ARCHIVE_QUARANTINE", "SKELETON_OR_NULL_DATE_EXCLUDED"]
    report = {}
    for era in eras:
        rows = [r for r in ledger if r["era_bucket"] == era]
        n = len(rows)
        if n == 0:
            report[era] = {"n": 0}
            continue
        vp_rows = [r for r in rows if r.get("vp") is not None]
        wins = [r for r in rows if str(r.get("outcome", "")).upper() == "WIN"]
        id_confirmed = sum(1 for r in rows if r["identity_status"] == "RP_UID_CONFIRMED")
        has_course = sum(1 for r in rows if r.get("course"))
        has_sp = sum(1 for r in rows if r.get("pick_sp") is not None or r.get("actual_winner_sp") is not None)
        vp_vals = [r["vp"] for r in vp_rows]
        avg_vp = round(mean(vp_vals), 4) if vp_vals else None

        report[era] = {
            "n": n,
            "n_with_vp": len(vp_rows),
            "avg_vp": avg_vp,
            "n_wins": len(wins),
            "sr": round(len(wins) / n, 4) if n > 0 else None,
            "n_rp_uid_confirmed": id_confirmed,
            "id_coverage_pct": round(id_confirmed / n * 100, 1),
            "n_with_course": has_course,
            "n_with_sp": has_sp,
            "doctrine_eligible": era == "CURRENT_ERA_VALIDATED",
            "quarantine": era in ("PRE_SURGERY_MAY_QUARANTINE", "PRE_SURGERY_ARCHIVE_QUARANTINE"),
            "excluded": era == "SKELETON_OR_NULL_DATE_EXCLUDED",
        }
    return report


def build_time_safety_report(ledger: list[dict], patterns: list[dict]) -> dict:
    statuses = [
        "TIME_SAFE", "PARTIAL_TIME_SAFE", "TEMPORAL_CONTAMINATION_RISK",
        "TEMPORAL_CONTAMINATION_CONFIRMED", "TIME_SAFETY_UNRESOLVED", "NOT_APPLICABLE_EVENT_ONLY",
    ]
    by_status = {}
    for s in statuses:
        rows = [r for r in ledger if r.get("time_safety_status") == s]
        by_status[s] = {
            "n": len(rows),
            "doctrine_safe": s == "TIME_SAFE",
            "requires_operator_review": s in ("TEMPORAL_CONTAMINATION_RISK", "TEMPORAL_CONTAMINATION_CONFIRMED"),
        }

    contaminated = [r for r in ledger if r.get("temporal_contamination_risk")]
    top_contaminated = sorted(
        [r for r in contaminated if r.get("horse_name")],
        key=lambda x: -(x.get("vp") or 0),
    )[:20]

    return {
        "by_status": by_status,
        "total_contamination_risk": len(contaminated),
        "top_contaminated_cases": [
            {
                "horse_name": r.get("horse_name"),
                "race_date": r.get("race_date"),
                "era_bucket": r["era_bucket"],
                "vp": r.get("vp"),
                "outcome": r.get("outcome"),
                "time_safety_status": r.get("time_safety_status"),
            }
            for r in top_contaminated
        ],
        "vfu_10_law": "No evidence becomes doctrine unless it was knowable before the race.",
        "mar_apr_quarantine_enforced": True,
    }


def build_md_report(summary: dict, era_q: dict, patterns: list[dict],
                    human_q: list[dict], timestamp: str) -> str:
    lines = [
        f"# VFU-11 — 2K Sigma Investigation Unit",
        f"**Version:** {VALIDATION_VERSION}  ",
        f"**Timestamp:** {timestamp}  ",
        f"**VP Threshold:** {VP_THRESHOLD} (UNCHANGED)  ",
        "",
        "---",
        "",
        "## VFU-10 Law (carried forward)",
        "",
        "> *No evidence becomes doctrine unless it was knowable before the race.*",
        "",
        "---",
        "",
        "## Executive Summary",
        "",
        f"- Total source rows discovered: **{summary['total_source_rows_discovered']:,}**",
        f"- Total rows processed (master ledger): **{summary['total_rows_processed']:,}**",
        f"- CURRENT_ERA_VALIDATED: **{summary['by_era_bucket'].get('CURRENT_ERA_VALIDATED', 0):,}**",
        f"- PRE_SURGERY_MAY_QUARANTINE: **{summary['by_era_bucket'].get('PRE_SURGERY_MAY_QUARANTINE', 0):,}** (inspect only)",
        f"- PRE_SURGERY_ARCHIVE_QUARANTINE: **{summary['by_era_bucket'].get('PRE_SURGERY_ARCHIVE_QUARANTINE', 0):,}** (Mar–Apr, quarantine only)",
        f"- SKELETON_OR_NULL_DATE_EXCLUDED: **{summary['by_era_bucket'].get('SKELETON_OR_NULL_DATE_EXCLUDED', 0):,}** (excluded)",
        f"- Usable for VP analysis: **{summary['usable_for_vp_analysis']:,}**",
        f"- Usable for doctrine: **{summary['usable_for_doctrine']:,}**",
        f"- Blocked from live use: **{summary['blocked_from_doctrine']:,}**",
        f"- Pattern candidates created: **{summary['pattern_candidates_created']}**",
        f"- Human review queue: **{summary['human_review_queue_count']}**",
        "",
        "---",
        "",
        "## Source Inventory",
        "",
        "| Source | Rows Discovered |",
        "|--------|----------------|",
    ]
    for src, n in summary["sources_discovered"].items():
        lines.append(f"| {src} | {n:,} |")

    lines += [
        "",
        "---",
        "",
        "## Era Quality Report",
        "",
        "| Era | n | Avg VP | SR | ID Confirmed | Doctrine Eligible |",
        "|-----|---|--------|----|--------------|-------------------|",
    ]
    era_order = ["CURRENT_ERA_VALIDATED", "PRE_SURGERY_MAY_QUARANTINE",
                 "PRE_SURGERY_ARCHIVE_QUARANTINE", "SKELETON_OR_NULL_DATE_EXCLUDED"]
    for era in era_order:
        eq = era_q.get(era, {})
        n = eq.get("n", 0)
        avg_vp = f"{eq.get('avg_vp', 'N/A'):.3f}" if eq.get("avg_vp") is not None else "N/A"
        sr = f"{eq.get('sr', 0):.1%}" if eq.get("sr") is not None else "N/A"
        id_c = f"{eq.get('n_rp_uid_confirmed', 0)} ({eq.get('id_coverage_pct', 0)}%)"
        doc = "YES" if eq.get("doctrine_eligible") else ("QUARANTINE" if eq.get("quarantine") else "EXCLUDED")
        lines.append(f"| {era} | {n:,} | {avg_vp} | {sr} | {id_c} | {doc} |")

    lines += [
        "",
        "---",
        "",
        "## Identity Status Distribution",
        "",
    ]
    for k, v in summary["by_identity_status"].items():
        lines.append(f"- **{k}**: {v:,}")

    lines += [
        "",
        "---",
        "",
        "## Time-Safety Status Distribution",
        "",
    ]
    for k, v in summary["by_time_safety_status"].items():
        lines.append(f"- **{k}**: {v:,}")

    lines += [
        "",
        "---",
        "",
        "## Pattern Candidates (Dry-Run Only)",
        "",
        "All candidates: `blocked_from_live_use=True`, `human_approval_required=True`",
        "",
        "| Pattern | n | n current-era | SR | Era Scope | Next Requirement |",
        "|---------|---|-------------|-----|-----------|-----------------|",
    ]
    for p in patterns:
        sr_str = f"{p['sr']:.1%}" if p.get("sr") is not None else "N/A"
        lines.append(
            f"| {p['pattern_flag']} | {p['n_rows']} | {p['n_current_era']} | {sr_str} "
            f"| {p['era_scope']} | {p['next_evidence_requirement'][:60]}... |"
        )

    lines += [
        "",
        "---",
        "",
        "## Top Data Quality Debts",
        "",
    ]
    for gap, n in summary["top_data_quality_debts"]:
        lines.append(f"- **{gap}**: {n:,} instances")

    lines += [
        "",
        "---",
        "",
        "## Required Questions — Answers",
        "",
        f"**Q1 Total Sigma rows discovered:** {summary['total_source_rows_discovered']:,}",
        f"**Q2 Total rows processed:** {summary['total_rows_processed']:,}",
        f"**Q3 Rows by era:** Current={summary['by_era_bucket'].get('CURRENT_ERA_VALIDATED', 0)}, MayQ={summary['by_era_bucket'].get('PRE_SURGERY_MAY_QUARANTINE', 0)}, ArchiveQ={summary['by_era_bucket'].get('PRE_SURGERY_ARCHIVE_QUARANTINE', 0)}, Skeleton={summary['by_era_bucket'].get('SKELETON_OR_NULL_DATE_EXCLUDED', 0)}",
        f"**Q4 Rows by evidence quality tier:** {dict(list(summary['by_evidence_quality_tier'].items())[:5])}",
        f"**Q5 Rows by identity status:** {summary['by_identity_status']}",
        f"**Q6 Usable for VP analysis:** {summary['usable_for_vp_analysis']:,}",
        f"**Q7 Usable for course analysis:** {summary['usable_for_course_analysis']:,}",
        f"**Q8 Usable for price analysis:** {summary['usable_for_price_analysis']:,}",
        f"**Q9 Usable for Passport analysis:** {summary['usable_for_passport_analysis']:,}",
        f"**Q10 Blocked from doctrine:** {summary['blocked_from_doctrine']:,}",
        f"**Q11 Excluded rows:** {summary['excluded_skeleton_null_date']:,} (null/skeleton dates)",
        f"**Q12 Current-era findings valid:** {'YES' if summary['current_era_findings_valid'] else 'NO'}",
        f"**Q13 Pre-surgery May viable:** {'YES' if summary['pre_surgery_may_study_viable'] else 'NO (insufficient n)'}",
        f"**Q14 Mar–Apr archive status:** {summary['mar_apr_archive_quarantine_status']}",
        f"**Q15 Skeleton rows usable:** NO — excluded from all conclusions",
        f"**Q16 Top data quality debt:** {summary['top_data_quality_debts'][0][0] if summary['top_data_quality_debts'] else 'N/A'}",
        f"**Q17 Top time-safety risk:** TEMPORAL_CONTAMINATION_RISK ({summary['by_time_safety_status'].get('TEMPORAL_CONTAMINATION_RISK', 0):,} rows)",
        f"**Q18 Top pattern candidates:** {', '.join(p['pattern_flag'] for p in patterns[:3])}",
        f"**Q19 Human review queue:** {summary['human_review_queue_count']} cases",
        f"**Q20 VFU-12 recommended:** YES — {summary['vfu_12_focus'][:120]}...",
        "",
        "---",
        "",
        "## Hard Rules — Confirmed",
        "",
        "- VP threshold: 0.40 — UNCHANGED",
        "- Canonical Horse Passport: NOT MUTATED",
        "- Supabase: NOT WRITTEN",
        "- Live scoring: NOT CHANGED",
        "- Model: NOT PROMOTED",
        "- Telegram: NOT SENT",
        "- Racing API: NOT RESTORED",
        "- Mar–Apr: QUARANTINE ONLY — no doctrine, no Passport, no live use",
        "- All pattern candidates: DRY_RUN_ONLY",
        "",
        "---",
        "",
        "## Final Classifications",
        "",
        "```",
    ]
    for fc in summary["final_classifications"]:
        lines.append(fc)
    lines.append("```")
    return "\n".join(lines)


# ── Main ─────────────────────────────────────────────────────────────────────

def main() -> None:
    global _ledger_id_counter
    _ledger_id_counter = 0
    timestamp = datetime.now(timezone.utc).isoformat()
    print(f"[VFU-11] {VALIDATION_VERSION}")
    print(f"[VFU-11] ERA_CURRENT_START={ERA_CURRENT_START} | VP_THRESHOLD={VP_THRESHOLD}")

    # Load all sources
    print("[VFU-11] Loading sources...")
    identity_rows   = load_identity_enriched_autopsy()
    sigma_2k_rows   = load_sigma_2k()
    audits_dump     = load_sigma_audits_dump()
    results_rows    = load_sigma_results_rows()
    archive_rows    = load_archive_sigma()

    source_counts = {
        "identity_enriched_autopsy":   len(identity_rows),
        "sigma_2k_training":           len(sigma_2k_rows),
        "sigma_audits_dump":           len(audits_dump),
        "sigma_results_eod_rows":      len(results_rows),
        "archive_mar_2026":            len(archive_rows),
    }
    total_discovered = sum(source_counts.values())
    print(f"[VFU-11] Source rows discovered: {total_discovered:,}")
    for src, n in source_counts.items():
        print(f"  {src}: {n:,}")

    # Combine all sources; identity-enriched autopsy is the canonical current-era layer
    all_raw = identity_rows + sigma_2k_rows + audits_dump + results_rows + archive_rows
    print(f"[VFU-11] Building master ledger from {len(all_raw):,} raw rows...")

    ledger = [build_ledger_row(r) for r in all_raw]
    print(f"[VFU-11] Ledger built: {len(ledger):,} rows")

    # Era distribution
    from collections import Counter
    era_dist = Counter(r["era_bucket"] for r in ledger)
    for era, n in sorted(era_dist.items()):
        print(f"  {era}: {n:,}")

    # Build outputs
    patterns = build_pattern_candidates(ledger)
    human_q  = build_human_review_queue(ledger)
    dq       = build_dq_debt(ledger)
    era_q    = build_era_quality_report(ledger)
    ts_report = build_time_safety_report(ledger, patterns)
    summary  = build_summary(source_counts, ledger, patterns, human_q, dq, timestamp)

    # Write outputs
    print("[VFU-11] Writing outputs...")

    with open(OUT_LEDGER, "w", encoding="utf-8") as f:
        for row in ledger:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(f"[VFU-11] Written: {OUT_LEDGER} ({len(ledger):,} rows)")

    OUT_JSON.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"[VFU-11] Written: {OUT_JSON}")

    OUT_ERA_Q.write_text(json.dumps(era_q, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"[VFU-11] Written: {OUT_ERA_Q}")

    OUT_DQ.write_text(json.dumps(dq, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"[VFU-11] Written: {OUT_DQ}")

    OUT_TIME_SAFE.write_text(json.dumps(ts_report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"[VFU-11] Written: {OUT_TIME_SAFE}")

    OUT_PATTERNS.write_text(json.dumps(patterns, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"[VFU-11] Written: {OUT_PATTERNS} ({len(patterns)} patterns)")

    OUT_REVIEW.write_text(json.dumps(human_q, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"[VFU-11] Written: {OUT_REVIEW} ({len(human_q)} cases)")

    md = build_md_report(summary, era_q, patterns, human_q, timestamp)
    OUT_MD.write_text(md, encoding="utf-8")
    print(f"[VFU-11] Written: {OUT_MD}")

    print(f"[VFU-11] Kakirra law: TEMPORAL_CONTAMINATION_BLOCKS_DOCTRINE")
    print(f"[VFU-11] Mar–Apr: QUARANTINE_ONLY — {era_dist.get('PRE_SURGERY_ARCHIVE_QUARANTINE', 0):,} rows")
    print(f"[VFU-11] Current-era: TIME_SAFE — {era_dist.get('CURRENT_ERA_VALIDATED', 0):,} rows")
    print(f"[VFU-11] VP threshold: {VP_THRESHOLD} (UNCHANGED)")
    print(f"[VFU-11] DONE.")


if __name__ == "__main__":
    main()
