#!/usr/bin/env python3
"""FormFav readiness gate: is the second source stored and fresh BEFORE RP lands?

Run this first (run_full_raceday.py Step 0). The RP capture is perishable and
local; FormFav is continuous and cloud-side. If FormFav's stored data for the
day is thin or stale, find out before spending the RP capture, not after.

Read-only (Supabase REST, same credentials as the worker). Exit 0 = ready,
2 = not ready, 0 with a SKIP message when Supabase credentials are absent
(this machine cannot check; Step 5.6 still enforces coverage after RP lands).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.parse
import urllib.request
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any

IN_CHUNK = 40


def _parse(ts: Any) -> datetime | None:
    try:
        dt = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
        return dt if dt.tzinfo else dt.replace(tzinfo=UTC)
    except (TypeError, ValueError):
        return None


def _rest_get(path: str) -> list[dict[str, Any]]:
    url = (os.getenv("SUPABASE_URL") or "").strip().rstrip("/")
    key = (os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_SERVICE_KEY") or "").strip()
    req = urllib.request.Request(
        f"{url}/rest/v1/{path}",
        headers={"apikey": key, "Authorization": f"Bearer {key}", "Accept": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def collect(date: str, countries: set[str], fetch: Callable[[str], list[dict[str, Any]]] = _rest_get) -> dict[str, Any]:
    in_c = "in.(" + ",".join(sorted(countries)) + ")"
    races = fetch("formfav_races?" + urllib.parse.urlencode({
        "race_date": f"eq.{date}", "country": in_c, "select": "provider_race_key", "limit": "5000"}))
    keys = [r["provider_race_key"] for r in races]
    with_form: set[str] = set()
    with_pred: set[str] = set()
    runners = scratched = with_stats = with_speed = with_class = 0
    newest: datetime | None = None
    for i in range(0, len(keys), IN_CHUNK):
        chunk = keys[i:i + IN_CHUNK]
        in_k = "in.(" + ",".join(f'"{k}"' for k in chunk) + ")"
        for row in fetch("formfav_runner_form?" + urllib.parse.urlencode({
                "provider_race_key": in_k, "select": "provider_race_key,scratched,form_payload,updated_at"})):
            with_form.add(row["provider_race_key"])
            runners += 1
            scratched += 1 if row.get("scratched") else 0
            fp = row.get("form_payload") or {}
            with_stats += 1 if fp.get("stats") else 0
            with_speed += 1 if fp.get("speedMap") else 0
            with_class += 1 if fp.get("classProfile") else 0
            ts = _parse(row.get("updated_at"))
            if ts and (newest is None or ts > newest):
                newest = ts
        for row in fetch("formfav_predictions?" + urllib.parse.urlencode({
                "provider_race_key": in_k, "select": "provider_race_key"})):
            with_pred.add(row["provider_race_key"])
    return {
        "date": date, "countries": sorted(countries), "races": len(keys),
        "races_with_form": len(with_form), "races_with_predictions": len(with_pred),
        "runners": runners, "scratched": scratched,
        "runners_with_stats": with_stats, "runners_with_speedmap": with_speed, "runners_with_class": with_class,
        "newest_form_update": newest.isoformat() if newest else None,
    }


def evaluate(
    stats: dict[str, Any], *, now: datetime, min_races: int = 1, min_form: float = 0.95,
    min_predictions: float = 0.9, min_stats: float = 0.8, max_age: timedelta = timedelta(hours=3),
) -> list[str]:
    """Return a list of failures (empty = ready)."""
    fails: list[str] = []
    n = stats["races"]
    if n < min_races:
        return [f"only {n} FormFav races stored for {stats['date']} (need >= {min_races})"]
    if stats["races_with_form"] / n < min_form:
        fails.append(f"form stored for {stats['races_with_form']}/{n} races (< {min_form:.0%})")
    if stats["races_with_predictions"] / n < min_predictions:
        fails.append(f"predictions stored for {stats['races_with_predictions']}/{n} races (< {min_predictions:.0%})")
    live = max(stats["runners"] - stats["scratched"], 0)
    if live == 0:
        fails.append("no runners stored")
    elif stats["runners_with_stats"] / live < min_stats:
        fails.append(f"runner stats on {stats['runners_with_stats']}/{live} runners (< {min_stats:.0%})")
    newest = _parse(stats.get("newest_form_update"))
    if newest is None or now - newest > max_age:
        fails.append(f"newest form update is {stats.get('newest_form_update')} (older than {max_age}); worker may be down")
    return fails


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--date", required=True)
    ap.add_argument("--countries", default="gb,ie")
    ap.add_argument("--min-races", type=int, default=1)
    args = ap.parse_args()
    if not (os.getenv("SUPABASE_URL") and (os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_SERVICE_KEY"))):
        print("[FORMFAV-READY] SKIP: no Supabase credentials on this machine; cannot pre-check. "
              "Step 5.6 still enforces FormFav coverage before scoring.", flush=True)
        return 0
    stats = collect(args.date, {c.strip().lower() for c in args.countries.split(",") if c.strip()})
    fails = evaluate(stats, now=datetime.now(UTC), min_races=args.min_races)
    print(json.dumps({"formfav_readiness": stats, "ready": not fails, "failures": fails}, indent=2), flush=True)
    if fails:
        print("[FORMFAV-READY] NOT READY: " + "; ".join(fails), file=sys.stderr, flush=True)
        return 2
    print("[FORMFAV-READY] READY: FormFav data is stored and fresh; safe to capture RP.", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
