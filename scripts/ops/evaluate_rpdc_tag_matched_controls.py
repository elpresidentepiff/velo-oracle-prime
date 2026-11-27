#!/usr/bin/env python3
"""Evaluate daily RPDC tags against same-race, non-tagged controls.

This is an outcome-only research report.  It reads the immutable pre-race
``today_rpdc_tags`` ledger, the day's candidate universe, and settled results
already ingested into ``racing_horse_runs``.  It never re-computes a tag, never
changes a score, and never recommends or executes a bet.

For each tag, the comparison is deliberately race-matched:

* treatment: runners carrying that exact tag;
* control: other settled runners in those exact races that do not carry it.

The report uses WIN and TOP_3 only.  Prices are reported as coverage facts but
are not used for ROI until an explicitly validated price-truth protocol exists.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.parse
import urllib.request
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from dotenv import load_dotenv


ROOT = Path(__file__).resolve().parents[2]
REPORT_VERSION = "rpdc_matched_control_v1"


def _identity(row: dict[str, Any]) -> tuple[str, str]:
    return str(row.get("race_id") or "").strip(), str(row.get("horse_id") or "").strip()


def _position(row: dict[str, Any]) -> int | None:
    try:
        pos = int(row.get("position_int"))
    except (TypeError, ValueError):
        return None
    return pos if pos > 0 else None


def _metrics(rows: list[dict[str, Any]]) -> dict[str, Any]:
    settled = [row for row in rows if _position(row) is not None]
    n = len(settled)
    wins = sum(_position(row) == 1 for row in settled)
    top_3 = sum((_position(row) or 999) <= 3 for row in settled)
    price_coverage = sum(row.get("sp_dec") not in (None, "") for row in settled)
    return {
        "n": n,
        "wins": wins,
        "top_3": top_3,
        "win_rate_pct": round(100 * wins / n, 1) if n else None,
        "top_3_rate_pct": round(100 * top_3 / n, 1) if n else None,
        "sp_decimal_coverage": price_coverage,
        "sp_decimal_coverage_pct": round(100 * price_coverage / n, 1) if n else None,
    }


def evaluate(
    tag_rows: list[dict[str, Any]],
    candidate_rows: list[dict[str, Any]],
    result_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    """Return a deterministic tag versus same-race control scorecard.

    Results join by the canonical ``(race_id, horse_id)`` pair only.  An absent
    or malformed identity is counted as unresolved instead of being guessed
    from a horse name.
    """
    candidates: dict[tuple[str, str], dict[str, Any]] = {}
    by_race: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in candidate_rows:
        race_id, horse_id = _identity(row)
        if not (race_id and horse_id):
            continue
        candidates[(race_id, horse_id)] = row
    for row in candidates.values():
        by_race[_identity(row)[0]].append(row)

    results: dict[tuple[str, str], dict[str, Any]] = {}
    for row in result_rows:
        race_id, horse_id = _identity(row)
        if race_id and horse_id:
            results[(race_id, horse_id)] = row

    tags_by_name: dict[str, set[tuple[str, str]]] = defaultdict(set)
    malformed_tag_rows = 0
    for row in tag_rows:
        tag = str(row.get("tag") or "").strip()
        ident = _identity(row)
        if not tag or not all(ident):
            malformed_tag_rows += 1
            continue
        tags_by_name[tag].add(ident)

    scorecards: list[dict[str, Any]] = []
    for tag in sorted(tags_by_name):
        tagged_identities = tags_by_name[tag]
        tagged_rows: list[dict[str, Any]] = []
        control_identities: set[tuple[str, str]] = set()
        tagged_missing_candidate = 0
        tagged_unresolved_result = 0

        for identity in sorted(tagged_identities):
            candidate = candidates.get(identity)
            if candidate is None:
                tagged_missing_candidate += 1
                continue
            result = results.get(identity)
            if result is None or _position(result) is None:
                tagged_unresolved_result += 1
                continue
            tagged_rows.append(result)
            race_id, _ = identity
            for peer in by_race.get(race_id, []):
                peer_identity = _identity(peer)
                if peer_identity not in tagged_identities:
                    control_identities.add(peer_identity)

        control_rows: list[dict[str, Any]] = []
        control_unresolved_result = 0
        for identity in sorted(control_identities):
            result = results.get(identity)
            if result is None or _position(result) is None:
                control_unresolved_result += 1
                continue
            control_rows.append(result)

        treatment = _metrics(tagged_rows)
        control = _metrics(control_rows)
        scorecards.append(
            {
                "tag": tag,
                "races": len({_identity(row)[0] for row in tagged_rows}),
                "tagged_source_rows": len(tagged_identities),
                "tagged_missing_candidate": tagged_missing_candidate,
                "tagged_unresolved_result": tagged_unresolved_result,
                "control_unresolved_result": control_unresolved_result,
                "treatment": treatment,
                "same_race_control": control,
                "delta_win_rate_pp": (
                    round(treatment["win_rate_pct"] - control["win_rate_pct"], 1)
                    if treatment["win_rate_pct"] is not None and control["win_rate_pct"] is not None
                    else None
                ),
                "delta_top_3_rate_pp": (
                    round(treatment["top_3_rate_pct"] - control["top_3_rate_pct"], 1)
                    if treatment["top_3_rate_pct"] is not None and control["top_3_rate_pct"] is not None
                    else None
                ),
                "interpretation": "DESCRIPTIVE_ONLY_INSUFFICIENT_SAMPLE",
            }
        )

    return {
        "report_version": REPORT_VERSION,
        "tag_rows_read": len(tag_rows),
        "candidate_rows_read": len(candidate_rows),
        "result_rows_read": len(result_rows),
        "malformed_tag_rows": malformed_tag_rows,
        "tag_scorecards": scorecards,
        "status": "OK" if scorecards else "NO_SETTLED_TAG_EVIDENCE",
        "guardrails": {
            "outcome_only": True,
            "same_race_controls_only": True,
            "identity_fallback": "DISALLOWED",
            "scoring_effect": "NONE",
            "execution_effect": "NONE",
            "promotion_effect": "NONE",
        },
    }


def _env() -> tuple[str, str]:
    load_dotenv(ROOT / ".env")
    url = os.getenv("SUPABASE_URL", "")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_SERVICE_KEY", "")
    if not url or not key:
        raise SystemExit("SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY not configured")
    return url.rstrip("/"), key


def _fetch_all(table: str, date_str: str, select: str) -> list[dict[str, Any]]:
    url, key = _env()
    out: list[dict[str, Any]] = []
    offset = 0
    while True:
        query = urllib.parse.urlencode(
            {"run_date": f"eq.{date_str}", "select": select, "offset": offset, "limit": 1000},
            safe=",*",
        )
        req = urllib.request.Request(
            f"{url}/rest/v1/{table}?{query}",
            headers={"apikey": key, "Authorization": f"Bearer {key}"},
        )
        with urllib.request.urlopen(req, timeout=60) as response:
            batch = json.loads(response.read().decode("utf-8"))
        out.extend(batch)
        if len(batch) < 1000:
            return out
        offset += len(batch)


def _render(report: dict[str, Any]) -> str:
    lines = [
        f"# RPDC Tag Matched-Control Report — {report['date']}",
        "",
        "> outcome-only shadow research · exact race/horse identity only · no scoring, promotion, execution, or staking effect",
        "",
        f"Status: **{report['status']}**",
        f"Source rows: tags {report['tag_rows_read']} · candidates {report['candidate_rows_read']} · result runners {report['result_rows_read']}",
        "",
        "| Tag | Tagged n | Control n | Tag win% | Control win% | Δ win pp | Tag top-3% | Control top-3% | Δ top-3 pp |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for card in report["tag_scorecards"]:
        treatment, control = card["treatment"], card["same_race_control"]
        lines.append(
            "| {tag} | {tn} | {cn} | {tw} | {cw} | {dw} | {tt} | {ct} | {dt} |".format(
                tag=card["tag"], tn=treatment["n"], cn=control["n"],
                tw=treatment["win_rate_pct"] if treatment["win_rate_pct"] is not None else "—",
                cw=control["win_rate_pct"] if control["win_rate_pct"] is not None else "—",
                dw=card["delta_win_rate_pp"] if card["delta_win_rate_pp"] is not None else "—",
                tt=treatment["top_3_rate_pct"] if treatment["top_3_rate_pct"] is not None else "—",
                ct=control["top_3_rate_pct"] if control["top_3_rate_pct"] is not None else "—",
                dt=card["delta_top_3_rate_pp"] if card["delta_top_3_rate_pp"] is not None else "—",
            )
        )
    lines += [
        "",
        "These are descriptive, same-race comparisons. They are not a causal claim, profitability result, promotion decision, or betting recommendation. Price coverage is retained for a future separately validated ROI protocol.",
    ]
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--date", required=True, help="race date YYYY-MM-DD")
    args = parser.parse_args()
    date_str = args.date

    report = evaluate(
        _fetch_all("today_rpdc_tags", date_str, "race_id,horse_id,horse,tag,tag_strength,evidence"),
        _fetch_all("runner_release_candidates", date_str, "race_id,horse_id,horse"),
        _fetch_all("racing_horse_runs", date_str, "race_id,horse_id,horse,position_int,position,sp_dec"),
    )
    report.update({"date": date_str, "generated_at": datetime.now(UTC).isoformat()})
    tag = date_str.replace("-", "_")
    output = ROOT / "data" / "reports" / f"rpdc_tag_matched_control_{tag}.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    output.with_suffix(".md").write_text(_render(report), encoding="utf-8")
    print(f"RPDC TAG MATCHED-CONTROL — {date_str}: {report['status']} ({len(report['tag_scorecards'])} tags)")
    sys.exit(0 if report["status"] == "OK" else 2)


if __name__ == "__main__":
    main()
