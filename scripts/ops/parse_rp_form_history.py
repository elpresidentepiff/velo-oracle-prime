#!/usr/bin/env python3
"""
parse_rp_form_history.py
========================
Phase 1 — Race Shape Intelligence: Extract per-horse run history from
already-captured Racing Post profile HTML files.

Parses the hp-formTable from each profile and extracts:
  - date, course, distance, going
  - finishing position, field size, beaten margin, winner info
  - SP, jockey (name + uid), TS, RPR, OR ratings
  - result URL and video replay link

Writes to:
  data/race_shape/form_history_YYYY-MM-DD.json    (per-date capture batch)
  data/race_shape/form_history_latest.json         (latest build)

SHADOW ONLY. Archive-context only. Never enters VELO scoring.

Usage:
    source venv/bin/activate
    PYTHONPATH=. python scripts/ops/parse_rp_form_history.py --date 2026-05-26
    PYTHONPATH=. python scripts/ops/parse_rp_form_history.py --date 2026-05-26 --date 2026-05-27
"""

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

try:
    from bs4 import BeautifulSoup
except ImportError:
    print("ERROR: beautifulsoup4 required. pip install beautifulsoup4 lxml")
    sys.exit(1)

OUT_DIR = ROOT / "data" / "race_shape"
PARSED_DIR = ROOT / "data" / "racing_post_account_parsed"
RAW_DIR = ROOT / "data" / "racing_post_account_raw"


TRUST_POLICY = "ARCHIVE_CONTEXT_ONLY_NOT_SCORING"
VELO_SCORING_ALLOWED = False


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _parse_date_str(date_str: str) -> str:
    """Parse RP date format '23Apr26' → '2026-04-23'."""
    try:
        d = datetime.strptime(date_str.strip(), "%d%b%y")
        return d.strftime("%Y-%m-%d")
    except Exception:
        return date_str


def _parse_position_cell(text: str) -> dict:
    """
    Parse position cell like '2 / 6 btn 2L Raft Up 9-2' or '1 / 12 by ¾L Forever Noah 11-1'.
    Returns: {position, field_size, beaten_margin, winner_name, winner_sp, result_type}
    """
    text = text.strip()
    result = {
        "position": None,
        "field_size": None,
        "beaten_margin": None,
        "winner_name": None,
        "winner_sp": None,
        "result_type": None,
    }

    # Match "N / M by/btn ..."
    m = re.match(r"^(\d+)\s*/\s*(\d+)\s*(by|btn)\s*(.*)", text)
    if m:
        result["position"] = int(m.group(1))
        result["field_size"] = int(m.group(2))
        rest = m.group(4).strip()
        result["result_type"] = "WIN" if result["position"] == 1 else "PLACED" if result["position"] <= 3 else "LOSS"

        # Extract beaten margin (first token before winner name)
        # Patterns: "2L", "nk", "hd", "¾L", "3¼L", "sht-hd"
        margin_m = re.match(r"^([^\s]+)\s*(.*)", rest)
        if margin_m:
            margin = margin_m.group(1)
            remainder = margin_m.group(2).strip()
            if result["position"] == 1:
                result["beaten_margin"] = margin  # margin by which winner won
            else:
                result["beaten_margin"] = margin  # how far beaten
            # Remainder should be "WinnerName SP" or "WinnerName SPFraction"
            sp_m = re.match(r"^(.*?)\s+(\d+[-/]\d+|\d+/\d+|evs|Evs)$", remainder)
            if sp_m:
                result["winner_name"] = sp_m.group(1).strip()
                result["winner_sp"] = sp_m.group(2)
            elif remainder:
                result["winner_name"] = remainder

    return result


def _parse_jockey_cell(cell) -> dict:
    """Extract jockey name and RP uid from jockey cell."""
    link = cell.find("a")
    if link:
        href = link.get("href", "")
        uid_m = re.search(r"/profile/jockey/(\d+)/", href)
        name = link.get_text(" ", strip=True).replace("right", "").strip()
        return {
            "jockey_name": name,
            "jockey_rp_uid": int(uid_m.group(1)) if uid_m else None,
            "jockey_profile_url": href,
        }
    text = cell.get_text(" ", strip=True).replace("right", "").strip()
    return {"jockey_name": text, "jockey_rp_uid": None, "jockey_profile_url": None}


