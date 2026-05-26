#!/usr/bin/env python3
"""
Parse VELO Racing Post account raw captures.

This parser only reads local files produced by racing_post_account_collector.py.
It does not browse, log in, call Racing Post endpoints, or mutate VELO scoring.
"""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_RAW_DIR = ROOT / "data" / "racing_post_account_raw"
DEFAULT_PARSED_DIR = ROOT / "data" / "racing_post_account_parsed"
PRELOADED_RE = re.compile(r"window\.PRELOADED_STATE\s*=\s*(\{.*?\});", re.S)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _assert_repo_path(path: Path, label: str) -> Path:
    resolved = path.resolve()
    if ROOT not in resolved.parents and resolved != ROOT:
        raise SystemExit(f"{label} must live under repo root: {ROOT}")
    return resolved


def _load_preloaded_state(html_path: Path) -> dict[str, Any] | None:
    html = html_path.read_text(encoding="utf-8", errors="replace")
    match = PRELOADED_RE.search(html)
    if not match:
        return None
    return json.loads(match.group(1))


def _normalise_horse_profile(meta: dict[str, Any], state: dict[str, Any]) -> dict[str, Any] | None:
    profile = state.get("profile") or {}
    if not profile.get("horseUid"):
        return None

    entries = state.get("entries") or []
    quotes = state.get("quotes") or []
    tips = profile.get("tips") or []
    trainer_last_14 = profile.get("trainerLast14Days") or {}

    return {
        "source": "racing_post_account_capture",
        "collector": meta.get("collector"),
        "source_url": meta.get("source_url"),
        "final_url": meta.get("final_url"),
        "html_path": meta.get("html_path"),
        "html_sha256": meta.get("html_sha256"),
        "captured_at": meta.get("finished_at"),
        "parsed_at": _utc_now(),
        "requires_audit": True,
        "horse_uid": profile.get("horseUid"),
        "horse_name": profile.get("horseName"),
        "country": profile.get("horseCountryOriginCode"),
        "age": profile.get("age"),
        "date_of_birth": profile.get("horseDateOfBirth"),
        "sex": profile.get("horseSex"),
        "colour": profile.get("horseColour"),
        "trainer_uid": profile.get("trainerUid"),
        "trainer_name": profile.get("trainerName"),
        "trainer_location": profile.get("trainerLocation"),
        "trainer_last_14_runs": trainer_last_14.get("runs"),
        "trainer_last_14_wins": trainer_last_14.get("wins"),
        "trainer_last_14_percent": trainer_last_14.get("percent"),
        "owner_uid": profile.get("ownerUid"),
        "owner_name": profile.get("ownerName"),
        "previous_owners": profile.get("previousOwners") or [],
        "breeder_name": profile.get("breederName"),
        "sire_uid": profile.get("sireUid"),
        "sire_name": profile.get("sireHorseName"),
        "sire_country": profile.get("sireCountryOriginCode"),
        "dam_uid": profile.get("damUid"),
        "dam_name": profile.get("damHorseName"),
        "dam_country": profile.get("damCountryOriginCode"),
        "dam_sire_uid": profile.get("damSireUid"),
        "dam_sire_name": profile.get("damSireHorseName"),
        "dam_sire_country": profile.get("damSireCountryOriginCode"),
        "avg_flat_win_distance": profile.get("avgFlatWinDist"),
        "sire_avg_flat_win_distance": profile.get("sireAvgFlatWinDist"),
        "dam_sire_avg_flat_win_distance": profile.get("damSireAvgFlatWinDist"),
        "avg_win_distance": profile.get("avgWinDistance"),
        "sire_avg_win_distance": profile.get("sireAvgWinDistance"),
        "dam_sire_avg_win_distance": profile.get("damSireAvgWinDistance"),
        "tips_count": len(tips),
        "entries_count": len(entries),
        "quotes_count": len(quotes),
        "tips": tips,
        "entries": entries,
        "quotes": quotes,
        "stable_tour_quotes": state.get("stableTourQuotes") or [],
        "account_user_role": state.get("userRole"),
        "account_original_subscription_level": state.get("originalSubscriptionLevel"),
        "account_is_logged": state.get("isLogged"),
    }


