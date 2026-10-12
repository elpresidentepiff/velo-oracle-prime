#!/usr/bin/env python3
"""Cloud-native VELO race-day bootstrap for Railway cron.

The laptop is not part of this path.

Flow:
  1. Fetch the authenticated Racing API Standard card for the London race date.
  2. Persist that card to the container's scratch data directory with explicit
     source provenance.
  3. Build the dated New Build passport feed from the checked-in passport bank.
  4. Execute the canonical Prime scorer, which persists durable truth to Supabase.

Racing Post HTML/PDF data may enrich later runs, but is not an execution
dependency for the baseline daily Railway run.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.velo.racecard_loader import fetch_api_racecards
from src.velo.formfav_enrichment import enrich_existing_racecards
from src.velo.formfav_uk_features import FEATURE_SCHEMA_VERSION, build_race_shadow_packet

LONDON = ZoneInfo("Europe/London")


def _date_today_london() -> str:
    return datetime.now(LONDON).date().isoformat()


def _normalise_country(value: object) -> str:
    key = str(value or "").strip().lower()
    return {"uk": "gb", "eng": "gb", "ire": "ie", "irl": "ie"}.get(key, key)


def _write_api_cache(date_str: str, races: list[dict]) -> Path:
    data_dir = ROOT / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    target = data_dir / f"racecards_{date_str.replace('-', '_')}_standard.json"
    temp = target.with_suffix(".json.tmp")
    payload = {
        "_velo_source": "racing_api_standard",
        "_requested_date": date_str,
        "_fetched_at_utc": datetime.now(timezone.utc).isoformat(),
        "_runtime": "railway-cloud-raceday",
        "racecards": races,
    }
    temp.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    os.replace(temp, target)
    return target


def _run(label: str, command: list[str]) -> None:
    print(f"\n[CLOUD] {label}: {' '.join(command)}", flush=True)
    completed = subprocess.run(command, cwd=ROOT, check=False)
    if completed.returncode != 0:
        raise RuntimeError(f"{label} failed with exit code {completed.returncode}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", default=None, help="Race date YYYY-MM-DD; defaults to Europe/London today")
    parser.add_argument("--no-notify", action="store_true", help="Disable Telegram sends from Prime")
    args = parser.parse_args()

    date_str = args.date or _date_today_london()
    print(f"VELO CLOUD RACEDAY — {date_str}", flush=True)
    print("executor=Railway source=RacingAPI-Standard durable_truth=Supabase", flush=True)

    races = fetch_api_racecards(date_str)

    # FormFav is a strictly isolated shadow copy. The object later written to
    # Prime's cache is never enriched, even when a canonical field is missing.
    if (os.getenv("FORMFAV_API_KEY") or "").strip():
        countries = {
            c.strip().lower()
            for c in (os.getenv("FORMFAV_ENRICH_COUNTRIES") or "gb,ie").split(",")
            if c.strip()
        }
        report_path = ROOT / "data" / "reports" / f"formfav_enrichment_{date_str.replace('-', '_')}.json"
        try:
            production_snapshot = deepcopy(races)
            shadow_races, ff_report = enrich_existing_racecards(
                date_str=date_str,
                races=races,
                countries=countries,
                include_prices=(os.getenv("FORMFAV_INCLUDE_PRICES", "1").strip() != "0"),
                include_track_bias=(os.getenv("FORMFAV_INCLUDE_TRACK_BIAS", "1").strip() != "0"),
                timezone=os.getenv("FORMFAV_TIMEZONE") or "Europe/London",
                report_path=report_path,
            )
            if races != production_snapshot:
                raise RuntimeError("FormFav shadow boundary violation: production racecards mutated")
            print(
                "[FORMFAV] enrichment "
                f"matched_races={ff_report.get('races_matched', 0)} "
                f"matched_runners={ff_report.get('runners_matched', 0)} "
                f"track_bias_calls={ff_report.get('track_bias_calls_ok', 0)} "
                f"price_calls={ff_report.get('price_calls_ok', 0)} "
                f"errors={len(ff_report.get('errors') or [])}",
                flush=True,
            )

            # Build a UK/IRE-only source-aware feature packet. This is SHADOW
            # evidence: Prime does not read these features yet.
            uk_races = [
                race for race in shadow_races
                if race.get("_formfav")
                if _normalise_country(
                    (race.get("_formfav") or {}).get("country")
                    or race.get("country")
                    or race.get("region")
                )
                in {"gb", "ie"}
            ]
            uk_packets = [build_race_shadow_packet(race) for race in uk_races]
            uk_report = {
                "date": date_str,
                "status": "SHADOW_ONLY_ENRICHED" if uk_packets else "SHADOW_NO_USABLE_ENRICHMENT",
                "shadow_only": True,
                "production_influence": False,
                "stake_authorised": False,
                "promotion_eligible": False,
                "feature_schema_version": FEATURE_SCHEMA_VERSION,
                "source": "formfav",
                "primary_source": "racing_api_standard",
                "race_count": len(uk_packets),
                "runner_count": sum(p.get("runner_count", 0) for p in uk_packets),
                "training_eligible_runners": sum(p.get("training_eligible_runners", 0) for p in uk_packets),
                "mean_race_quality": (
                    round(sum(float(p.get("mean_quality_score") or 0.0) for p in uk_packets) / len(uk_packets), 4)
                    if uk_packets else 0.0
                ),
                "races": uk_packets,
            }
            uk_shadow_path = ROOT / "data" / "reports" / f"formfav_uk_shadow_features_{date_str.replace('-', '_')}.json"
            uk_shadow_path.parent.mkdir(parents=True, exist_ok=True)
            uk_shadow_path.write_text(json.dumps(uk_report, ensure_ascii=False), encoding="utf-8")
            print(
                "[FORMFAV-UK] shadow features "
                f"schema={FEATURE_SCHEMA_VERSION} races={uk_report['race_count']} "
                f"runners={uk_report['runner_count']} eligible={uk_report['training_eligible_runners']} "
                f"mean_quality={uk_report['mean_race_quality']}",
                flush=True,
            )
        except Exception as exc:
            print(f"[FORMFAV] non-fatal enrichment failure: {type(exc).__name__}: {exc}", file=sys.stderr, flush=True)

    runner_count = sum(len(r.get("runners", [])) for r in races)
    if not races or runner_count == 0:
        raise RuntimeError(f"Racing API card unusable: races={len(races)} runners={runner_count}")

    cache_path = _write_api_cache(date_str, races)
    print(
        f"[CLOUD] card ready: races={len(races)} runners={runner_count} cache={cache_path.name}",
        flush=True,
    )

    # Prime's readiness contract requires the dated passport feed before
    # scoring. Build it inside this same ephemeral Railway container.
    _run(
        "passport feed",
        [
            sys.executable,
            "scripts/ops/new_build_current_card_feed.py",
            "--execute",
            "--racecard-path",
            str(cache_path),
        ],
    )

    feed_path = (
        ROOT
        / "data"
        / "new_build"
        / "current_cards"
        / f"current_card_passport_feed_{date_str.replace('-', '_')}.jsonl"
    )
    if not feed_path.exists() or feed_path.stat().st_size == 0:
        raise RuntimeError(f"Passport readiness feed missing/empty after build: {feed_path}")

    score_cmd = [
        sys.executable,
        "scripts/ops/run_prime_today.py",
        "--date",
        date_str,
        "--source",
        "cache",
        "--allow-missing-pdfs",
    ]
    if args.no_notify:
        score_cmd.append("--no-notify")
    _run("Prime scoring", score_cmd)

    # Persist FormFav's raw enrichment packet alongside the other daily report
    # artifacts. This is intentionally non-fatal: a persistence problem must
    # never invalidate a successfully completed canonical scoring run.
    ff_report_path = ROOT / "data" / "reports" / f"formfav_enrichment_{date_str.replace('-', '_')}.json"
    if ff_report_path.exists():
        persist_cmd = [
            sys.executable,
            "scripts/ops/persist_daily_artifacts.py",
            "--kind",
            "reports",
            "--date",
            date_str,
            "--execute",
        ]
        print(f"\n[CLOUD] FormFav artifact persistence: {' '.join(persist_cmd)}", flush=True)
        persisted = subprocess.run(persist_cmd, cwd=ROOT, check=False)
        if persisted.returncode != 0:
            print(
                f"[FORMFAV] WARNING: artifact persistence exited {persisted.returncode}; scoring remains PASS",
                file=sys.stderr,
                flush=True,
            )

    print(f"\n[CLOUD] PASS — Railway completed canonical scoring for {date_str}", flush=True)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"\n[CLOUD] FAIL — {type(exc).__name__}: {exc}", file=sys.stderr, flush=True)
        raise
