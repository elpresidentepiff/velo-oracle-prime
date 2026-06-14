#!/usr/bin/env python3
"""
RPDC Attach Preflight — READ-ONLY pre-scoring gate
===================================================
Proves BEFORE scoring that today's RPDC candidates can join today's
racecard runners. Born from the June 9 failure: 632 candidates existed
under real RP IDs while the PDF-bypass card carried synthetic
rp_{VENUE}_* IDs — attach silently returned no_data for every race.

After scoring is proof. Before scoring is protection.

Usage:
    PYTHONPATH=. python scripts/ops/check_rpdc_attach_preflight.py --date YYYY-MM-DD

Statuses / exit codes:
    RPDC_ATTACH_READY    0   (>=90% of runners attach by exact race_id+horse_id)
    RPDC_ATTACH_PARTIAL  2   (>=50% attach exact, or fallback raises total >=90%)
    RPDC_ATTACH_FAIL     3   (below partial thresholds)
    RPDC_ATTACH_UNKNOWN  4   (no card, no candidates, or Supabase unreachable)

Outputs:
    data/current/rpdc_attach_preflight_latest.json
    data/reports/rpdc_attach_preflight_{date}.md

Hard constraints: GET-only Supabase; no scoring; no Telegram; no dashboard;
writes nothing except its two output files.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

READY, PARTIAL, FAIL, UNKNOWN = (
    "RPDC_ATTACH_READY",
    "RPDC_ATTACH_PARTIAL",
    "RPDC_ATTACH_FAIL",
    "RPDC_ATTACH_UNKNOWN",
)
_EXIT = {READY: 0, PARTIAL: 2, FAIL: 3, UNKNOWN: 4}


def normalize_horse_name(name: str) -> str:
    """Deterministic name key: lowercase, alphanumeric only, country suffix dropped."""
    name = re.sub(r"\s*\([A-Z]{2,3}\)\s*$", "", name or "")
    return re.sub(r"[^a-z0-9]", "", name.lower())


def _load_env() -> dict:
    env: dict[str, str] = {}
    p = ROOT / ".env"
    if p.exists():
        for line in p.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                env[k.strip()] = v.strip().strip('"').strip("'")
    return env


def _fetch_candidates(date_str: str) -> list | None:
    env = _load_env()
    url = env.get("SUPABASE_URL") or (
        f"https://{env['SUPABASE_PROJECT_ID']}.supabase.co" if env.get("SUPABASE_PROJECT_ID") else ""
    )
    key = env.get("SUPABASE_SERVICE_KEY") or env.get("SUPABASE_KEY") or ""
    if not url or not key:
        return None
    rows: list = []
    offset = 0
    while True:
        req = urllib.request.Request(
            f"{url.rstrip('/')}/rest/v1/runner_release_candidates"
            f"?select=race_id,horse_id,horse,rpdc_tags&run_date=eq.{date_str}"
            f"&limit=1000&offset={offset}",
            headers={"apikey": key, "Authorization": f"Bearer {key}"},
            method="GET",
        )
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                batch = json.loads(resp.read().decode())
        except Exception:
            return None
        rows.extend(batch)
        if len(batch) < 1000:
            return rows
        offset += 1000


def _load_card_runners(date_str: str) -> list[dict] | None:
    """Load the day's card the way scoring will see it (rp_merged path)."""
    try:
        from src.velo.racecard_loader import load_rp_merged_as_racecards

        races = load_rp_merged_as_racecards(date_str, ROOT / "data")
    except Exception:
        return None
    if not races:
        return None
    out = []
    for race in races:
        rid = str(race.get("race_id", ""))
        for runner in race.get("runners", []):
            out.append(
                {
                    "race_id": rid,
                    "horse_id": str(runner.get("horse_id") or ""),
                    "horse": runner.get("horse") or runner.get("horse_name") or "",
                }
            )
    return out


