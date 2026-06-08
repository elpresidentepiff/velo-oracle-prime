#!/usr/bin/env python3
"""Build a paper-only identity bridge for the official final-card cache.

This links the Live VELO standard cache runner set to the parsed Racing Post
full-card runners and then to the New Build Passport Bank. It does not write to
Live VELO, Shadow, Telegram, staking, or Supabase.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from new_build_velo.spine import NEW_BUILD_ROOT, norm, stable_id


BRIDGE_PATH = NEW_BUILD_ROOT / "bridges" / "final_card_identity_bridge_latest.jsonl"
REPORT_JSON_PATH = NEW_BUILD_ROOT / "reports" / "final_card_identity_bridge_latest.json"
REPORT_MD_PATH = NEW_BUILD_ROOT / "reports" / "final_card_identity_bridge_latest.md"
PASSPORT_PATH = NEW_BUILD_ROOT / "passports" / "horse_passports_v1.jsonl"


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _write_json(path: Path, payload: Any) -> None:
    if NEW_BUILD_ROOT.resolve() not in path.resolve().parents:
        raise ValueError(f"Refusing to write outside New Build: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    if NEW_BUILD_ROOT.resolve() not in path.resolve().parents:
        raise ValueError(f"Refusing to write outside New Build: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def _off_time(value: Any) -> str:
    text = str(value or "")
    if "T" in text and len(text) >= 16:
        return text[11:16]
    return text[:5]


def _load_official_runners(path: Path) -> list[dict[str, Any]]:
    data = _read_json(path)
    races = data.get("racecards") or data.get("races") or []
    rows: list[dict[str, Any]] = []
    for race in races:
        for runner in race.get("runners", []):
            rows.append(
                {
                    "official_runner_key": stable_id(race.get("race_id"), runner.get("horse") or runner.get("horse_name")),
                    "race_id": str(race.get("race_id") or ""),
                    "course": race.get("course"),
                    "off_time": _off_time(race.get("off_time")),
                    "horse": runner.get("horse") or runner.get("horse_name"),
                    "normalized_name": norm(runner.get("horse") or runner.get("horse_name")),
                    "official_horse_id": str(runner.get("horse_id") or ""),
                    "trainer": runner.get("trainer"),
                    "jockey": runner.get("jockey"),
                }
            )
    return rows


def _load_parsed_runners(path: Path) -> list[dict[str, Any]]:
    data = _read_json(path)
    rows: list[dict[str, Any]] = []
    for race in data.get("races", []):
        for runner in race.get("runners", []):
            if runner.get("non_runner") or runner.get("irish_reserve"):
                continue
            rows.append(
                {
                    "race_id": str(race.get("race_id") or ""),
                    "course": race.get("course"),
                    "off_time": _off_time(race.get("race_time")),
                    "horse": runner.get("horse"),
                    "normalized_name": norm(runner.get("horse")),
                    "rp_uid": str(runner.get("horse_id") or ""),
                    "trainer": runner.get("trainer"),
                    "jockey": runner.get("jockey"),
                }
            )
    return rows


def _load_passports() -> tuple[dict[str, dict[str, Any]], dict[str, list[dict[str, Any]]]]:
    rows = _read_jsonl(PASSPORT_PATH)
    by_uid = {str(row.get("horse_rp_uid")): row for row in rows if row.get("horse_rp_uid") not in (None, "")}
    by_name: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_name[norm(row.get("horse_name"))].append(row)
    return by_uid, by_name


def build_bridge(*, standard_cache: Path, parsed_rp: Path, execute: bool) -> dict[str, Any]:
    official = _load_official_runners(standard_cache)
    parsed = _load_parsed_runners(parsed_rp)
    passports_by_uid, passports_by_name = _load_passports()

    parsed_by_race_name: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    parsed_by_race_name_trainer: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    parsed_by_race_name_jockey: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in parsed:
        parsed_by_race_name[(row["race_id"], row["normalized_name"])].append(row)
        parsed_by_race_name_trainer[(row["race_id"], row["normalized_name"], norm(row.get("trainer")))].append(row)
        parsed_by_race_name_jockey[(row["race_id"], row["normalized_name"], norm(row.get("jockey")))].append(row)

    rows: list[dict[str, Any]] = []
    for runner in official:
        official_uid = runner["official_horse_id"]
        parsed_candidates = parsed_by_race_name_trainer.get(
            (runner["race_id"], runner["normalized_name"], norm(runner.get("trainer"))),
            [],
        )
        method = "NO_MATCH"
        ambiguous = False
        if len(parsed_candidates) == 1:
            parsed_match = parsed_candidates[0]
            method = "RACE_NAME_TRAINER"
        else:
            jockey_candidates = parsed_by_race_name_jockey.get(
                (runner["race_id"], runner["normalized_name"], norm(runner.get("jockey"))),
                [],
            )
            if len(jockey_candidates) == 1:
                parsed_match = jockey_candidates[0]
                method = "RACE_NAME_JOCKEY"
            else:
                name_candidates = parsed_by_race_name.get((runner["race_id"], runner["normalized_name"]), [])
                if len(name_candidates) == 1:
                    parsed_match = name_candidates[0]
                    method = "RACE_NAME"
                elif len(name_candidates) > 1:
                    parsed_match = None
                    method = "AMBIGUOUS_RACE_NAME"
                    ambiguous = True
                else:
                    parsed_match = None

        rp_uid = str(parsed_match.get("rp_uid")) if parsed_match else official_uid
        if official_uid and official_uid == rp_uid:
            method = "EXACT_RP_UID" if method != "NO_MATCH" else "EXACT_RP_UID_STANDARD_ONLY"

        passport = passports_by_uid.get(rp_uid)
        passport_method = "PASSPORT_UID" if passport else None
        if passport is None:
            name_matches = passports_by_name.get(runner["normalized_name"], [])
            if len(name_matches) == 1:
                passport = name_matches[0]
                passport_method = "PASSPORT_NORMALIZED_NAME"
            elif len(name_matches) > 1:
                ambiguous = True
                passport_method = "PASSPORT_NAME_AMBIGUOUS"

        if ambiguous:
            classification = "AMBIGUOUS"
        elif passport:
            classification = "PASSPORT_MATCHED"
        elif parsed_match:
            classification = "RP_UID_NO_PASSPORT"
        else:
            classification = "NO_RP_MATCH"

        rows.append(
            {
                **runner,
                "parsed_rp_uid": rp_uid if parsed_match else None,
                "passport_rp_uid": str(passport.get("horse_rp_uid")) if passport else None,
                "passport_name": passport.get("horse_name") if passport else None,
                "match_method": method,
                "passport_match_method": passport_method,
                "classification": classification,
                "identity_confidence": "HIGH" if classification == "PASSPORT_MATCHED" and method.startswith("EXACT") else "MEDIUM" if passport else "NONE",
                "ambiguous": ambiguous,
                "trust_policy": "ARCHIVE_CONTEXT_ONLY_NOT_SCORING",
                "velo_scoring_allowed": False,
                "rpr_policy": "RPR_ARCHIVE_ONLY_EXCLUDED_FROM_VELO",
                "rp_rpr_velo_allowed": False,
            }
        )

    counts = Counter(row["classification"] for row in rows)
    method_counts = Counter(row["match_method"] for row in rows)
    passport_methods = Counter(row["passport_match_method"] or "NO_PASSPORT" for row in rows)
    duplicate_keys = [
        key for key, count in Counter((row["race_id"], row["normalized_name"]) for row in rows).items() if count > 1
    ]
    before_exact = sum(1 for row in rows if row["official_horse_id"] in passports_by_uid)
    after = sum(1 for row in rows if row["classification"] == "PASSPORT_MATCHED")
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "classification": "FINAL_CARD_IDENTITY_BRIDGE_READY" if not duplicate_keys else "FINAL_CARD_IDENTITY_BRIDGE_REVIEW_REQUIRED",
        "standard_cache": str(standard_cache),
        "parsed_rp": str(parsed_rp),
        "official_runners_checked": len(rows),
        "exact_rp_uid_matches": method_counts.get("EXACT_RP_UID", 0) + method_counts.get("EXACT_RP_UID_STANDARD_ONLY", 0),
        "normalized_name_matches": method_counts.get("RACE_NAME", 0),
        "trainer_jockey_supported_matches": method_counts.get("RACE_NAME_TRAINER", 0) + method_counts.get("RACE_NAME_JOCKEY", 0),
        "ambiguous_matches": counts.get("AMBIGUOUS", 0),
        "no_match_runners": counts.get("NO_RP_MATCH", 0),
        "passport_coverage": {
            "before_exact_uid": before_exact,
            "after_bridge": after,
            "total": len(rows),
            "before_pct": round(before_exact / len(rows) * 100, 2) if rows else 0.0,
            "after_pct": round(after / len(rows) * 100, 2) if rows else 0.0,
        },
        "classification_counts": dict(counts),
        "match_method_counts": dict(method_counts),
        "passport_match_method_counts": dict(passport_methods),
        "duplicate_unsafe_matches": len(duplicate_keys),
        "duplicate_keys": [list(key) for key in duplicate_keys[:50]],
        "rpr_violations": 0,
        "rules": {
            "paper_only": True,
            "no_live_velo": True,
            "no_shadow": True,
            "no_telegram": True,
            "no_staking": True,
            "rpr_archive_only": True,
        },
    }
    if execute:
        _write_jsonl(BRIDGE_PATH, rows)
        _write_json(REPORT_JSON_PATH, payload)
        REPORT_MD_PATH.parent.mkdir(parents=True, exist_ok=True)
        REPORT_MD_PATH.write_text(_markdown(payload, rows), encoding="utf-8")
    return payload


def _markdown(payload: dict[str, Any], rows: list[dict[str, Any]]) -> str:
    coverage = payload["passport_coverage"]
    lines = [
        "# Final-Card Identity Bridge",
        f"Generated: {payload['generated_at']}",
        "",
        "## Summary",
        f"- **Classification**: `{payload['classification']}`",
        f"- **Official runners checked**: {payload['official_runners_checked']}",
        f"- **Exact RP UID matches**: {payload['exact_rp_uid_matches']}",
        f"- **Normalized-name matches**: {payload['normalized_name_matches']}",
        f"- **Trainer/jockey-supported matches**: {payload['trainer_jockey_supported_matches']}",
        f"- **Ambiguous matches**: {payload['ambiguous_matches']}",
        f"- **No-match runners**: {payload['no_match_runners']}",
        f"- **Passport coverage before**: {coverage['before_exact_uid']} / {coverage['total']} ({coverage['before_pct']}%)",
        f"- **Passport coverage after**: {coverage['after_bridge']} / {coverage['total']} ({coverage['after_pct']}%)",
        f"- **Duplicate/unsafe matches**: {payload['duplicate_unsafe_matches']}",
        f"- **RPR violations**: {payload['rpr_violations']}",
        "",
        "## Classification Counts",
    ]
    for key, count in sorted(payload["classification_counts"].items()):
        lines.append(f"- `{key}`: {count}")
    lines += ["", "## No Passport Sample", "| Race | Course | Time | Horse | RP UID | Match |", "|---|---|---:|---|---:|---|"]
    for row in [r for r in rows if r["classification"] != "PASSPORT_MATCHED"][:50]:
        lines.append(f"| {row['race_id']} | {row.get('course')} | {row.get('off_time')} | {row.get('horse')} | {row.get('parsed_rp_uid') or row.get('official_horse_id')} | {row.get('classification')} |")
    lines += [
        "",
        "## Boundaries",
        "- New Build paper-only bridge.",
        "- No Live VELO edits, no Shadow edits, no Telegram, no staking, no live-table writes.",
        "- RPR remains archive-only.",
    ]
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="Build New Build final-card identity bridge.")
    parser.add_argument("--standard-cache", default="data/racecards_2026_05_26_standard.json")
    parser.add_argument("--parsed-rp", default="data/racing_post_account_parsed/live-full-racepages-2026-05-26/racecard_injection.json")
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    print(
        json.dumps(
            build_bridge(
                standard_cache=Path(args.standard_cache),
                parsed_rp=Path(args.parsed_rp),
                execute=args.execute,
            ),
            indent=2,
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
