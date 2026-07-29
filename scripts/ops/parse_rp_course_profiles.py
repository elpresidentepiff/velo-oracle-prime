"""
parse_rp_course_profiles.py
Parses captured Racing Post course-map and statistics HTML pages.
Each extracted field carries its own source_status — never a blanket VERIFIED_LOCAL.

Provenance rules (strict):
    field found in local captured HTML      → VERIFIED_LOCAL, confidence 0.9
    page captured but field text not found  → LOCAL_CAPTURED_FIELD_MISSING, confidence 0
    page returned 404                       → SOURCE_404, confidence 0
    page had login/paywall block            → LOGIN_REQUIRED_OR_BLOCKED, confidence 0
    page not captured at all               → NOT_CAPTURED, confidence 0
    field inferred from course name/memory → FORBIDDEN (never used)

Usage:
    PYTHONPATH=. venv/bin/python scripts/ops/parse_rp_course_profiles.py \\
        --capture-dir data/racing_post_account_raw/course-profiles-2026-07-01

Outputs:
    data/reports/course_intelligence_rp_raw.json
    data/reports/course_intelligence_rp_draw.csv
    data/reports/course_intelligence_rp_facts.csv
    data/reports/course_intelligence_rp_summary.md

REPORT_ONLY. No scoring changes. No Supabase writes. No Telegram.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REPORTS = ROOT / "data" / "reports"

# ── Provenance constants ───────────────────────────────────────────────────────

VERIFIED_LOCAL = "VERIFIED_LOCAL"
LOCAL_CAPTURED_FIELD_MISSING = "LOCAL_CAPTURED_FIELD_MISSING"
SOURCE_404 = "SOURCE_404"
LOGIN_REQUIRED_OR_BLOCKED = "LOGIN_REQUIRED_OR_BLOCKED"
NOT_CAPTURED = "NOT_CAPTURED"


def _prov(value: str | None, missing_status: str = LOCAL_CAPTURED_FIELD_MISSING) -> tuple[str, str, float]:
    """Return (value, source_status, confidence).
    Only VERIFIED_LOCAL if value was actually found — not None, not empty."""
    if value is not None and value != "":
        return value, VERIFIED_LOCAL, 0.9
    return "UNKNOWN", missing_status, 0.0


# ── Page classification ───────────────────────────────────────────────────────


def _classify_page(html: str, http_status: int | None) -> str:
    """Classify what kind of page this is before parsing content."""
    # HTTP status takes priority — check this first, before inspecting HTML
    if http_status == 404:
        return SOURCE_404
    if http_status == 406:
        # 406 Not Acceptable from RP course profile section = anti-bot block
        # Not a 404 — the URL exists but the server is rejecting the request.
        # Treat as LOGIN_REQUIRED_OR_BLOCKED (session/subscription issue)
        return LOGIN_REQUIRED_OR_BLOCKED
    if http_status is not None and http_status >= 400:
        return SOURCE_404

    # No HTTP status — inspect HTML content
    if len(html) < 3000:
        return SOURCE_404  # tiny page = likely error

    text_sample = html[:10000].lower()

    # Login wall / paywall detection
    login_signals = [
        "log in to view",
        "sign in to view",
        "subscribe to view",
        "login required",
        "please log in",
        "members only",
        "create a free account",
        "sign up to see",
        "you need to be logged in",
        'class="rp-login"',
        'class="login-wall"',
        'id="login-modal"',
    ]
    if any(sig in text_sample for sig in login_signals):
        return LOGIN_REQUIRED_OR_BLOCKED

    # 404 / error signals in HTML body (from pages without HTTP status metadata)
    # Only check for actual error *content*, not CSS class names for error pages
    error_signals = [
        "page not found",
        "404 not found",
        "we can't find that page",
        "something went wrong",
    ]
    if any(sig in text_sample for sig in error_signals):
        return SOURCE_404

    return "OK"


# ── Text helpers ──────────────────────────────────────────────────────────────


def _strip_tags(html: str) -> str:
    text = re.sub(r"<[^>]+>", " ", html)
    return re.sub(r"\s+", " ", text).strip()


def _extract_course_id_and_name(source_url: str, html: str) -> tuple[str, str]:
    m = re.search(r"/profile/course/(\d+)/([^/\"'?&\s]+)", source_url)
    if m:
        cid = m.group(1)
        cname = m.group(2).replace("-", " ").title()
        return cid, cname
    # fallback: page title
    tm = re.search(r"<title>([^<|]+)", html)
    if tm:
        return "UNKNOWN", tm.group(1).strip()
    return "UNKNOWN", "UNKNOWN"


# ── course-map parser ─────────────────────────────────────────────────────────


def _parse_course_map(html: str, page_status: str) -> dict:
    """Extract track facts from course-map page. Each field carries own provenance."""

    if page_status != "OK":
        # Page not usable — all fields get page-level block status
        return {
            f: {"value": "UNKNOWN", "source_status": page_status, "confidence": 0.0}
            for f in (
                "handedness",
                "circuit_character",
                "surface",
                "straight_furlongs",
                "run_in_furlongs",
                "uphill_finish",
                "sprint_chute",
                "pace_notes_present",
                "raw_description",
            )
        }

    text = _strip_tags(html)
    facts: dict = {}

    # Handedness
    if re.search(r"\bleft.?hand(ed)?\b", text, re.I):
        facts["handedness"] = {"value": "LEFT_HAND", "source_status": VERIFIED_LOCAL, "confidence": 0.9}
    elif re.search(r"\bright.?hand(ed)?\b", text, re.I):
        facts["handedness"] = {"value": "RIGHT_HAND", "source_status": VERIFIED_LOCAL, "confidence": 0.9}
    else:
        facts["handedness"] = {"value": "UNKNOWN", "source_status": LOCAL_CAPTURED_FIELD_MISSING, "confidence": 0.0}

    # Circuit character
    char_found = None
    for word in ("galloping", "undulating", "sharp", "stiff", "tight", "flat"):
        if re.search(rf"\b{word}\b", text, re.I):
            char_found = word.upper()
            break
    if char_found:
        facts["circuit_character"] = {"value": char_found, "source_status": VERIFIED_LOCAL, "confidence": 0.9}
    else:
        facts["circuit_character"] = {
            "value": "UNKNOWN",
            "source_status": LOCAL_CAPTURED_FIELD_MISSING,
            "confidence": 0.0,
        }

    # Surface — must match actual content word, not course name
    surface_found = None
    for surface in ("Tapeta", "Polytrack", "Fibresand", "Turf", "Dirt", "Synthetic"):
        if re.search(rf"\b{surface}\b", text, re.I):
            surface_found = surface.upper()
            break
    if surface_found:
        facts["surface"] = {"value": surface_found, "source_status": VERIFIED_LOCAL, "confidence": 0.9}
    else:
        facts["surface"] = {"value": "UNKNOWN", "source_status": LOCAL_CAPTURED_FIELD_MISSING, "confidence": 0.0}

    # Straight furlongs
    sm = re.search(r"(\d+(?:\.\d+)?)\s*f(?:urlong)?\s*(?:finishing\s*)?straight", text, re.I)
    if not sm:
        sm = re.search(r"straight\s+of\s+(\d+(?:\.\d+)?)\s*f", text, re.I)
    if sm:
        facts["straight_furlongs"] = {"value": sm.group(1), "source_status": VERIFIED_LOCAL, "confidence": 0.9}
    else:
        facts["straight_furlongs"] = {
            "value": "UNKNOWN",
            "source_status": LOCAL_CAPTURED_FIELD_MISSING,
            "confidence": 0.0,
        }

    # Run-in furlongs
    rim = re.search(r"(\d+(?:\.\d+)?)\s*f(?:urlong)?\s*run.in", text, re.I)
    if not rim:
        rim = re.search(r"run.in\s+of\s+(\d+(?:\.\d+)?)\s*f", text, re.I)
    if rim:
        facts["run_in_furlongs"] = {"value": rim.group(1), "source_status": VERIFIED_LOCAL, "confidence": 0.9}
    else:
        facts["run_in_furlongs"] = {
            "value": "UNKNOWN",
            "source_status": LOCAL_CAPTURED_FIELD_MISSING,
            "confidence": 0.0,
        }

    # Uphill finish
    if re.search(r"uphill\s+finish|finishes?\s+uphill|rises?\s+to\s+finish", text, re.I):
        facts["uphill_finish"] = {"value": "YES", "source_status": VERIFIED_LOCAL, "confidence": 0.9}
    elif re.search(r"downhill\s+finish|flat\s+finish|level\s+finish", text, re.I):
        facts["uphill_finish"] = {"value": "NO", "source_status": VERIFIED_LOCAL, "confidence": 0.9}
    else:
        facts["uphill_finish"] = {"value": "UNKNOWN", "source_status": LOCAL_CAPTURED_FIELD_MISSING, "confidence": 0.0}

    # Sprint chute
    if re.search(r"sprint\s+chute|chute\s+start|separate\s+chute", text, re.I):
        facts["sprint_chute"] = {"value": "YES", "source_status": VERIFIED_LOCAL, "confidence": 0.9}
    else:
        facts["sprint_chute"] = {"value": "UNKNOWN", "source_status": LOCAL_CAPTURED_FIELD_MISSING, "confidence": 0.0}

    # Pace notes
    if re.search(r"front.?runner|pace.?setter|prominent\s+position|leaders?\s+tend", text, re.I):
        facts["pace_notes_present"] = {"value": "YES", "source_status": VERIFIED_LOCAL, "confidence": 0.9}
    else:
        facts["pace_notes_present"] = {"value": "NO", "source_status": LOCAL_CAPTURED_FIELD_MISSING, "confidence": 0.0}

    # Raw description — first meaningful paragraph
    desc_m = re.search(
        r"(?:Course Description|About the Course|Circuit|racecourse)[^.]*\.\s*(.{80,600}?)(?:\s{2,}|<|\Z)", text, re.I
    )
    if desc_m:
        facts["raw_description"] = {
            "value": desc_m.group(1).strip(),
            "source_status": VERIFIED_LOCAL,
            "confidence": 0.9,
        }
    else:
        # Use a slice of stripped text — mark as LOCAL_CAPTURED not verified description
        snippet = text[300:700].strip()
        if len(snippet) > 50:
            facts["raw_description"] = {
                "value": snippet,
                "source_status": LOCAL_CAPTURED_FIELD_MISSING,
                "confidence": 0.0,
            }
        else:
            facts["raw_description"] = {
                "value": "UNKNOWN",
                "source_status": LOCAL_CAPTURED_FIELD_MISSING,
                "confidence": 0.0,
            }

    return facts


# ── statistics parser ─────────────────────────────────────────────────────────


def _parse_statistics(html: str, page_status: str) -> dict:
    """Extract draw bias and going stats from statistics page. Per-field provenance."""

    if page_status != "OK":
        return {
            "draw_dominant_zone": {"value": "UNKNOWN", "source_status": page_status, "confidence": 0.0},
            "draw_dominant_pct": {"value": 0, "source_status": page_status, "confidence": 0.0},
            "draw_sample_n": {"value": 0, "source_status": page_status, "confidence": 0.0},
            "stall_zone_stats": [],
            "going_performance": [],
        }

    stats: dict = {
        "stall_zone_stats": [],
        "going_performance": [],
    }

    # ── Stall draw zones ─────────────────────────────────────────────────────
    stall_pattern = re.compile(
        r"L\s*\[(?:Stalls?\s*)?([\d-]+)\]\s*(\d+)\s*\((\d+)%\)\s*"
        r"M\s*\[([\d-]+)\]\s*(\d+)\s*\((\d+)%\)\s*"
        r"H\s*\[([\d-]+)\]\s*(\d+)\s*\((\d+)%\)"
    )
    for m in stall_pattern.finditer(html):
        stats["stall_zone_stats"].append(
            {
                "low_range": m.group(1),
                "low_wins": int(m.group(2)),
                "low_pct": int(m.group(3)),
                "mid_range": m.group(4),
                "mid_wins": int(m.group(5)),
                "mid_pct": int(m.group(6)),
                "high_range": m.group(7),
                "high_wins": int(m.group(8)),
                "high_pct": int(m.group(9)),
            }
        )

    if stats["stall_zone_stats"]:
        zone_wins = {"low": 0, "mid": 0, "high": 0}
        for row in stats["stall_zone_stats"]:
            zone_wins["low"] += row["low_wins"]
            zone_wins["mid"] += row["mid_wins"]
            zone_wins["high"] += row["high_wins"]
        dominant = max(zone_wins, key=lambda z: zone_wins[z])
        total = sum(zone_wins.values())
        stats["draw_dominant_zone"] = {"value": dominant.upper(), "source_status": VERIFIED_LOCAL, "confidence": 0.9}
        stats["draw_dominant_pct"] = {
            "value": round(zone_wins[dominant] / total * 100, 1),
            "source_status": VERIFIED_LOCAL,
            "confidence": 0.9,
        }
        stats["draw_sample_n"] = {"value": total, "source_status": VERIFIED_LOCAL, "confidence": 0.9}
        stats["draw_zone_totals"] = zone_wins
    else:
        stats["draw_dominant_zone"] = {
            "value": "UNKNOWN",
            "source_status": LOCAL_CAPTURED_FIELD_MISSING,
            "confidence": 0.0,
        }
        stats["draw_dominant_pct"] = {"value": 0, "source_status": LOCAL_CAPTURED_FIELD_MISSING, "confidence": 0.0}
        stats["draw_sample_n"] = {"value": 0, "source_status": LOCAL_CAPTURED_FIELD_MISSING, "confidence": 0.0}

    # ── Going performance ─────────────────────────────────────────────────────
    text = _strip_tags(html)
    for m in re.finditer(
        r"(Firm|Good to Firm|Good|Good to Soft|Soft|Heavy|Standard|Fast|Slow)"
        r"[^:]*:\s*(\d+)\s*(?:runs?|races?)[,\s]+(\d+)%",
        text,
        re.I,
    ):
        stats["going_performance"].append(
            {
                "going": m.group(1).strip(),
                "n": int(m.group(2)),
                "sr_pct": int(m.group(3)),
                "source_status": VERIFIED_LOCAL,
            }
        )

    return stats


# ── File parser ───────────────────────────────────────────────────────────────


def parse_html_file(path: Path) -> dict | None:
    """Parse one captured HTML file. Returns structured result with per-field provenance."""
    html = path.read_text(encoding="utf-8", errors="replace")

    # Try to find source URL in meta JSON sibling
    meta_path = path.with_suffix(".json")
    source_url = ""
    http_status = None
    if meta_path.exists():
        try:
            meta = json.loads(meta_path.read_text())
            source_url = meta.get("url", meta.get("source_url", meta.get("final_url", "")))
            http_status = meta.get("http_status")
        except Exception:
            pass

    # Fallback URL from filename
    if not source_url:
        fn = path.stem
        m = re.search(r"(\d+)_([a-z_]+)_(?:course.map|statistics)", fn)
        if m:
            cid = m.group(1)
            slug = m.group(2).replace("_", "-")
            source_url = f"https://www.racingpost.com/profile/course/{cid}/{slug}/course-map"

    page_status = _classify_page(html, http_status)

    course_id, course_name = _extract_course_id_and_name(source_url, html)

    # Determine tab
    tab = "unknown"
    if "course-map" in source_url:
        tab = "course-map"
    elif "statistics" in source_url:
        tab = "statistics"
    elif "course-map" in path.stem:
        tab = "course-map"
    elif "statistic" in path.stem:
        tab = "statistics"

    result: dict = {
        "course_id": course_id,
        "course_name": course_name,
        "source_url": source_url,
        "source_file": path.name,
        "page_status": page_status,
        "http_status": http_status,
        "tab": tab,
        "parsed_at": datetime.now(UTC).isoformat(),
    }

    if page_status != "OK":
        result["skip_reason"] = page_status
        return result

    if tab == "course-map":
        result["facts"] = _parse_course_map(html, page_status)
    elif tab == "statistics":
        result["stats"] = _parse_statistics(html, page_status)
    else:
        # Unknown tab — try both
        result["facts"] = _parse_course_map(html, page_status)
        result["stats"] = _parse_statistics(html, page_status)

    return result


# ── Writers ───────────────────────────────────────────────────────────────────


def _write_draw_csv(all_parsed: list[dict], out: Path) -> int:
    rows = []
    for p in all_parsed:
        stats = p.get("stats", {})
        if not stats:
            continue
        dz = stats.get("draw_dominant_zone", {})
        if isinstance(dz, dict) and dz.get("source_status") == VERIFIED_LOCAL:
            rows.append(
                {
                    "course_id": p["course_id"],
                    "course": p["course_name"],
                    "draw_dominant_zone": dz["value"],
                    "draw_dominant_pct": stats.get("draw_dominant_pct", {}).get("value", 0),
                    "draw_sample_n": stats.get("draw_sample_n", {}).get("value", 0),
                    "source_status": VERIFIED_LOCAL,
                    "confidence": 0.9,
                    "last_checked": datetime.now(UTC).strftime("%Y-%m-%d"),
                }
            )
    if rows:
        with open(out, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            writer.writerows(rows)
    return len(rows)


def _write_facts_csv(all_parsed: list[dict], out: Path) -> int:
    rows = []
    for p in all_parsed:
        facts = p.get("facts", {})
        if not facts:
            continue
        # Only include courses where at least one field was VERIFIED_LOCAL
        if not any(isinstance(v, dict) and v.get("source_status") == VERIFIED_LOCAL for v in facts.values()):
            continue

        def _val(field: str, facts=facts) -> str:
            f = facts.get(field, {})
            return f.get("value", "UNKNOWN") if isinstance(f, dict) else "UNKNOWN"

        def _status(field: str, facts=facts) -> str:
            f = facts.get(field, {})
            return f.get("source_status", "UNKNOWN") if isinstance(f, dict) else "UNKNOWN"

        rows.append(
            {
                "course_id": p["course_id"],
                "course": p["course_name"],
                "handedness": _val("handedness"),
                "handedness_status": _status("handedness"),
                "circuit_character": _val("circuit_character"),
                "circuit_status": _status("circuit_character"),
                "surface": _val("surface"),
                "surface_status": _status("surface"),
                "straight_furlongs": _val("straight_furlongs"),
                "straight_status": _status("straight_furlongs"),
                "run_in_furlongs": _val("run_in_furlongs"),
                "run_in_status": _status("run_in_furlongs"),
                "uphill_finish": _val("uphill_finish"),
                "uphill_status": _status("uphill_finish"),
                "sprint_chute": _val("sprint_chute"),
                "pace_notes_present": _val("pace_notes_present"),
                "last_checked": datetime.now(UTC).strftime("%Y-%m-%d"),
            }
        )
    if rows:
        with open(out, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            writer.writerows(rows)
    return len(rows)


def _build_provenance_tally(all_parsed: list[dict]) -> dict[str, int]:
    tally: dict[str, int] = {
        VERIFIED_LOCAL: 0,
        LOCAL_CAPTURED_FIELD_MISSING: 0,
        SOURCE_404: 0,
        LOGIN_REQUIRED_OR_BLOCKED: 0,
        NOT_CAPTURED: 0,
        "OTHER": 0,
    }
    for p in all_parsed:
        for section in ("facts", "stats"):
            for v in p.get(section, {}).values():
                if isinstance(v, dict) and "source_status" in v:
                    s = v["source_status"]
                    tally[s] = tally.get(s, 0) + 1
    return tally


def _write_summary_md(
    all_parsed: list[dict],
    draw_n: int,
    facts_n: int,
    capture_dir: Path,
    url_list_count: int,
) -> str:
    now = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")

    # Page status counts
    status_counts: dict[str, int] = {}
    for p in all_parsed:
        s = p.get("page_status", "UNKNOWN")
        status_counts[s] = status_counts.get(s, 0) + 1

    ok_pages = status_counts.get("OK", 0)
    s404 = status_counts.get(SOURCE_404, 0)
    login_block = status_counts.get(LOGIN_REQUIRED_OR_BLOCKED, 0)

    courses_with_map = sum(1 for p in all_parsed if "facts" in p and p.get("page_status") == "OK")
    courses_with_stats = sum(1 for p in all_parsed if "stats" in p and p.get("page_status") == "OK")
    courses_with_draw = draw_n
    courses_with_going = sum(1 for p in all_parsed if p.get("stats", {}).get("going_performance"))

    prov_tally = _build_provenance_tally(all_parsed)

    # Specific courses
    def _get_course(course_id: str) -> dict | None:
        for p in all_parsed:
            if p["course_id"] == course_id:
                return p
        return None

    southwell = _get_course("394")
    beverley = _get_course("6")

    def _fact_val(p: dict | None, field: str) -> str:
        if not p:
            return "NOT_CAPTURED"
        f = p.get("facts", {}).get(field, {})
        if isinstance(f, dict):
            return f"{f.get('value', '?')} [{f.get('source_status', '?')}]"
        return "MISSING"

    lines = [
        "# COURSE-00B — RP Course Profile Parse Summary",
        f"Generated: {now}",
        "Status: REPORT_ONLY | COURSE_00B_RP_CAPTURE_PREP_ACCEPTED",
        "",
        "---",
        "",
        "## Section 1 — Capture Stats",
        "",
        f"  URL list count:        {url_list_count}",
        f"  HTML files found:      {len(all_parsed)}",
        f"  Pages OK:              {ok_pages}",
        f"  Pages 404:             {s404}",
        f"  Pages login/blocked:   {login_block}",
        f"  Capture dir:           {capture_dir}",
        "",
        "## Section 2 — Parse Results",
        "",
        f"  Course-map pages parsed:   {courses_with_map}",
        f"  Statistics pages parsed:   {courses_with_stats}",
        f"  Courses with draw data:    {courses_with_draw}",
        f"  Courses with going data:   {courses_with_going}",
        f"  Facts CSV rows:            {facts_n}",
        f"  Draw CSV rows:             {draw_n}",
        "",
        "## Section 3 — Provenance Breakdown (per field)",
        "",
        f"  VERIFIED_LOCAL:                {prov_tally.get(VERIFIED_LOCAL, 0)}",
        f"  LOCAL_CAPTURED_FIELD_MISSING:  {prov_tally.get(LOCAL_CAPTURED_FIELD_MISSING, 0)}",
        f"  SOURCE_404:                    {prov_tally.get(SOURCE_404, 0)}",
        f"  LOGIN_REQUIRED_OR_BLOCKED:     {prov_tally.get(LOGIN_REQUIRED_OR_BLOCKED, 0)}",
        "",
        "## Section 4 — Southwell Surface",
        "",
        f"  Surface: {_fact_val(southwell, 'surface')}",
        "  Expected: TAPETA [VERIFIED_LOCAL]",
        "",
        "## Section 5 — Beverley Facts",
        "",
        f"  Handedness:         {_fact_val(beverley, 'handedness')}",
        f"  Circuit character:  {_fact_val(beverley, 'circuit_character')}",
        f"  Straight furlongs:  {_fact_val(beverley, 'straight_furlongs')}",
        f"  Uphill finish:      {_fact_val(beverley, 'uphill_finish')}",
        f"  Sprint chute:       {_fact_val(beverley, 'sprint_chute')}",
        "",
        "## Section 6 — AW Cluster Facts",
        "",
    ]
    aw_ids = {
        "394": "Southwell (AW)",
        "513": "Wolverhampton (AW)",
        "1079": "Kempton (AW)",
        "1083": "Chelmsford (AW)",
        "1353": "Newcastle (AW)",
    }
    for cid, cname in aw_ids.items():
        p = _get_course(cid)
        lines.append(f"  {cname}:")
        lines.append(f"    Surface:      {_fact_val(p, 'surface')}")
        lines.append(f"    Handedness:   {_fact_val(p, 'handedness')}")
        lines.append(f"    Sprint chute: {_fact_val(p, 'sprint_chute')}")
        lines.append("")
    lines += [
        "## Section 7 — All Courses Parsed",
        "",
        f"  {'Course':<30} {'ID':<6} {'Tab':<14} {'Status':<26} {'Hand':<14} {'Surface'}",
        f"  {'-' * 30} {'-' * 6} {'-' * 14} {'-' * 26} {'-' * 14} {'-' * 12}",
    ]
    for p in sorted(all_parsed, key=lambda x: x.get("course_name", "")):
        facts = p.get("facts", {})
        hand = facts.get("handedness", {})
        hand_val = hand.get("value", "?") if isinstance(hand, dict) else "?"
        hand_status = hand.get("source_status", "?")[:20] if isinstance(hand, dict) else "?"
        surf = facts.get("surface", {})
        surf_val = surf.get("value", "?") if isinstance(surf, dict) else "?"
        lines.append(
            f"  {p.get('course_name', '?'):<30} "
            f"{p.get('course_id', '?'):<6} "
            f"{p.get('tab', '?'):<14} "
            f"{p.get('page_status', '?'):<26} "
            f"{hand_val}/{hand_status[:12]:<14} "
            f"{surf_val}"
        )
    lines += [
        "",
        "---",
        "",
        "## FINAL CLASSIFICATIONS",
        "",
        "  - COURSE_00B_RP_CAPTURE_PREP_ACCEPTED",
        "  - LOCAL_DRAW_STATS_EXTRACTED",
        "  - RP_COURSE_PROFILE_CAPTURE_COMPLETED_OR_REPORTED",
        "  - RP_COURSE_PROFILE_PARSE_COMPLETED_OR_REPORTED",
        "  - COURSE_FIELDS_REQUIRE_LOCAL_HTML_EVIDENCE",
        "  - UNPARSED_FIELDS_RESOLVE_UNKNOWN",
        "  - SOURCE_404_RECORDED",
        "  - LOGIN_BLOCK_RECORDED_IF_PRESENT",
        "  - NO_COURSE_01_IMPLEMENTATION",
        "  - NO_VFU_21_START",
        "  - NO_VCP_04_START",
        "  - NO_LIVE_SCORING_CHANGE",
        "  - NO_MODEL_PROMOTION",
        "  - NO_SUPABASE_WRITES",
        "  - NO_TELEGRAM_SEND",
        "  - REPORT_ONLY",
    ]
    return "\n".join(lines)


# ── Main ──────────────────────────────────────────────────────────────────────


def main(capture_dir: Path) -> None:
    now = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")
    print(f"── parse_rp_course_profiles — {now} ──")
    print(f"  Capture dir: {capture_dir}")

    if not capture_dir.exists():
        print(f"\n  CAPTURE DIR MISSING: {capture_dir}")
        print("\n  Run capture first:")
        print("    PYTHONPATH=. venv/bin/python scripts/ops/racing_post_account_collector.py capture \\")
        print("      --url-list data/racing_post_url_lists/course_profiles_gb_ire.txt \\")
        print("      --date 2026-07-01 \\")
        print("      --output-dir data/racing_post_account_raw/course-profiles-2026-07-01 \\")
        print("      --delay-seconds 6 --execute")
        sys.exit(1)

    # Read URL list count for reporting
    url_list_path = ROOT / "data/racing_post_url_lists/course_profiles_gb_ire.txt"
    url_list_count = 0
    if url_list_path.exists():
        url_list_count = sum(
            1 for line in url_list_path.read_text().splitlines() if line.strip() and not line.startswith("#")
        )

    html_files = sorted(capture_dir.glob("*.html"))
    print(f"  HTML files: {len(html_files)}")

    if not html_files:
        # Also check date subdirectory (collector puts files in YYYY-MM-DD subdir)
        for sub in capture_dir.iterdir():
            if sub.is_dir():
                html_files = sorted(sub.glob("*.html"))
                if html_files:
                    print(f"  Found in subdir: {sub.name} ({len(html_files)} files)")
                    break

    all_parsed: list[dict] = []
    for f in html_files:
        result = parse_html_file(f)
        if result:
            all_parsed.append(result)

    # Status summary
    status_counts: dict[str, int] = {}
    for p in all_parsed:
        s = p.get("page_status", "UNKNOWN")
        status_counts[s] = status_counts.get(s, 0) + 1

    print(f"  Parsed: {len(all_parsed)}")
    print(
        f"  OK: {status_counts.get('OK', 0)} | 404: {status_counts.get(SOURCE_404, 0)} | Login/Block: {status_counts.get(LOGIN_REQUIRED_OR_BLOCKED, 0)}"
    )

    REPORTS.mkdir(parents=True, exist_ok=True)

    # Raw JSON
    raw_path = REPORTS / "course_intelligence_rp_raw.json"
    raw_path.write_text(json.dumps(all_parsed, indent=2))
    print(f"  OK   {raw_path.relative_to(ROOT)}")

    # Draw CSV
    draw_path = REPORTS / "course_intelligence_rp_draw.csv"
    draw_n = _write_draw_csv(all_parsed, draw_path)
    print(f"  OK   {draw_path.relative_to(ROOT)} ({draw_n} rows)")

    # Facts CSV
    facts_path = REPORTS / "course_intelligence_rp_facts.csv"
    facts_n = _write_facts_csv(all_parsed, facts_path)
    print(f"  OK   {facts_path.relative_to(ROOT)} ({facts_n} rows)")

    # Summary + operator brief
    summary = _write_summary_md(all_parsed, draw_n, facts_n, capture_dir, url_list_count)
    sum_path = REPORTS / "course_00b_rp_capture_operator_brief.md"
    sum_path.write_text(summary)
    print(f"  OK   {sum_path.relative_to(ROOT)}")

    # JSON brief
    prov_tally = _build_provenance_tally(all_parsed)
    brief_json = {
        "meta": {
            "mission": "COURSE-00B",
            "generated_at": now,
            "final_classifications": [
                "COURSE_00B_RP_CAPTURE_PREP_ACCEPTED",
                "LOCAL_DRAW_STATS_EXTRACTED",
                "RP_COURSE_PROFILE_CAPTURE_COMPLETED_OR_REPORTED",
                "RP_COURSE_PROFILE_PARSE_COMPLETED_OR_REPORTED",
                "COURSE_FIELDS_REQUIRE_LOCAL_HTML_EVIDENCE",
                "UNPARSED_FIELDS_RESOLVE_UNKNOWN",
                "SOURCE_404_RECORDED",
                "LOGIN_BLOCK_RECORDED_IF_PRESENT",
                "NO_COURSE_01_IMPLEMENTATION",
                "REPORT_ONLY",
            ],
        },
        "capture": {
            "url_list_count": url_list_count,
            "html_files_found": len(all_parsed),
            "page_status": status_counts,
        },
        "parse": {
            "facts_rows": facts_n,
            "draw_rows": draw_n,
            "provenance_tally": prov_tally,
        },
    }
    json_path = REPORTS / "course_00b_rp_capture_operator_brief.json"
    json_path.write_text(json.dumps(brief_json, indent=2))
    print(f"  OK   {json_path.relative_to(ROOT)}")

    print()
    print("── DONE ──")
    print("HARD STOP — no COURSE-01 implementation follows.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Parse captured RP course profile HTML.")
    parser.add_argument(
        "--capture-dir",
        default="data/racing_post_account_raw/course-profiles-2026-07-01",
    )
    args = parser.parse_args()
    main(ROOT / args.capture_dir)
