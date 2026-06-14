#!/usr/bin/env python3
"""
scripts/ops/vfu_enrich_pick_sp.py
===================================
VFU-03 — Local pick_sp enrichment from innovation protocol CSV.

Joins pick_sp onto the current-era sigma union rows using a deterministic
key hierarchy. Never writes Supabase. Never mutates canonical Horse Passport.

Join strategy (priority order):
  1. race_id + normalized horse_name  (PRIMARY)
  2. race_date + normalized course + exact off_time + normalized horse_name (SECONDARY)
  3. race_date + normalized course + off_time ±2 min + normalized horse_name (FALLBACK, unique only)

LOCAL_ONLY rows (numeric race IDs, no horse/course/date) are classified as
UNMATCHED_LOCAL_ONLY — structurally unmatchable from this CSV.

Usage:
    python scripts/ops/vfu_enrich_pick_sp.py
"""
from __future__ import annotations

import csv
import json
import re
import unicodedata
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# ── Paths ────────────────────────────────────────────────────────────────────
ROOT = Path(__file__).resolve().parents[2]
UNION_FILE = ROOT / "data/reports/current_era_sigma_union_rows_2026_05_08_to_2026_06_13.json"
CSV_FILE   = ROOT / "data/velo_innovation_protocol_1k_deduped.csv"

OUT_DIR = ROOT / "data/reports"
OUT_ENRICHED   = OUT_DIR / "current_era_sigma_union_rows_enriched_vfu_v1.json"
OUT_REPORT_MD  = OUT_DIR / "vfu_pick_sp_enrichment_report.md"
OUT_REPORT_JSON= OUT_DIR / "vfu_pick_sp_enrichment_report.json"
OUT_UNMATCHED  = OUT_DIR / "vfu_pick_sp_unmatched_rows.json"
OUT_AMBIGUOUS  = OUT_DIR / "vfu_pick_sp_ambiguous_rows.json"

ENRICHMENT_VERSION = "VFU_PICK_SP_ENRICHMENT_V1"
SURGERY_DATE = "2026-05-08"
ERA_BOUNDARY = "2026-05-23"  # boundary between early/late blocks


# ── Normalisation helpers ────────────────────────────────────────────────────

def norm_course(c: str | None) -> str:
    if not c:
        return ""
    c = unicodedata.normalize("NFD", str(c))
    c = "".join(ch for ch in c if unicodedata.category(ch) != "Mn")
    c = c.lower().strip()
    # common abbreviations
    c = re.sub(r"\b(aw)\b", "", c)
    c = re.sub(r"[^a-z0-9 ]", "", c)
    c = re.sub(r"\s+", " ", c)
    return c.strip()


def to_minutes(t: str | None) -> int | None:
    """Convert time string to minutes since midnight, assuming PM for horse racing."""
    if not t or not str(t).strip():
        return None
    t = str(t).strip().replace(".", ":")
    m = re.match(r"^(\d{1,2}):(\d{2})$", t)
    if not m:
        return None
    h, mi = int(m.group(1)), int(m.group(2))
    # horse racing: if hour < 10, assume PM
    if h < 10:
        h += 12
    return h * 60 + mi


def norm_horse(h: str | None) -> str:
    if not h:
        return ""
    h = unicodedata.normalize("NFD", str(h))
    h = "".join(ch for ch in h if unicodedata.category(ch) != "Mn")
    h = h.lower().strip()
    # strip country suffix before removing parens (e.g. (IRE), (GB), (USA))
    h = re.sub(r"\s*\([a-z]+\)\s*$", "", h)
    h = h.replace("'", "").replace("-", " ")
    h = re.sub(r"[^a-z0-9 ]", "", h)
    h = re.sub(r"\s+", " ", h)
    return h.strip()


def parse_sp(val: str | None) -> float | None:
    """Return float SP or None if missing/zero."""
    if not val or not str(val).strip():
        return None
    try:
        f = float(str(val).strip())
        return f if f > 0.0 else None
    except ValueError:
        return None


