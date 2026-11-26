#!/usr/bin/env python3
"""Write the daily FormFav factual-lane report from immutable packets only."""
from __future__ import annotations

import argparse
import json
import os
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env")

from src.velo.formfav_factual_ablation import build_factual_ablation_report  # noqa: E402


def _packets(date: str) -> list[dict[str, Any]]:
    url = os.getenv("SUPABASE_URL", "").rstrip("/")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_SERVICE_KEY")
    if not url or not key:
        raise RuntimeError("SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY not configured")
    query = urllib.parse.urlencode({
        "race_date": f"eq.{date}",
        "select": "race_id,horse_id,feature_families,eligible_for_future_fit,created_at",
        "limit": "5000",
    })
    request = urllib.request.Request(
        f"{url}/rest/v1/rich_context_shadow_packets?{query}",
        headers={"apikey": key, "Authorization": f"Bearer {key}", "Accept": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        data = json.loads(response.read().decode("utf-8"))
    if not isinstance(data, list):
        raise RuntimeError("unexpected rich_context_shadow_packets response")
    return data


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", required=True)
    parser.add_argument("--output-dir", type=Path, default=ROOT / "data" / "reports")
    args = parser.parse_args()
    report = build_factual_ablation_report(date=args.date, packets=_packets(args.date))
    args.output_dir.mkdir(parents=True, exist_ok=True)
    output = args.output_dir / f"formfav_factual_ablation_{args.date.replace('-', '_')}.json"
    output.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"output": str(output), "summary": report["summary"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