def _parse_course_cell(cell) -> dict:
    """Extract course name and RP course uid from course cell."""
    link = cell.find("a")
    course_uid = None
    course_key = None
    if link:
        href = link.get("href", "")
        uid_m = re.search(r"/profile/course/(\d+)/([^/\s]+)", href)
        if uid_m:
            course_uid = int(uid_m.group(1))
            course_key = uid_m.group(2)
    text = cell.get_text(" ", strip=True)
    # Clean up the messy text: "Southwell (AW) Sth right 6f St C 6Hc 4K"
    # Remove direction arrows and extract just course name
    name_m = re.match(r"^([A-Za-z\s\(\)]+?)(?:\s+(?:Sth|Rhs|Lhs|right|left|NHF|C\s+\d+|\d+f))", text)
    course_name = name_m.group(1).strip() if name_m else text.split("right")[0].strip()
    return {
        "course_name": course_name,
        "course_rp_uid": course_uid,
        "course_key": course_key,
    }


def _parse_date_cell(cell) -> dict:
    """Extract race date and result/video links from date cell."""
    links = cell.find_all("a")
    date_text = cell.get_text(" ", strip=True)
    # Remove icon labels
    for remove in ["hollow video icon right", "right", "left"]:
        date_text = date_text.replace(remove, "").strip()

    date_str = _parse_date_str(date_text.strip())

    video_url = None
    result_url = None
    for a in links:
        href = a.get("href", "")
        if "fullReplay" in href:
            video_url = href
        elif "/results/" in href:
            result_url = href

    return {"race_date": date_str, "video_url": video_url, "result_url": result_url}


def _parse_weight_cell(text: str) -> dict:
    """Parse weight like '8-12 p' or '9-8 t' → stones-lbs + gear."""
    text = text.strip()
    gear = None
    if " " in text:
        parts = text.split()
        weight_str = parts[0]
        gear = " ".join(parts[1:]) if len(parts) > 1 else None
    else:
        weight_str = text

    lbs_total = None
    try:
        if "-" in weight_str:
            st, lb = weight_str.split("-")
            lbs_total = int(st) * 14 + int(lb)
    except Exception:
        pass

    return {"weight_raw": text, "weight_lbs": lbs_total, "gear": gear}


def _parse_sp(sp_str: str) -> float | None:
    """Convert fractional SP like '9/2' to decimal."""
    try:
        sp_str = sp_str.strip().lower()
        if sp_str in ("evs", "evens"):
            return 2.0
        if "/" in sp_str:
            n, d = sp_str.split("/")
            return round(int(n) / int(d) + 1, 2)
        return float(sp_str)
    except Exception:
        return None


def parse_form_history_from_html(html_path: str, horse_name: str, horse_uid: int) -> list[dict]:
    """
    Parse all form history rows from a captured RP profile HTML file.
    Returns list of run records, most recent first.
    """
    html = Path(html_path).read_text(encoding="utf-8")
    soup = BeautifulSoup(html, "lxml")

    date_wrappers = soup.select(".hp-formTable__dateWrapper")
    runs = []

    for dw in date_wrappers:
        row = dw.find_parent("tr")
        if not row:
            continue
        cells = row.find_all("td")
        if len(cells) < 8:
            continue

        try:
            date_info = _parse_date_cell(cells[0])
            course_info = _parse_course_cell(cells[1])
            distance = cells[2].get_text(strip=True)
            going = cells[3].get_text(strip=True)
            weight_info = _parse_weight_cell(cells[4].get_text(strip=True))
            pos_text = cells[5].get_text(" ", strip=True).replace("right", "").strip()
            pos_info = _parse_position_cell(pos_text)
            sp_str = cells[6].get_text(strip=True)
            jockey_info = _parse_jockey_cell(cells[7])

            ts_raw = cells[8].get_text(strip=True) if len(cells) > 8 else ""
            rpr_raw = cells[9].get_text(strip=True) if len(cells) > 9 else ""
            or_raw = cells[10].get_text(strip=True) if len(cells) > 10 else ""

            def _safe_int(s):
                try:
                    return int(s.replace("—", "").strip()) if s and s not in ("—", "-", "") else None
                except Exception:
                    return None

            run = {
                "trust_policy": TRUST_POLICY,
                "velo_scoring_allowed": VELO_SCORING_ALLOWED,
                "horse_name": horse_name,
                "horse_rp_uid": horse_uid,
                "race_date": date_info["race_date"],
                "course_name": course_info["course_name"],
                "course_rp_uid": course_info["course_rp_uid"],
                "course_key": course_info["course_key"],
                "distance": distance,
                "going": going,
                "weight_raw": weight_info["weight_raw"],
                "weight_lbs": weight_info["weight_lbs"],
                "gear": weight_info["gear"],
                "position": pos_info["position"],
                "field_size": pos_info["field_size"],
                "beaten_margin": pos_info["beaten_margin"],
                "winner_name": pos_info["winner_name"],
                "winner_sp": pos_info["winner_sp"],
                "result_type": pos_info["result_type"],
                "sp_raw": sp_str,
                "sp_dec": _parse_sp(sp_str),
                "jockey_name": jockey_info["jockey_name"],
                "jockey_rp_uid": jockey_info["jockey_rp_uid"],
                "ts_rating": _safe_int(ts_raw),
                "rpr_rating": _safe_int(rpr_raw),
                "or_rating": _safe_int(or_raw),
                "result_url": date_info["result_url"],
                "video_url": date_info["video_url"],
            }
            runs.append(run)
        except Exception as e:
            continue

    return runs