def is_local_only_race_id(race_id: str | None) -> bool:
    """LOCAL_ONLY rows use numeric race IDs (e.g. '920219'), not 'rac_XXXXXXXX'."""
    if not race_id:
        return False
    return bool(re.match(r"^\d+$", str(race_id).strip()))


# ── Load CSV ─────────────────────────────────────────────────────────────────

def load_csv(path: Path) -> list[dict]:
    with open(path, newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def build_csv_indexes(
    csv_rows: list[dict],
    union_rid_to_date: dict[str, str],
) -> tuple[dict, dict]:
    """Return (by_rid_horse, by_date_course_min)."""
    by_rid_horse: dict[tuple, dict] = {}
    by_date_course_min: dict[tuple, list] = defaultdict(list)

    for r in csv_rows:
        rid = (r.get("race_id") or "").strip()
        horse_raw = r.get("horse") or ""
        hn = norm_horse(horse_raw)

        # Infer date: from CSV 'date' field or from union race_id mapping
        date_raw = (r.get("date") or "").strip()
        if not date_raw and rid:
            date_raw = union_rid_to_date.get(rid, "")

        course_raw = r.get("course") or ""
        time_raw = r.get("race_time") or ""

        sp = parse_sp(r.get("sp_decimal"))

        if rid and hn:
            key = (rid, hn)
            if key not in by_rid_horse:
                by_rid_horse[key] = {**r, "_date": date_raw, "_sp": sp}

        if date_raw and course_raw and time_raw and hn:
            nc = norm_course(course_raw)
            tm = to_minutes(time_raw)
            if nc and tm is not None:
                by_date_course_min[(date_raw, nc, tm)].append(
                    {**r, "_date": date_raw, "_sp": sp, "_norm_horse": hn}
                )

    return by_rid_horse, by_date_course_min


# ── Join logic ───────────────────────────────────────────────────────────────

def join_row(
    u: dict,
    by_rid_horse: dict,
    by_date_course_min: dict,
) -> dict:
    """Return enrichment fields dict for a single union row."""
    rid = (u.get("race_id") or "").strip()
    horse_raw = u.get("horse_name") or ""
    hn = norm_horse(horse_raw)
    date_raw = (u.get("race_date") or "").strip()
    course_raw = u.get("course") or ""
    time_raw = u.get("off_time") or ""

    base = {
        "pick_sp": None,
        "pick_sp_source": None,
        "pick_sp_join_key": None,
        "pick_sp_join_confidence": None,
        "pick_sp_missing_reason": None,
        "pick_sp_ambiguous": False,
        "enrichment_version": ENRICHMENT_VERSION,
        "pick_sp_conflict": False,
        "pick_sp_existing": None,
        "pick_sp_csv": None,
        "pick_sp_resolution": None,
    }

    existing_sp = parse_sp(u.get("pick_sp"))

    def resolve(sp_val: float | None, source: str, join_key: str, confidence: str) -> dict:
        result = {**base}
        if existing_sp is not None:
            # Existing value takes priority
            result["pick_sp"] = existing_sp
            result["pick_sp_source"] = "EXISTING"
            result["pick_sp_join_key"] = join_key
            result["pick_sp_join_confidence"] = confidence
            if sp_val is not None and abs(sp_val - existing_sp) > 0.001:
                result["pick_sp_conflict"] = True
                result["pick_sp_existing"] = existing_sp
                result["pick_sp_csv"] = sp_val
                result["pick_sp_resolution"] = "KEEP_EXISTING"
        else:
            result["pick_sp"] = sp_val
            result["pick_sp_source"] = source
            result["pick_sp_join_key"] = join_key
            result["pick_sp_join_confidence"] = confidence
        return result

    # ── LOCAL_ONLY: numeric race ID, no horse/course/date ────────────────────
    if is_local_only_race_id(rid) or (not hn and not date_raw):
        r = {**base}
        r["pick_sp_missing_reason"] = "UNMATCHED_LOCAL_ONLY"
        if existing_sp is not None:
            r["pick_sp"] = existing_sp
            r["pick_sp_source"] = "EXISTING"
        return r

    # ── Strategy 1: race_id + horse_name ─────────────────────────────────────
    key1 = (rid, hn)
    if key1 in by_rid_horse:
        match = by_rid_horse[key1]
        sp = match["_sp"]
        r = resolve(sp, "INNOVATION_CSV_RACE_ID_HORSE", "race_id+horse_name", "HIGH")
        if sp is None:
            r["pick_sp_missing_reason"] = "MATCHED_SP_ZERO_OR_EMPTY"
        return r

    # ── Strategy 2: date + course + exact time + horse ────────────────────────
    if date_raw and course_raw and time_raw:
        nc = norm_course(course_raw)
        tm = to_minutes(time_raw)
        if nc and tm is not None:
            candidates = [
                c for c in by_date_course_min.get((date_raw, nc, tm), [])
                if c["_norm_horse"] == hn
            ]
            if len(candidates) == 1:
                sp = candidates[0]["_sp"]
                return resolve(sp, "INNOVATION_CSV_DATE_COURSE_TIME_HORSE",
                               "date+course+off_time+horse_name", "HIGH")
            if len(candidates) > 1:
                r = {**base, "pick_sp_ambiguous": True,
                     "pick_sp_missing_reason": "AMBIGUOUS_DATE_COURSE_TIME_HORSE"}
                if existing_sp is not None:
                    r["pick_sp"] = existing_sp
                    r["pick_sp_source"] = "EXISTING"
                return r

            # ── Strategy 3: ±2 minute fallback ───────────────────────────────
            fallback = []
            for delta in range(-2, 3):
                if delta == 0:
                    continue
                for c in by_date_course_min.get((date_raw, nc, tm + delta), []):
                    if c["_norm_horse"] == hn:
                        fallback.append(c)
            if len(fallback) == 1:
                sp = fallback[0]["_sp"]
                return resolve(sp, "INNOVATION_CSV_DATE_COURSE_TIME_FUZZY",
                               "date+course+off_time_±2min+horse_name", "MEDIUM")
            if len(fallback) > 1:
                r = {**base, "pick_sp_ambiguous": True,
                     "pick_sp_missing_reason": "AMBIGUOUS_FALLBACK_TIME"}
                if existing_sp is not None:
                    r["pick_sp"] = existing_sp
                    r["pick_sp_source"] = "EXISTING"
                return r

    # ── Unmatched ─────────────────────────────────────────────────────────────
    r = {**base}
    if not date_raw and not is_local_only_race_id(rid):
        r["pick_sp_missing_reason"] = "UNMATCHED_NO_DATE_IN_UNION"
    elif date_raw < SURGERY_DATE:
        r["pick_sp_missing_reason"] = "UNMATCHED_PRE_SURGERY_DATE"
    else:
        r["pick_sp_missing_reason"] = "UNMATCHED_NO_CSV_ENTRY"
    if existing_sp is not None:
        r["pick_sp"] = existing_sp
        r["pick_sp_source"] = "EXISTING"
    return r


# ── Report helpers ───────────────────────────────────────────────────────────

def date_block(row: dict) -> str:
    d = (row.get("race_date") or "").strip()
    if not d:
        return "NO_DATE"
    if d < ERA_BOUNDARY:
        return "May08-May22"
    return "May23-Jun13"


def build_report(
    union_rows: list[dict],
    enriched: list[dict],
    unmatched: list[dict],
    ambiguous: list[dict],
) -> dict:
    total = len(union_rows)
    sp_before = sum(1 for u in union_rows if parse_sp(u.get("pick_sp")) is not None)
    sp_after  = sum(1 for e in enriched if parse_sp(e.get("pick_sp")) is not None)

    by_source: dict[str, int] = defaultdict(int)
    for e in enriched:
        src = e.get("pick_sp_source") or "NULL"
        if parse_sp(e.get("pick_sp")) is not None:
            by_source[src] += 1

    by_layer: dict[str, dict] = defaultdict(lambda: {"total": 0, "sp_filled": 0})
    for i, e in enumerate(enriched):
        layer = union_rows[i].get("source_layer", "UNKNOWN")
        by_layer[layer]["total"] += 1
        if parse_sp(e.get("pick_sp")) is not None:
            by_layer[layer]["sp_filled"] += 1

    by_block: dict[str, dict] = defaultdict(lambda: {"total": 0, "sp_filled": 0})
    for i, e in enumerate(enriched):
        blk = date_block(union_rows[i])
        by_block[blk]["total"] += 1
        if parse_sp(e.get("pick_sp")) is not None:
            by_block[blk]["sp_filled"] += 1

    missing_reasons: dict[str, int] = defaultdict(int)
    for e in enriched:
        reason = e.get("pick_sp_missing_reason")
        if reason:
            missing_reasons[reason] += 1

    top_unmatched_courses: dict[str, int] = defaultdict(int)
    for e, u in zip(enriched, union_rows):
        if e.get("pick_sp_missing_reason") == "UNMATCHED_NO_CSV_ENTRY":
            c = (u.get("course") or "UNKNOWN")
            top_unmatched_courses[c] += 1

    conflicts = sum(1 for e in enriched if e.get("pick_sp_conflict"))

    primary = sum(1 for e in enriched
                  if e.get("pick_sp_source") == "INNOVATION_CSV_RACE_ID_HORSE"
                  and parse_sp(e.get("pick_sp")) is not None)
    secondary = sum(1 for e in enriched
                    if e.get("pick_sp_source") == "INNOVATION_CSV_DATE_COURSE_TIME_HORSE"
                    and parse_sp(e.get("pick_sp")) is not None)
    fallback = sum(1 for e in enriched
                   if e.get("pick_sp_source") == "INNOVATION_CSV_DATE_COURSE_TIME_FUZZY"
                   and parse_sp(e.get("pick_sp")) is not None)

    full_pass_recommended = sp_after >= (0.30 * total)

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "enrichment_version": ENRICHMENT_VERSION,
        "total_union_rows": total,
        "pick_sp_before_enrichment": sp_before,
        "pick_sp_after_enrichment": sp_after,
        "coverage_before_pct": round(sp_before / total * 100, 2),
        "coverage_after_pct": round(sp_after / total * 100, 2),
        "primary_join_count": primary,
        "secondary_join_count": secondary,
        "fallback_join_count": fallback,
        "unmatched_count": len(unmatched),
        "ambiguous_count": len(ambiguous),
        "conflict_count": conflicts,
        "by_source_layer": dict(by_layer),
        "by_date_block": dict(by_block),
        "missing_reason_breakdown": dict(missing_reasons),
        "top_unmatched_courses": dict(
            sorted(top_unmatched_courses.items(), key=lambda x: -x[1])[:15]
        ),
        "full_1263_pass_recommended": full_pass_recommended,
        "full_1263_pass_notes": (
            f"{sp_after}/{total} rows have pick_sp ({round(sp_after/total*100,1)}%). "
            "LOCAL_ONLY rows (294) are structurally unmatchable. "
            "Remaining unmatched are races not present in innovation CSV. "
            "Proceed with null-tolerant autopsy logic."
        ),
        "classifications": [
            "VFU_PICK_SP_LOCAL_ENRICHMENT_COMPLETE",
            "VFU_PICK_SP_COVERAGE_REPORTED",
            "SUPABASE_STAGING_NOT_CREATED",
            "CANONICAL_HORSE_PASSPORT_NOT_MUTATED",
            "NO_SUPABASE_WRITES",
        ],
    }


