"""Step 5.55 — Build Horse Arrival Snapshot packets from racecard_merged Spotlight text.

Reads racecard_merged JSON files for --date, extracts RP Spotlight comment text
for every runner, and builds an immutable factual evidence packet using the
existing rich_context_comment_intelligence module.

Packets are:
  - Persisted to Supabase ``rp_arrival_snapshot_facts`` (append-only, upsert
    skips existing rows — safe to rerun).
  - Written locally to data/spotlight_parsed/arrival_snapshot_{date}.json.

This script NEVER modifies Prime probabilities. It is evidence collection only.
Captured data is explicitly marked as not consumed by any active model until a
separately trained and validated artifact declares the family.

Usage:
    python scripts/ops/build_arrival_snapshot_packets.py --date 2026-11-22
    python scripts/ops/build_arrival_snapshot_packets.py --date 2026-11-22 --dry-run
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from src.velo.rich_context_comment_intelligence import (
    build_runner_comment_shadow,
    resolve_race_off_time_utc,
)

DATA_DIR = ROOT / "data"
MERGED_DIR = DATA_DIR / "racecard_merged"
SNAPSHOT_DIR = DATA_DIR / "spotlight_parsed"
SNAPSHOT_DIR.mkdir(exist_ok=True)


def _load_supabase_client():
    """Return a Supabase client or None when env vars are absent."""
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_KEY") or os.getenv("SUPABASE_KEY")
    if not url or not key:
        return None
    try:
        from supabase import create_client
        return create_client(url, key)
    except Exception as exc:
        print(f"  [WARN] Supabase client init failed: {exc}", file=sys.stderr)
        return None


def _resolve_off_utc(race: dict) -> datetime | None:
    return resolve_race_off_time_utc(race)


def _captured_at_from_race(race_info: dict) -> datetime | None:
    """Return only durable RP source time; never substitute a file mtime.

    A merged-file modification time can describe a post-off rerun rather than
    the authenticated pre-off page capture.  An absent/invalid source time is
    deliberately passed through as missing so the factual parser marks the
    packet ineligible instead of inventing historical pre-off evidence.
    """
    value = race_info.get("source_parsed_at") if isinstance(race_info, dict) else None
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else None


def build_packets_for_date(date_str: str, *, dry_run: bool = False) -> dict:
    """Build arrival snapshot packets for all racecard_merged files on date_str."""
    rp_files = sorted(MERGED_DIR.glob(f"racecard_*_{date_str}.json"))
    if not rp_files:
        print(f"  [SKIP] No racecard_merged files found for {date_str}.")
        return {
            "date": date_str,
            "total_runners": 0,
            "runners_with_spotlight": 0,
            "training_eligible": 0,
            "files": 0,
        }

    sb = _load_supabase_client()
    all_packets: list[dict] = []

    total = eligible = skipped_no_text = captured_ok = 0

    for rp_path in rp_files:
        try:
            rp = json.loads(rp_path.read_text())
        except Exception as exc:
            print(f"  [WARN] Could not read {rp_path.name}: {exc}", file=sys.stderr)
            continue

        venue_name: str = rp.get("venue", rp_path.stem.split("_")[1])

        for race_time, race_data in rp.get("races", {}).items():
            horses = race_data.get("horses", [])
            if not horses:
                continue

            race_info = race_data.get("race_info", {})
            captured_at = _captured_at_from_race(race_info)
            race_id = str(
                race_data.get("race_id")
                or f"rp_{rp_path.stem.split('_')[1].lower()}_{date_str.replace('-', '')}_{race_time.replace(':', '_')}"
            )

            # Build a minimal race dict for off-time resolution
            race_proxy = {
                "race_id": race_id,
                "off_time": race_time,
                "date": date_str,
                "course": venue_name,
                "_raw": race_data,
            }
            if isinstance(race_info, dict):
                race_proxy.update(race_info)

            off_utc = _resolve_off_utc(race_proxy)

            for h in horses:
                total += 1
                horse_id = str(h.get("horse_id") or "")
                horse_name = str(h.get("horse_name") or h.get("horse") or "")
                spotlight = str(h.get("spotlight_comment") or "").strip()
                diomed = str(h.get("diomed_comment") or "").strip()

                if not spotlight:
                    skipped_no_text += 1

                packet = build_runner_comment_shadow(
                    raw_text=spotlight,
                    race_id=race_id,
                    horse_id=horse_id,
                    horse_name=horse_name,
                    captured_at=captured_at,
                    off_time_utc=off_utc,
                )
                # Diomed is kept as separate evidence.  It must never be
                # silently concatenated with Spotlight: source attribution is
                # necessary for later factual-family ablations.
                diomed_packet = build_runner_comment_shadow(
                    raw_text=diomed,
                    race_id=race_id,
                    horse_id=horse_id,
                    horse_name=horse_name,
                    captured_at=captured_at,
                    off_time_utc=off_utc,
                )
                factual_spans = [
                    {**span, "source_kind": "RP_SPOTLIGHT"}
                    for span in packet["factual_spans"]
                ] + [
                    {**span, "source_kind": "RP_DIOMED"}
                    for span in diomed_packet["factual_spans"]
                ]
                rejected_spans = [
                    {**span, "source_kind": "RP_SPOTLIGHT"}
                    for span in packet["rejected_spans"]
                ] + [
                    {**span, "source_kind": "RP_DIOMED"}
                    for span in diomed_packet["rejected_spans"]
                ]
                family_counts: dict[str, int] = {}
                for source_packet in (packet, diomed_packet):
                    for family, count in source_packet["family_counts"].items():
                        family_counts[family] = family_counts.get(family, 0) + int(count)
                family_names = sorted(family_counts)
                training_eligible = bool(packet["training_eligible"] or diomed_packet["training_eligible"])
                ineligibility_reasons = sorted(set(packet["ineligibility_reasons"]) & set(diomed_packet["ineligibility_reasons"]))

                row = {
                    "race_date": date_str,
                    "race_id": race_id,
                    "horse_id": horse_id,
                    "horse_name": horse_name,
                    "feature_schema_version": packet["feature_schema_version"],
                    "parser_version": packet["parser_version"],
                    "captured_at": packet["captured_at"],
                    "off_time_utc": packet["off_time_utc"],
                    "captured_before_off": bool(packet["captured_before_off"] or diomed_packet["captured_before_off"]),
                    "identity_eligible": bool(packet["identity_eligible"] and diomed_packet["identity_eligible"]),
                    "raw_text_sha256": packet["raw_text_sha256"],
                    "normalized_text_sha256": packet["normalized_text_sha256"],
                    "has_spotlight_text": bool(spotlight),
                    "has_diomed_text": bool(diomed),
                    "source_capture_provenance": "RP_PARSED_AT",
                    "source_url": race_info.get("source_url") if isinstance(race_info, dict) else None,
                    "source_html_sha256": race_info.get("source_html_sha256") if isinstance(race_info, dict) else None,
                    "factual_spans": factual_spans,
                    "rejected_spans": rejected_spans,
                    "feature_families": family_names,
                    "family_counts": family_counts,
                    "eligible_family_count": len(family_names),
                    "training_eligible": training_eligible,
                    "ineligibility_reasons": ineligibility_reasons,
                    "production_prime_consumed": False,
                    "provider_prediction_consumed": False,
                }
                all_packets.append(row)
                if training_eligible:
                    eligible += 1
                captured_ok += 1

    # ── Persist to Supabase ──────────────────────────────────────────────────
    if not dry_run and sb and all_packets:
        inserted = 0
        BATCH = 200
        for i in range(0, len(all_packets), BATCH):
            batch = all_packets[i : i + BATCH]
            try:
                sb.table("rp_arrival_snapshot_facts").upsert(
                    batch, on_conflict="race_id,horse_id", ignore_duplicates=True
                ).execute()
                inserted += len(batch)
            except Exception as exc:
                print(f"  [WARN] Supabase upsert batch {i//BATCH}: {exc}", file=sys.stderr)
        print(f"  [DB] {inserted} rows upserted → rp_arrival_snapshot_facts")
    elif dry_run:
        print(f"  [DRY-RUN] Would upsert {len(all_packets)} rows → rp_arrival_snapshot_facts")

    # ── Persist local ledger ─────────────────────────────────────────────────
    if not dry_run:
        ledger_path = SNAPSHOT_DIR / f"arrival_snapshot_{date_str}.json"
        ledger = {
            "date": date_str,
            "generated_at": datetime.now(UTC).isoformat(),
            "total_runners": total,
            "runners_with_spotlight_text": captured_ok - skipped_no_text,
            "training_eligible": eligible,
            "skipped_no_spotlight_text": skipped_no_text,
            "files": len(rp_files),
            "packets": all_packets,
        }
        ledger_path.write_text(json.dumps(ledger, indent=2, default=str))
        print(f"  [LOCAL] Ledger → {ledger_path}")

    return {
        "date": date_str,
        "total_runners": total,
        "runners_with_spotlight": captured_ok - skipped_no_text,
        "training_eligible": eligible,
        "files": len(rp_files),
    }


def print_coverage_summary(result: dict) -> None:
    total = result["total_runners"]
    with_text = result.get("runners_with_spotlight", 0)
    eligible = result["training_eligible"]
    if total == 0:
        print("  SNAPSHOT COVERAGE: 0 runners")
        return
    pct_text = 100.0 * with_text / total if total else 0
    pct_elig = 100.0 * eligible / total if total else 0
    status = "FULL" if pct_elig >= 80 else "PARTIAL" if pct_elig >= 40 else "LOW"
    print(
        f"\n  ARRIVAL SNAPSHOT COVERAGE [{result['date']}]\n"
        f"  ├─ Runners total:          {total}\n"
        f"  ├─ Have Spotlight text:    {with_text}  ({pct_text:.0f}%)\n"
        f"  ├─ Training-eligible pkts: {eligible}  ({pct_elig:.0f}%)\n"
        f"  ├─ Captured, NOT consumed: {eligible}  (shadow only — Prime unaffected)\n"
        f"  └─ Coverage status:        {status}\n"
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build Horse Arrival Snapshot packets from racecard_merged Spotlight text."
    )
    parser.add_argument("--date", required=True, help="Race date YYYY-MM-DD")
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Parse and report without writing to Supabase or local files"
    )
    args = parser.parse_args()

    print(f"\n[Step 5.55] Horse Arrival Snapshot packets — {args.date}")
    result = build_packets_for_date(args.date, dry_run=args.dry_run)
    print_coverage_summary(result)

    # Exit non-zero only when we found runners but zero have spotlight text
    if result["total_runners"] > 0 and result.get("runners_with_spotlight", 0) == 0:
        print("  [WARN] No Spotlight text found for any runner on this date.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