def build_form_history_for_date(capture_date: str) -> dict:
    """Process all captured profiles for a given capture_date."""
    profiles_path = PARSED_DIR / capture_date / "horse_profiles.json"
    if not profiles_path.exists():
        raise FileNotFoundError(f"No parsed profiles for {capture_date}: {profiles_path}")

    profiles_data = json.loads(profiles_path.read_text(encoding="utf-8"))
    profiles = profiles_data.get("horse_profiles", [])

    all_runs: list[dict] = []
    horse_summaries = []
    parsed_count = 0
    fail_count = 0

    for prof in profiles:
        html_path = prof.get("html_path")
        horse_name = prof.get("horse_name", "")
        horse_uid = prof.get("horse_uid")
        if not html_path or not Path(html_path).exists():
            fail_count += 1
            continue

        try:
            runs = parse_form_history_from_html(html_path, horse_name, horse_uid)
            all_runs.extend(runs)
            parsed_count += 1
            horse_summaries.append({
                "horse": horse_name,
                "horse_uid": horse_uid,
                "runs_found": len(runs),
                "date_range": f"{runs[-1]['race_date']} → {runs[0]['race_date']}" if runs else "none",
            })
            print(f"  {horse_name}: {len(runs)} runs")
        except Exception as e:
            print(f"  [FAIL] {horse_name}: {e}")
            fail_count += 1

    return {
        "capture_date": capture_date,
        "generated_at": _utc_now(),
        "trust_policy": TRUST_POLICY,
        "velo_scoring_allowed": VELO_SCORING_ALLOWED,
        "horses_processed": parsed_count,
        "horses_failed": fail_count,
        "total_runs": len(all_runs),
        "horse_summaries": horse_summaries,
        "runs": all_runs,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", action="append", dest="dates", required=True,
                        help="Capture date(s) to process (YYYY-MM-DD). Can specify multiple.")
    args = parser.parse_args()

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    all_results = []
    for date in args.dates:
        print(f"\n=== Parsing form history for {date} ===")
        try:
            result = build_form_history_for_date(date)
            out_path = OUT_DIR / f"form_history_{date}.json"
            out_path.write_text(json.dumps(result, indent=2))
            print(f"\n  Horses: {result['horses_processed']} | Runs: {result['total_runs']}")
            print(f"  Saved: {out_path}")
            all_results.append(result)
        except Exception as e:
            print(f"  ERROR: {e}")

    # Write latest
    if all_results:
        combined = all_results[-1] if len(all_results) == 1 else {
            "dates": args.dates,
            "generated_at": _utc_now(),
            "trust_policy": TRUST_POLICY,
            "velo_scoring_allowed": VELO_SCORING_ALLOWED,
            "batches": len(all_results),
            "total_runs": sum(r["total_runs"] for r in all_results),
            "total_horses": sum(r["horses_processed"] for r in all_results),
        }
        (OUT_DIR / "form_history_latest.json").write_text(json.dumps(combined, indent=2))
        print(f"\nLatest written: {OUT_DIR}/form_history_latest.json")


if __name__ == "__main__":
    main()