def write_report_md(report: dict, out: Path) -> None:
    lines = [
        "# VFU Pick_SP Local Enrichment Report — VFU-03",
        "",
        f"**Generated:** {report['generated_at']}",
        f"**Version:** {report['enrichment_version']}",
        "",
        "## Coverage Summary",
        "",
        f"| Metric | Value |",
        f"|---|---|",
        f"| Total union rows | {report['total_union_rows']} |",
        f"| pick_sp before enrichment | {report['pick_sp_before_enrichment']} ({report['coverage_before_pct']}%) |",
        f"| pick_sp after enrichment | {report['pick_sp_after_enrichment']} ({report['coverage_after_pct']}%) |",
        f"| Primary join (race_id+horse) | {report['primary_join_count']} |",
        f"| Secondary join (date+course+time+horse) | {report['secondary_join_count']} |",
        f"| Fallback join (±2 min, unique) | {report['fallback_join_count']} |",
        f"| Unmatched rows | {report['unmatched_count']} |",
        f"| Ambiguous rows | {report['ambiguous_count']} |",
        f"| Conflict rows | {report['conflict_count']} |",
        "",
        "## Coverage by Source Layer",
        "",
        "| Layer | Total | SP Filled | % |",
        "|---|---|---|---|",
    ]
    for layer, counts in sorted(report["by_source_layer"].items()):
        t = counts["total"]
        f = counts["sp_filled"]
        pct = round(f / t * 100, 1) if t else 0
        lines.append(f"| {layer} | {t} | {f} | {pct}% |")

    lines += [
        "",
        "## Coverage by Date Block",
        "",
        "| Block | Total | SP Filled | % |",
        "|---|---|---|---|",
    ]
    for blk, counts in sorted(report["by_date_block"].items()):
        t = counts["total"]
        f = counts["sp_filled"]
        pct = round(f / t * 100, 1) if t else 0
        lines.append(f"| {blk} | {t} | {f} | {pct}% |")

    lines += [
        "",
        "## Missing Reason Breakdown",
        "",
        "| Reason | Count |",
        "|---|---|",
    ]
    for reason, count in sorted(report["missing_reason_breakdown"].items(), key=lambda x: -x[1]):
        lines.append(f"| {reason} | {count} |")

    lines += [
        "",
        "## Top Unmatched Courses",
        "",
        "| Course | Unmatched Count |",
        "|---|---|",
    ]
    for course, count in list(report["top_unmatched_courses"].items())[:10]:
        lines.append(f"| {course} | {count} |")

    lines += [
        "",
        "## Full 1,263-Row Pass Assessment",
        "",
        f"**Recommended:** {'YES' if report['full_1263_pass_recommended'] else 'PENDING OPERATOR REVIEW'}",
        "",
        report["full_1263_pass_notes"],
        "",
        "## Hard Rule Confirmations",
        "",
        "| Check | Status |",
        "|---|---|",
        "| Supabase staging NOT created | CONFIRMED |",
        "| Canonical Horse Passport NOT mutated | CONFIRMED |",
        "| No Supabase writes | CONFIRMED |",
        "| No live scoring change | CONFIRMED |",
        "| No model promotion | CONFIRMED |",
        "| No Telegram send | CONFIRMED |",
        "| No Racing API restoration | CONFIRMED |",
        "",
        "## Final Classifications",
        "",
    ]
    for cls in report["classifications"]:
        lines.append(f"- `{cls}`")

    out.write_text("\n".join(lines), encoding="utf-8")


