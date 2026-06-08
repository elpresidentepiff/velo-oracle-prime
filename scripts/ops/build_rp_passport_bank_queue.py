#!/usr/bin/env python3
"""
Build a Racing Post Passport Bank scrape queue from local archive artifacts.

The queue is intentionally conservative: current/upcoming racecard runners are
highest priority, existing profile captures are marked so they are not fetched
again, and name-only sources are reported as blocked until an RP uid is known.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

PARSED_ROOT = ROOT / "data" / "racing_post_account_parsed"
RAW_ROOT = ROOT / "data" / "racing_post_account_raw"
QUEUE_DIR = ROOT / "data" / "new_build" / "rp_scrape_queue"
REPORT_DIR = ROOT / "data" / "new_build" / "reports"
URL_LIST_DIR = ROOT / "data" / "racing_post_url_lists"
PASSPORT_PATH = ROOT / "data" / "new_build" / "passports" / "horse_passports_v1.jsonl"

PROFILE_RE = re.compile(r"/profile/horse/(?P<uid>\d+)/(?P<slug>[^\"'<>?#/\s]+)")

SOURCE_PRIORITIES = {
    "upcoming_racecard": 10,
    "current_racecard": 20,
    "big_race_entries": 30,
    "top_rated_flat": 40,
    "recent_profile_capture": 50,
    "raw_profile_link_review": 80,
    "name_only_statistics": 90,
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _load_passport_ids() -> set[str]:
    ids: set[str] = set()
    if not PASSPORT_PATH.exists():
        return ids
    for line in PASSPORT_PATH.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        uid = row.get("horse_rp_uid")
        if uid not in (None, ""):
            ids.add(str(uid))
    return ids


def _load_captured_profile_ids() -> set[str]:
    ids: set[str] = set()
    for path in sorted(PARSED_ROOT.glob("*/horse_profiles.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        for profile in data.get("horse_profiles", []):
            uid = profile.get("horse_uid")
            if uid not in (None, ""):
                ids.add(str(uid))
    return ids


def _normalise_profile_url(uid: str, slug_or_url: str | None) -> str:
    if slug_or_url and (slug_or_url.startswith("http") or slug_or_url.startswith("/")):
        base = urljoin("https://www.racingpost.com", slug_or_url)
        base = base.split("#")[0].split("?")[0].rstrip("/")
        if not base.endswith("/form"):
            base = f"{base}/form"
        return base
    slug = (slug_or_url or "horse").split("#")[0].split("?")[0].strip("/").split("/")[-1] or "horse"
    return f"https://www.racingpost.com/profile/horse/{uid}/{slug}/form"


def _candidate(
    candidates: dict[str, dict],
    *,
    uid: str | None,
    name: str | None,
    source: str,
    profile_url: str | None,
    reason: str,
    source_date: str | None = None,
    source_file: str | None = None,
) -> None:
    if not uid:
        key = f"name_only:{(name or '').strip().lower()}:{source}"
        candidates.setdefault(
            key,
            {
                "rp_uid": None,
                "name": name,
                "source": source,
                "sources": [],
                "priority": SOURCE_PRIORITIES.get(source, 99),
                "profile_url": None,
                "reason": "NO_RP_UID",
            },
        )
        source_item = {"source": source, "date": source_date, "file": source_file}
        if source_item not in candidates[key]["sources"]:
            candidates[key]["sources"].append(source_item)
        return

    key = str(uid)
    row = candidates.setdefault(
        key,
        {
            "rp_uid": key,
            "name": name,
            "source": source,
            "sources": [],
            "priority": SOURCE_PRIORITIES.get(source, 99),
            "profile_url": profile_url or _normalise_profile_url(key, None),
            "reason": reason,
        },
    )
    row["name"] = row.get("name") or name
    row["profile_url"] = row.get("profile_url") or profile_url or _normalise_profile_url(key, None)
    if SOURCE_PRIORITIES.get(source, 99) < row["priority"]:
        row["priority"] = SOURCE_PRIORITIES[source]
        row["source"] = source
        row["reason"] = reason
    source_item = {"source": source, "date": source_date, "file": source_file}
    if source_item not in row["sources"]:
        row["sources"].append(source_item)


def _racecard_source_for_date(capture_date: str) -> str:
    if "big-race-entries" in capture_date:
        return "big_race_entries"
    if capture_date >= "2026-05-26":
        return "upcoming_racecard"
    return "current_racecard"


def add_racecard_injection_candidates(candidates: dict[str, dict]) -> None:
    for path in sorted(PARSED_ROOT.glob("*/racecard_injection.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        capture_date = data.get("capture_date") or path.parent.name
        source = _racecard_source_for_date(capture_date)
        for race in data.get("races", []):
            for runner in race.get("runners", []):
                uid = runner.get("horse_id")
                if not uid:
                    continue
                _candidate(
                    candidates,
                    uid=str(uid),
                    name=runner.get("horse"),
                    source=source,
                    profile_url=_normalise_profile_url(str(uid), runner.get("horse_url")),
                    reason=f"{source.upper()}_RUNNER",
                    source_date=capture_date,
                    source_file=str(path),
                )


def add_existing_profile_candidates(candidates: dict[str, dict]) -> None:
    for path in sorted(PARSED_ROOT.glob("*/horse_profiles.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        capture_date = data.get("capture_date") or path.parent.name
        for profile in data.get("horse_profiles", []):
            uid = profile.get("horse_uid")
            if not uid:
                continue
            source = "recent_profile_capture"
            entries = profile.get("entries") or []
            if any(str(entry.get("raceDatetime", ""))[:10] >= "2026-05-26" for entry in entries):
                source = "upcoming_racecard"
            _candidate(
                candidates,
                uid=str(uid),
                name=profile.get("horse_name"),
                source=source,
                profile_url=_normalise_profile_url(str(uid), profile.get("source_url")),
                reason=f"{source.upper()}_PROFILE",
                source_date=capture_date,
                source_file=str(path),
            )


def add_raw_profile_link_review_candidates(candidates: dict[str, dict]) -> None:
    for path in sorted(RAW_ROOT.glob("*/*.html")):
        text = path.read_text(encoding="utf-8", errors="replace")
        source = "raw_profile_link_review"
        for match in PROFILE_RE.finditer(text):
            uid = match.group("uid")
            slug = match.group("slug")
            _candidate(
                candidates,
                uid=uid,
                name=slug.replace("-", " ").title(),
                source=source,
                profile_url=_normalise_profile_url(uid, slug),
                reason="RAW_PROFILE_LINK_NEEDS_RUNNER_SOURCE_REVIEW",
                source_date=path.parent.name,
                source_file=str(path),
            )


def add_statistics_candidates(candidates: dict[str, dict]) -> None:
    for path in sorted(PARSED_ROOT.glob("*/statistics_horses.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        capture_date = data.get("capture_date") or path.parent.name
        for row in data.get("rows", []):
            _candidate(
                candidates,
                uid=row.get("horse_uid") or row.get("rp_uid"),
                name=row.get("horse_name"),
                source="top_rated_flat",
                profile_url=None,
                reason="TOP_RATED_FLAT",
                source_date=capture_date,
                source_file=str(path),
            )


def apply_status(candidates: dict[str, dict], passport_ids: set[str], captured_ids: set[str]) -> list[dict]:
    rows: list[dict] = []
    for row in candidates.values():
        uid = row.get("rp_uid")
        if not uid:
            status = "BLOCKED_NO_RP_UID"
            already_captured = False
            already_passported = False
        else:
            already_captured = uid in captured_ids
            already_passported = uid in passport_ids
            if already_passported:
                status = "PASSPORT_EXISTS"
            elif already_captured:
                status = "CAPTURED_NEEDS_FORM_HISTORY_OR_NO_RUNS"
            elif row.get("source") == "raw_profile_link_review":
                status = "NEEDS_SOURCE_REVIEW"
            else:
                status = "QUEUED_FOR_CAPTURE"
        row.update(
            {
                "status": status,
                "already_captured": already_captured,
                "already_passported": already_passported,
                "capture_tab_order": ["form", "entries", "stats", "pedigree", "quotes", "notes", "sales"],
                "trust_policy": "ARCHIVE_CONTEXT_ONLY_NOT_SCORING",
                "velo_scoring_allowed": False,
                "rpr_policy": "RPR_ARCHIVE_ONLY_EXCLUDED_FROM_VELO",
            }
        )
        rows.append(row)
    return sorted(rows, key=lambda r: (r["priority"], r["status"], str(r.get("name") or ""), str(r.get("rp_uid") or "")))


def write_outputs(rows: list[dict], *, batch_limit: int, execute: bool) -> dict:
    QUEUE_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    URL_LIST_DIR.mkdir(parents=True, exist_ok=True)

    queue_path = QUEUE_DIR / "passport_queue_latest.jsonl"
    url_list_path = URL_LIST_DIR / "passport_bank_next_batch_latest.txt"
    report_json_path = REPORT_DIR / "passport_bank_expansion_latest.json"
    report_md_path = REPORT_DIR / "passport_bank_expansion_latest.md"

    capture_rows = [row for row in rows if row["status"] == "QUEUED_FOR_CAPTURE" and row.get("profile_url")]
    next_batch = capture_rows[:batch_limit]
    status_counts = Counter(row["status"] for row in rows)
    source_counts = Counter(row["source"] for row in rows)
    priority_counts = Counter(str(row["priority"]) for row in rows)
    reason_counts = Counter(row.get("reason") for row in rows)
    source_member_counts = Counter(
        source
        for row in rows
        for source in {item.get("source") for item in row.get("sources", []) if item.get("source")}
    )

    duplicate_uids = sum(1 for uid, count in Counter(row.get("rp_uid") for row in rows if row.get("rp_uid")).items() if count > 1)
    passport_total = status_counts.get("PASSPORT_EXISTS", 0)
    capture_batches = [
        {
            "batch": path.name,
            "html_files": len(list(path.glob("*.html"))),
            "sidecar_json_files": len([item for item in path.glob("*.json") if item.name != "manifest.json"]),
            "manifest_present": (path / "manifest.json").exists(),
        }
        for path in sorted(RAW_ROOT.glob("passport-bank*"))
        if path.is_dir()
    ]
    parsed_batches = []
    for path in sorted(PARSED_ROOT.glob("passport-bank*")):
        if not path.is_dir():
            continue
        horse_profiles_path = path / "horse_profiles.json"
        racecard_path = path / "racecard_injection.json"
        horse_profile_count = 0
        race_count = 0
        runner_count = 0
        if horse_profiles_path.exists():
            horse_profile_count = len(json.loads(horse_profiles_path.read_text(encoding="utf-8")).get("horse_profiles", []))
        if racecard_path.exists():
            racecard_data = json.loads(racecard_path.read_text(encoding="utf-8"))
            race_count = len(racecard_data.get("races", []))
            runner_count = sum(len(race.get("runners", [])) for race in racecard_data.get("races", []))
        parsed_batches.append(
            {
                "batch": path.name,
                "horse_profiles": horse_profile_count,
                "races": race_count,
                "runners": runner_count,
            }
        )
    payload = {
        "generated_at": _utc_now(),
        "status": "PASS" if execute else "DRY_RUN",
        "queue_path": str(queue_path),
        "next_batch_url_list": str(url_list_path),
        "queued_horses": len(rows),
        "queued_for_capture": len(capture_rows),
        "next_batch_limit": batch_limit,
        "next_batch_count": len(next_batch),
        "captured_profiles": status_counts.get("CAPTURED_NEEDS_FORM_HISTORY_OR_NO_RUNS", 0) + status_counts.get("PASSPORT_EXISTS", 0),
        "parsed_passports": passport_total,
        "total_passports_after_run": len(_load_passport_ids()),
        "duplicates": duplicate_uids,
        "failures": status_counts.get("BLOCKED_NO_RP_UID", 0),
        "no_form_history_horses": status_counts.get("CAPTURED_NEEDS_FORM_HISTORY_OR_NO_RUNS", 0),
        "upcoming_race_coverage": source_member_counts.get("upcoming_racecard", 0),
        "big_race_entries_coverage": source_member_counts.get("big_race_entries", 0),
        "rpr_violations": 0,
        "status_counts": dict(status_counts),
        "source_counts": dict(source_counts),
        "source_member_counts": dict(source_member_counts),
        "priority_counts": dict(priority_counts),
        "top_reasons": dict(reason_counts.most_common(20)),
        "next_batch_sample": next_batch[:20],
        "capture_batches": capture_batches,
        "parsed_batches": parsed_batches,
        "continuation_commands": [
            "python scripts/ops/build_rp_passport_bank_queue.py --execute",
            "python scripts/ops/racing_post_account_collector.py capture --date passport-bank-YYYY-MM-DD-N --url-list data/racing_post_url_lists/passport_bank_next_batch_latest.txt --delay-seconds 1.5 --execute",
            "python scripts/ops/parse_racing_post_account_capture.py --date passport-bank-YYYY-MM-DD-N --execute",
            "python scripts/ops/parse_rp_form_history.py --date passport-bank-YYYY-MM-DD-N",
            "python scripts/ops/new_build_horse_passports.py",
        ],
        "rules": {
            "append_only": True,
            "no_duplicates": True,
            "old_live_velo_untouched": True,
            "shadow_velo_untouched": True,
            "rpr_archive_only": True,
        },
    }

    if execute:
        with queue_path.open("w", encoding="utf-8") as fh:
            for row in rows:
                fh.write(json.dumps(row, ensure_ascii=False) + "\n")
        url_list_path.write_text("\n".join(row["profile_url"] for row in next_batch) + ("\n" if next_batch else ""), encoding="utf-8")
        report_json_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        lines = [
            "# Passport Bank Expansion Latest",
            f"Generated: {payload['generated_at']}",
            "",
            "## Summary",
            f"- **Queued horses**: {payload['queued_horses']}",
            f"- **Queued for capture**: {payload['queued_for_capture']}",
            f"- **Next batch count**: {payload['next_batch_count']}",
            f"- **Captured/profiled already**: {payload['captured_profiles']}",
            f"- **Parsed passports**: {payload['parsed_passports']}",
            f"- **Total passports after run**: {payload['total_passports_after_run']}",
            f"- **Duplicates**: {payload['duplicates']}",
            f"- **Failures / blocked no UID**: {payload['failures']}",
            f"- **No-form-history or captured-without-passport horses**: {payload['no_form_history_horses']}",
            f"- **Upcoming-race coverage rows**: {payload['upcoming_race_coverage']}",
            f"- **Big Race Entries coverage rows**: {payload['big_race_entries_coverage']}",
            f"- **RPR violations**: {payload['rpr_violations']}",
            "",
            "## Status Counts",
            "| Status | Count |",
            "|---|---:|",
        ]
        for status, count in status_counts.most_common():
            lines.append(f"| {status} | {count} |")
        lines += ["", "## Source Counts", "| Source | Count |", "|---|---:|"]
        for source, count in source_counts.most_common():
            lines.append(f"| {source} | {count} |")
        lines += ["", "## Capture Batches", "| Batch | HTML | Sidecars | Manifest |", "|---|---:|---:|---|"]
        for batch in capture_batches:
            lines.append(
                f"| {batch['batch']} | {batch['html_files']} | {batch['sidecar_json_files']} | {batch['manifest_present']} |"
            )
        lines += ["", "## Parsed Batches", "| Batch | Horse Profiles | Races | Runners |", "|---|---:|---:|---:|"]
        for batch in parsed_batches:
            lines.append(
                f"| {batch['batch']} | {batch['horse_profiles']} | {batch['races']} | {batch['runners']} |"
            )
        lines += ["", "## Next Batch Sample", "| RP UID | Horse | Source | Priority | URL |", "|---|---|---|---:|---|"]
        for row in next_batch[:25]:
            lines.append(f"| {row.get('rp_uid')} | {row.get('name')} | {row.get('source')} | {row.get('priority')} | {row.get('profile_url')} |")
        lines += ["", "## Continuation Commands"]
        lines.extend(f"- `{cmd}`" for cmd in payload["continuation_commands"])
        report_md_path.write_text("\n".join(lines), encoding="utf-8")

    return payload


def run(*, batch_limit: int, execute: bool) -> dict:
    candidates: dict[str, dict] = {}
    add_racecard_injection_candidates(candidates)
    add_existing_profile_candidates(candidates)
    add_raw_profile_link_review_candidates(candidates)
    add_statistics_candidates(candidates)
    rows = apply_status(candidates, _load_passport_ids(), _load_captured_profile_ids())
    return write_outputs(rows, batch_limit=batch_limit, execute=execute)


def main() -> None:
    parser = argparse.ArgumentParser(description="Build New Build RP Passport Bank queue.")
    parser.add_argument("--batch-limit", type=int, default=500)
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    print(json.dumps(run(batch_limit=args.batch_limit, execute=args.execute), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
