"""New Build passport coverage report.

Calls build_current_card_feed(execute=True), then reads the written JSONL
and prints a summary to stdout. Returns exit code 0 on success.

Usage:
    python scripts/ops/new_build_passport_coverage_report.py
"""
from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

# Ensure repo root is on sys.path
_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from new_build_velo.current_card_feed import (  # noqa: E402
    FEED_JSONL_PATH,
    build_current_card_feed,
)


def _read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def main() -> int:
    print("Running build_current_card_feed(execute=True) ...")
    build_current_card_feed(execute=True)

    rows = _read_jsonl(FEED_JSONL_PATH)
    total = len(rows)
    if total == 0:
        print("No feed rows written — nothing to report.")
        return 0

    hits = sum(1 for r in rows if (r.get("passport_live_features") or {}).get("pp_career_runs") is not None)
    misses = total - hits
    pct = round(hits / total * 100, 1) if total else 0.0

    weak_count = sum(1 for r in rows if r.get("weak_profile_runner"))
    weak_pct = round(weak_count / total * 100, 1) if total else 0.0

    # Per-course coverage
    course_hits: Counter[str] = Counter()
    course_total: Counter[str] = Counter()
    for r in rows:
        course = str(r.get("course") or "Unknown")
        course_total[course] += 1
        if (r.get("passport_live_features") or {}).get("pp_career_runs") is not None:
            course_hits[course] += 1

    low_coverage_courses = []
    for course, n in course_total.items():
        h = course_hits[course]
        c_pct = round(h / n * 100, 1) if n else 0.0
        if c_pct < 50.0:
            low_coverage_courses.append((course, h, n, c_pct))
    low_coverage_courses.sort(key=lambda x: x[3])

    # Top 10 missing UIDs (uid present but no passport hit)
    missing_uid_rows = [
        r for r in rows
        if (r.get("passport_live_features") or {}).get("pp_career_runs") is None
        and r.get("rp_uid") not in (None, "")
    ]
    seen_uids: list[str] = []
    for r in missing_uid_rows:
        uid = str(r["rp_uid"])
        if uid not in seen_uids:
            seen_uids.append(uid)
        if len(seen_uids) >= 10:
            break

    print()
    print("=" * 60)
    print("NEW BUILD PASSPORT COVERAGE REPORT")
    print("=" * 60)
    print(f"  Total feed rows     : {total}")
    print(f"  Live passport hits  : {hits}")
    print(f"  Passport misses     : {misses}")
    print(f"  Coverage            : {hits}/{total} = {pct}%")
    print(f"  Weak-profile runners: {weak_count} ({weak_pct}%)")
    print()

    if low_coverage_courses:
        print("Courses with < 50% passport coverage:")
        for course, h, n, c_pct in low_coverage_courses:
            print(f"  {course}: {h}/{n} ({c_pct}%)")
    else:
        print("All courses at >= 50% passport coverage.")
    print()

    if seen_uids:
        print("Top 10 missing UIDs (uid present, no passport hit):")
        for uid in seen_uids:
            print(f"  {uid}")
    else:
        print("No runners with UID had missing passports.")
    print()
    print("Done.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