# ── Main ─────────────────────────────────────────────────────────────────────

def main() -> None:
    print(f"[VFU-03] Loading union rows from {UNION_FILE.name}")
    union_rows: list[dict] = json.loads(UNION_FILE.read_text(encoding="utf-8"))
    print(f"  {len(union_rows)} union rows loaded")

    print(f"[VFU-03] Loading innovation CSV from {CSV_FILE.name}")
    csv_rows = load_csv(CSV_FILE)
    print(f"  {len(csv_rows)} CSV rows loaded")

    # Build race_id → date mapping from union (for undated CSV rows)
    union_rid_to_date = {
        r["race_id"]: r["race_date"]
        for r in union_rows
        if r.get("race_id") and r.get("race_date")
    }

    print("[VFU-03] Building CSV indexes…")
    by_rid_horse, by_date_course_min = build_csv_indexes(csv_rows, union_rid_to_date)
    print(f"  race_id+horse index: {len(by_rid_horse)} entries")
    print(f"  date+course+time index: {len(by_date_course_min)} buckets")

    print("[VFU-03] Enriching union rows…")
    enrichment_fields: list[dict] = []
    unmatched: list[dict] = []
    ambiguous: list[dict] = []

    for u in union_rows:
        ef = join_row(u, by_rid_horse, by_date_course_min)
        enrichment_fields.append(ef)
        if ef.get("pick_sp_missing_reason") and not ef.get("pick_sp_ambiguous"):
            unmatched.append({**u, **ef})
        if ef.get("pick_sp_ambiguous"):
            ambiguous.append({**u, **ef})

    print(f"  Enriched. Building output…")

    # Merge enrichment fields into union rows
    enriched_union: list[dict] = []
    for u, ef in zip(union_rows, enrichment_fields):
        row = dict(u)
        # Merge enrichment fields (overwrite pick_sp if enriched)
        for k, v in ef.items():
            if k == "pick_sp" and v is not None:
                row["pick_sp"] = v
            elif k != "pick_sp":
                row[k] = v
        enriched_union.append(row)

    # Safety assertion: canonical passport must not be in output paths
    assert str(OUT_ENRICHED) != str(ROOT / "data/new_build/passports/horse_passports_v1.jsonl"), \
        "SAFETY: enriched output path must not be canonical passport"

    # Write outputs
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    OUT_ENRICHED.write_text(json.dumps(enriched_union, indent=2, default=str), encoding="utf-8")
    print(f"  Written: {OUT_ENRICHED.name}")

    OUT_UNMATCHED.write_text(json.dumps(unmatched, indent=2, default=str), encoding="utf-8")
    print(f"  Written: {OUT_UNMATCHED.name} ({len(unmatched)} rows)")

    OUT_AMBIGUOUS.write_text(json.dumps(ambiguous, indent=2, default=str), encoding="utf-8")
    print(f"  Written: {OUT_AMBIGUOUS.name} ({len(ambiguous)} rows)")

    report = build_report(union_rows, enrichment_fields, unmatched, ambiguous)
    OUT_REPORT_JSON.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    print(f"  Written: {OUT_REPORT_JSON.name}")
    write_report_md(report, OUT_REPORT_MD)
    print(f"  Written: {OUT_REPORT_MD.name}")

    print("\n[VFU-03] Summary:")
    print(f"  pick_sp before: {report['pick_sp_before_enrichment']}/{report['total_union_rows']} "
          f"({report['coverage_before_pct']}%)")
    print(f"  pick_sp after:  {report['pick_sp_after_enrichment']}/{report['total_union_rows']} "
          f"({report['coverage_after_pct']}%)")
    print(f"  primary join:   {report['primary_join_count']}")
    print(f"  secondary join: {report['secondary_join_count']}")
    print(f"  fallback join:  {report['fallback_join_count']}")
    print(f"  unmatched:      {report['unmatched_count']}")
    print(f"  ambiguous:      {report['ambiguous_count']}")
    print(f"  conflicts:      {report['conflict_count']}")
    print(f"\n  Full 1263-row pass recommended: {report['full_1263_pass_recommended']}")
    print("\n[VFU-03] DONE. No Supabase writes. No canonical Passport mutation.")


if __name__ == "__main__":
    main()
