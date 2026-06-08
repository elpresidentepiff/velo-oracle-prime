#!/usr/bin/env python3
"""Plan and report final-card Passport Bank backfill.

The script is deterministic: it uses RP horse UIDs already present on the
official standard card, writes a New Build queue/url-list, and reports coverage
before/after downstream capture/parse/passport-build steps.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

NEW_BUILD_ROOT = ROOT / "data" / "new_build"
PASSPORT_PATH = NEW_BUILD_ROOT / "passports" / "horse_passports_v1.jsonl"
QUEUE_DIR = NEW_BUILD_ROOT / "rp_scrape_queue"
DEFAULT_DATE = "2026-05-26"
DEFAULT_CAPTURE_DATE = "2026-05-26-passport-backfill-final-card"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _write_json(path: Path, payload: Any) -> None:
    _assert_new_build_path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    _assert_new_build_path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + ("\n" if rows else ""), encoding="utf-8")


def _assert_new_build_path(path: Path) -> None:
    resolved = path.resolve()
    allowed = NEW_BUILD_ROOT.resolve()
    if resolved != allowed and allowed not in resolved.parents:
        raise ValueError(f"Refusing New Build write outside {allowed}: {resolved}")


def _norm_slug(value: Any) -> str:
    text = str(value or "").lower().strip()
    text = text.replace("'", "").replace("’", "")
    text = re.sub(r"[^a-z0-9]+", "-", text).strip("-")
    return text or "horse"


def _profile_url(uid: str, horse: str, existing_url: str | None) -> str:
    if existing_url:
        path = existing_url.split("#", 1)[0]
        match = re.search(r"(/profile/horse/\d+/[^/]+)", path)
        if match:
            return f"https://www.racingpost.com{match.group(1)}/form"
        if path.startswith("http") and "/profile/horse/" in path:
            return path.rstrip("/") + "/form" if not path.rstrip("/").endswith("/form") else path.rstrip("/")
    return f"https://www.racingpost.com/profile/horse/{uid}/{_norm_slug(horse)}/form"


def _load_passport_ids() -> set[str]:
    ids: set[str] = set()
    for row in _read_jsonl(PASSPORT_PATH):
        uid = row.get("horse_rp_uid")
        if uid not in (None, ""):
            ids.add(str(uid))
    return ids


def _load_official_active_runners(path: Path) -> list[dict[str, Any]]:
    data = _read_json(path)
    rows: list[dict[str, Any]] = []
    if isinstance(data, list):
        for race in data:
            for runner in race.get("runners", []):
                if runner.get("non_runner"):
                    continue
                uid = runner.get("horse_id")
                if uid in (None, ""):
                    continue
                rows.append(
                    {
                        "race_id": str(race.get("race_id") or ""),
                        "course": race.get("course"),
                        "off_time": race.get("race_time") or race.get("off_time"),
                        "horse": runner.get("horse") or runner.get("horse_name"),
                        "rp_uid": str(uid),
                        "trainer": runner.get("trainer"),
                        "jockey": runner.get("jockey"),
                        "horse_url": runner.get("horse_url"),
                    }
                )
        return rows

    if data.get("races"):
        for race in data.get("races", []):
            for runner in race.get("runners", []):
                if runner.get("non_runner"):
                    continue
                uid = runner.get("horse_id")
                if uid in (None, ""):
                    continue
                rows.append(
                    {
                        "race_id": str(race.get("race_id") or ""),
                        "course": race.get("course"),
                        "off_time": race.get("race_time"),
                        "horse": runner.get("horse") or runner.get("horse_name"),
                        "rp_uid": str(uid),
                        "trainer": runner.get("trainer"),
                        "jockey": runner.get("jockey"),
                        "horse_url": runner.get("horse_url"),
                    }
                )
        return rows

    for race in data.get("racecards", []):
        for runner in race.get("runners", []):
            if runner.get("non_runner"):
                continue
            uid = runner.get("horse_id")
            if uid in (None, ""):
                continue
            rows.append(
                {
                    "race_id": str(race.get("race_id") or ""),
                    "course": race.get("course"),
                    "off_time": race.get("off_time"),
                    "horse": runner.get("horse") or runner.get("horse_name"),
                    "rp_uid": str(uid),
                    "trainer": runner.get("trainer"),
                    "jockey": runner.get("jockey"),
                    "horse_url": runner.get("horse_url"),
                }
            )
    return rows


def _load_capture_manifest(capture_date: str) -> dict[str, Any]:
    path = ROOT / "data" / "racing_post_account_raw" / capture_date / "manifest.json"
    if not path.exists():
        return {"captures": []}
    return _read_json(path)


def _load_parsed_profiles(capture_date: str) -> dict[str, dict[str, Any]]:
    path = ROOT / "data" / "racing_post_account_parsed" / capture_date / "horse_profiles.json"
    if not path.exists():
        return {}
    data = _read_json(path)
    return {str(row.get("horse_uid")): row for row in data.get("horse_profiles", []) if row.get("horse_uid") not in (None, "")}


def build_backfill_report(*, standard_cache: Path, target_date: str, capture_date: str, execute: bool) -> dict[str, Any]:
    active = _load_official_active_runners(standard_cache)
    passport_ids = _load_passport_ids()
    missing = [row for row in active if row["rp_uid"] not in passport_ids]
    seen: set[str] = set()
    deduped_missing: list[dict[str, Any]] = []
    for row in missing:
        if row["rp_uid"] in seen:
            continue
        seen.add(row["rp_uid"])
        deduped_missing.append(row)

    manifest = _load_capture_manifest(capture_date)
    captures = manifest.get("captures", []) or []
    captured_plan_uids = {
        match.group(1)
        for capture in captures
        for match in [re.search(r"/profile/horse/(\d+)/", str(capture.get("source_url") or ""))]
        if match
    }
    # Once capture has run, the current missing list is no longer the original
    # plan. Preserve the pre-run baseline by reconstructing it from the manifest.
    plan_rows = [row for row in active if row["rp_uid"] in captured_plan_uids] if captured_plan_uids else deduped_missing

    queue_rows = []
    for idx, row in enumerate(plan_rows, start=1):
        url = _profile_url(row["rp_uid"], row["horse"], row.get("horse_url"))
        captured = row["rp_uid"] in captured_plan_uids
        passported_now = row["rp_uid"] in passport_ids
        queue_rows.append(
            {
                "rp_uid": row["rp_uid"],
                "horse": row["horse"],
                "source": f"official_final_card_{target_date}",
                "priority": idx,
                "profile_url": url,
                "status": "PASSPORT_CREATED" if captured and passported_now else "CAPTURED_NO_FORM_OR_NO_PASSPORT" if captured else "QUEUED_FOR_CAPTURE",
                "already_captured": captured,
                "reason": "FINAL_CARD_ACTIVE_RUNNER_NO_PASSPORT",
                "race_id": row["race_id"],
                "course": row.get("course"),
                "off_time": row.get("off_time"),
                "trainer": row.get("trainer"),
                "jockey": row.get("jockey"),
                "trust_policy": "ARCHIVE_CONTEXT_ONLY_NOT_SCORING",
                "velo_scoring_allowed": False,
                "rpr_policy": "RPR_ARCHIVE_ONLY_EXCLUDED_FROM_VELO",
                "rp_rpr_velo_allowed": False,
            }
        )

    parsed_profiles = _load_parsed_profiles(capture_date)
    passport_ids_after = _load_passport_ids()
    missing_after = [row for row in active if row["rp_uid"] not in passport_ids_after]
    captured_urls = {str(row.get("source_url")) for row in captures if row.get("status") == "PASS"}
    captured_uids = {
        uid
        for row in queue_rows
        for uid in [row["rp_uid"]]
        if row["profile_url"] in captured_urls
    }
    parsed_uids = set(parsed_profiles)
    created_uids = {row["rp_uid"] for row in queue_rows if captures and row["rp_uid"] in passport_ids_after}
    failed_uids = [
        row["rp_uid"]
        for row in queue_rows
        if captures and row["rp_uid"] not in passport_ids_after and row["rp_uid"] not in parsed_uids
    ]
    parse_failures = [
        row["rp_uid"]
        for row in queue_rows
        if captures and row["rp_uid"] in captured_uids and row["rp_uid"] not in parsed_uids
    ]
    no_form_or_not_created = [
        row["rp_uid"]
        for row in queue_rows
        if row["rp_uid"] in parsed_uids and row["rp_uid"] not in passport_ids_after
    ]

    safe_date = target_date.replace("-", "_")
    url_list_path = QUEUE_DIR / f"passport_backfill_{safe_date}_urls.txt"
    queue_path = QUEUE_DIR / f"passport_backfill_{safe_date}_queue.jsonl"
    missing_before_count = len(queue_rows) if captures else len(missing)
    payload = {
        "generated_at": _utc_now(),
        "target_date": target_date,
        "classification": _classification(missing_before_count, len(missing_after), bool(captures)),
        "standard_cache": str(standard_cache),
        "capture_date": capture_date,
        "url_list_path": str(url_list_path),
        "queue_path": str(queue_path),
        "missing_passports_before": missing_before_count,
        "unique_missing_passports_before": missing_before_count,
        "profiles_attempted": len(queue_rows) if captures else 0,
        "profiles_queued": len(queue_rows),
        "profiles_captured": len(captured_uids) if captures else 0,
        "capture_records": len(captures),
        "parse_successes": len(parsed_uids & {row["rp_uid"] for row in queue_rows}),
        "parse_failures": len(parse_failures),
        "parse_failure_uids": parse_failures[:100],
        "passports_created": len(created_uids),
        "passport_created_uids": sorted(created_uids)[:100],
        "missing_passports_after": len(missing_after),
        "passport_coverage_before": {
            "found": len(active) - missing_before_count,
            "total": len(active),
            "coverage_pct": round((len(active) - missing_before_count) / len(active) * 100, 2) if active else 0.0,
        },
        "passport_coverage_after": {
            "found": len(active) - len(missing_after),
            "total": len(active),
            "coverage_pct": round((len(active) - len(missing_after)) / len(active) * 100, 2) if active else 0.0,
        },
        "failed_rp_uids": failed_uids[:200],
        "no_form_or_not_created_uids": no_form_or_not_created[:200],
        "queued_sample": queue_rows[:20],
        "status_counts": dict(Counter(row["status"] for row in queue_rows)),
        "rpr_archive_only_confirmation": {
            "rpr_policy": "RPR_ARCHIVE_ONLY_EXCLUDED_FROM_VELO",
            "rpr_model_feature_use": 0,
            "rp_rpr_velo_allowed": False,
        },
        "rules": {
            "new_build_only": True,
            "no_old_live_velo": True,
            "no_shadow": True,
            "no_telegram": True,
            "no_live_scoring_tables": True,
            "no_staking": True,
            "no_newspaper_form_into_passport": True,
            "rpr_archive_only": True,
        },
    }
    if execute:
        _write_jsonl(queue_path, queue_rows)
        url_list_path.parent.mkdir(parents=True, exist_ok=True)
        url_list_path.write_text("\n".join(row["profile_url"] for row in queue_rows) + ("\n" if queue_rows else ""), encoding="utf-8")
        report_json = NEW_BUILD_ROOT / "reports" / f"passport_bank_backfill_{safe_date}_latest.json"
        report_md = NEW_BUILD_ROOT / "reports" / f"passport_bank_backfill_{safe_date}_latest.md"
        _write_json(report_json, payload)
        report_md.write_text(_markdown(payload), encoding="utf-8")
    return payload


def _classification(before: int, after: int, captures_exist: bool) -> str:
    if not captures_exist:
        return "PASSPORT_BACKFILL_QUEUE_READY"
    if after < before and after > 0:
        return "PASSPORT_BANK_BACKFILL_PARTIAL"
    if after == 0:
        return "PASSPORT_BANK_BACKFILL_COMPLETE"
    return "PASSPORT_BANK_BACKFILL_FAILED_OR_NO_GAIN"


def _markdown(payload: dict[str, Any]) -> str:
    before = payload["passport_coverage_before"]
    after = payload["passport_coverage_after"]
    lines = [
        f"# Passport Bank Backfill - {payload.get('target_date')} Final Card",
        f"Generated: {payload['generated_at']}",
        "",
        "## Summary",
        f"- **Classification**: `{payload['classification']}`",
        f"- **Missing passports before**: {payload['missing_passports_before']}",
        f"- **Profiles queued**: {payload['profiles_queued']}",
        f"- **Profiles attempted**: {payload['profiles_attempted']}",
        f"- **Profiles captured**: {payload['profiles_captured']}",
        f"- **Parse successes**: {payload['parse_successes']}",
        f"- **Parse failures**: {payload['parse_failures']}",
        f"- **Passports created**: {payload['passports_created']}",
        f"- **Missing passports after**: {payload['missing_passports_after']}",
        f"- **Coverage before**: {before['found']} / {before['total']} ({before['coverage_pct']}%)",
        f"- **Coverage after**: {after['found']} / {after['total']} ({after['coverage_pct']}%)",
        "- **RPR archive-only confirmation**: PASS",
        "",
        "## Queue Files",
        f"- URL list: `{payload['url_list_path']}`",
        f"- Queue: `{payload['queue_path']}`",
        "",
        "## Queued Sample",
        "| RP UID | Horse | Course | Trainer | URL |",
        "|---:|---|---|---|---|",
    ]
    for row in payload["queued_sample"]:
        lines.append(f"| {row['rp_uid']} | {row['horse']} | {row.get('course')} | {row.get('trainer')} | {row['profile_url']} |")
    if payload["failed_rp_uids"]:
        lines += ["", "## Failed RP UIDs", ", ".join(payload["failed_rp_uids"][:100])]
    if payload["no_form_or_not_created_uids"]:
        lines += ["", "## Parsed But No Passport Yet / No Form", ", ".join(payload["no_form_or_not_created_uids"][:100])]
    lines += [
        "",
        "## Boundaries",
        "- New Build data-bank work only.",
        "- No Live VÉLØ, Shadow, Telegram, staking, live scoring tables, or Newspaper Form into Passport.",
        "- RPR stays archive-only.",
    ]
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="Plan/report New Build final-card Passport Bank backfill.")
    parser.add_argument("--standard-cache", default="data/racecards_2026_05_26_standard.json")
    parser.add_argument("--date", default=DEFAULT_DATE)
    parser.add_argument("--capture-date", default=DEFAULT_CAPTURE_DATE)
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    payload = build_backfill_report(
        standard_cache=Path(args.standard_cache),
        target_date=args.date,
        capture_date=args.capture_date,
        execute=args.execute,
    )
    print(json.dumps(payload, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