def evaluate(card: list[dict], candidates: list[dict]) -> dict:
    by_exact = {(str(c["race_id"]), str(c["horse_id"])) for c in candidates}
    name_counts: dict[str, int] = {}
    for c in candidates:
        k = normalize_horse_name(c.get("horse", ""))
        if k:
            name_counts[k] = name_counts.get(k, 0) + 1

    exact = fallback = ambiguous = missing = 0
    mismatch_examples = []
    for r in card:
        if (r["race_id"], r["horse_id"]) in by_exact:
            exact += 1
            continue
        k = normalize_horse_name(r["horse"])
        n = name_counts.get(k, 0)
        if n == 1:
            fallback += 1
            if len(mismatch_examples) < 5:
                mismatch_examples.append(
                    {"card": f"{r['race_id']}/{r['horse_id']}", "horse": r["horse"], "join": "name_fallback"}
                )
        elif n > 1:
            ambiguous += 1
        else:
            missing += 1
            if len(mismatch_examples) < 5:
                mismatch_examples.append(
                    {"card": f"{r['race_id']}/{r['horse_id']}", "horse": r["horse"], "join": "none"}
                )

    total = len(card)
    exact_pct = (exact / total * 100) if total else 0.0
    total_attachable_pct = ((exact + fallback) / total * 100) if total else 0.0

    if total == 0:
        status = UNKNOWN
    elif exact_pct >= 90:
        status = READY
    elif exact_pct >= 50 or total_attachable_pct >= 90:
        status = PARTIAL
    else:
        status = FAIL

    return {
        "runners_on_card": total,
        "races_on_card": len({r["race_id"] for r in card}),
        "candidate_rows": len(candidates),
        "attach_exact_race_id": exact,
        "attach_name_fallback": fallback,
        "ambiguous_blocked": ambiguous,
        "no_rpdc": missing,
        "exact_coverage_pct": round(exact_pct, 1),
        "total_attachable_pct": round(total_attachable_pct, 1),
        "mismatch_examples": mismatch_examples,
        "status": status,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", required=True)
    args = parser.parse_args()

    result: dict = {
        "date": args.date,
        "generated_at": datetime.now(UTC).isoformat(),
        "read_only_confirmed": True,
        "status": UNKNOWN,
        "detail": "",
    }

    card = _load_card_runners(args.date)
    if card is None:
        result["detail"] = "no merged racecard found for date (capture/merge not done yet?)"
    else:
        candidates = _fetch_candidates(args.date)
        if candidates is None:
            result["detail"] = "Supabase unreachable or credentials missing"
        elif not candidates:
            result["detail"] = "zero runner_release_candidates for date (build_rpdc_daily not run?)"
            result.update({"runners_on_card": len(card), "candidate_rows": 0})
        else:
            result.update(evaluate(card, candidates))

    out = ROOT / "data/current/rpdc_attach_preflight_latest.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2))

    lines = [
        f"# RPDC Attach Preflight — {args.date}",
        "",
        f"**Status:** {result['status']} · generated {result['generated_at']} · READ-ONLY",
        "",
        f"- Races on card: {result.get('races_on_card', '—')}",
        f"- Runners on card: {result.get('runners_on_card', '—')}",
        f"- Candidate rows: {result.get('candidate_rows', '—')}",
        f"- Exact race_id+horse_id attach: {result.get('attach_exact_race_id', '—')} ({result.get('exact_coverage_pct', '—')}%)",
        f"- Name-fallback attachable: {result.get('attach_name_fallback', '—')}",
        f"- Ambiguous (blocked): {result.get('ambiguous_blocked', '—')}",
        f"- No RPDC available: {result.get('no_rpdc', '—')}",
        f"- Detail: {result.get('detail') or '—'}",
        "",
        "Go/no-go: READY → dry-run scoring allowed · PARTIAL → operator decision ·",
        "FAIL/UNKNOWN → degraded only with operator approval, learning blocked.",
    ]
    reports = ROOT / "data/reports"
    reports.mkdir(parents=True, exist_ok=True)
    (reports / f"rpdc_attach_preflight_{args.date}.md").write_text(
        "\n".join(lines), encoding="utf-8"
    )

    print(f"RPDC attach preflight [{args.date}]: {result['status']}")
    if result.get("detail"):
        print(f"  detail: {result['detail']}")
    if "exact_coverage_pct" in result:
        print(
            f"  exact={result['attach_exact_race_id']}/{result['runners_on_card']} "
            f"({result['exact_coverage_pct']}%), fallback={result['attach_name_fallback']}, "
            f"ambiguous={result['ambiguous_blocked']}, none={result['no_rpdc']}"
        )
    print(f"  -> {out}")
    return _EXIT[result["status"]]


if __name__ == "__main__":
    sys.exit(main())