def _load_manifest_or_sidecars(raw_day_dir: Path, manifest_path: Path) -> dict[str, Any]:
    if manifest_path.exists():
        return json.loads(manifest_path.read_text(encoding="utf-8"))

    captures: list[dict[str, Any]] = []
    for sidecar_path in sorted(raw_day_dir.glob("*.json")):
        if sidecar_path.name == "manifest.json":
            continue
        row = json.loads(sidecar_path.read_text(encoding="utf-8"))
        html_path = row.get("html_path")
        if html_path and not Path(html_path).exists():
            local_html = raw_day_dir / Path(html_path).name
            if local_html.exists():
                row["html_path"] = str(local_html)
        captures.append(row)

    return {
        "mode": "capture_sidecar_recovery",
        "status": "RECOVERED_FROM_SIDECARS",
        "captures": captures,
    }


def parse_capture_day(*, capture_date: str, raw_dir: Path, output_dir: Path, execute: bool) -> dict[str, Any]:
    raw_day_dir = _assert_repo_path(raw_dir / capture_date, "raw_day_dir")
    output_day_dir = _assert_repo_path(output_dir / capture_date, "output_day_dir")
    manifest_path = raw_day_dir / "manifest.json"

    manifest = _load_manifest_or_sidecars(raw_day_dir, manifest_path)
    horse_profiles: list[dict[str, Any]] = []
    page_results: list[dict[str, Any]] = []

    for capture in manifest.get("captures", []):
        html_path_value = capture.get("html_path")
        if not html_path_value:
            page_results.append({"source_url": capture.get("source_url"), "status": "NO_HTML"})
            continue
        html_path = Path(html_path_value)
        if not html_path.exists():
            page_results.append({"source_url": capture.get("source_url"), "status": "HTML_MISSING"})
            continue
        state = _load_preloaded_state(html_path)
        if not state:
            page_results.append({"source_url": capture.get("source_url"), "status": "NO_PRELOADED_STATE"})
            continue
        horse_profile = _normalise_horse_profile(capture, state)
        if horse_profile:
            horse_profiles.append(horse_profile)
            page_results.append(
                {
                    "source_url": capture.get("source_url"),
                    "status": "HORSE_PROFILE_PARSED",
                    "horse_uid": horse_profile["horse_uid"],
                    "horse_name": horse_profile["horse_name"],
                }
            )
        else:
            page_results.append({"source_url": capture.get("source_url"), "status": "PRELOADED_STATE_UNSUPPORTED"})

    payload = {
        "capture_date": capture_date,
        "generated_at": _utc_now(),
        "raw_manifest": str(manifest_path),
        "pages_seen": len(manifest.get("captures", [])),
        "horse_profiles_count": len(horse_profiles),
        "page_results": page_results,
        "horse_profiles": horse_profiles,
    }

    if not execute:
        payload["status"] = "DRY_RUN"
        payload["execute_required"] = True
        return payload

    output_day_dir.mkdir(parents=True, exist_ok=True)
    out_path = output_day_dir / "horse_profiles.json"
    out_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    payload["status"] = "PASS"
    payload["output_path"] = str(out_path)
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description="Parse local Racing Post account capture files.")
    parser.add_argument("--date", required=True, help="YYYY-MM-DD capture date")
    parser.add_argument("--raw-dir", default=str(DEFAULT_RAW_DIR))
    parser.add_argument("--output-dir", default=str(DEFAULT_PARSED_DIR))
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()

    payload = parse_capture_day(
        capture_date=args.date,
        raw_dir=Path(args.raw_dir),
        output_dir=Path(args.output_dir),
        execute=args.execute,
    )
    print(json.dumps(payload, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
