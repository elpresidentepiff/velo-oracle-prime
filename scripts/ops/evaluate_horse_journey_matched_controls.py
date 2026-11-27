#!/usr/bin/env python3
"""Settle frozen Horse Journey tags against matched same-race controls.

This reads only append-only Rich Context packets captured before the runner's
off time and already-settled canonical results.  It never recalculates a
Journey tag from post-race data and has no scoring, learning, promotion,
routing, execution, or staking effect.
"""
from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Mapping

from scripts.ops.evaluate_rpdc_tag_matched_controls import _fetch_all, evaluate


ROOT = Path(__file__).resolve().parents[2]
REPORT_VERSION = "horse_journey_matched_control_v1"


def _identity(row: Mapping[str, Any]) -> tuple[str, str]:
    return str(row.get("race_id") or "").strip(), str(row.get("horse_id") or "").strip()


def _mapping(value: Any) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return dict(value)
    if isinstance(value, str):
        try:
            decoded = json.loads(value)
        except json.JSONDecodeError:
            return {}
        return dict(decoded) if isinstance(decoded, Mapping) else {}
    return {}


def build_evaluation_inputs(
    packet_rows: list[dict[str, Any]],
) -> tuple[list[dict[str, str]], list[dict[str, str]], dict[str, int]]:
    """Extract an eligible, immutable Journey treatment/control universe.

    A control must itself have a Journey payload that was captured strictly
    pre-off and eligible for future fitting.  That avoids comparing evidence
    captured under two different provenance standards.  No horse-name fallback
    is allowed at any stage.
    """
    tags: list[dict[str, str]] = []
    candidates: list[dict[str, str]] = []
    coverage = {
        "packets_read": len(packet_rows),
        "packets_missing_journey_family": 0,
        "packets_invalid_identity": 0,
        "journey_packets_not_preoff_or_ineligible": 0,
        "journey_eligible_packets": 0,
        "journey_tag_rows": 0,
    }
    seen_candidates: set[tuple[str, str]] = set()
    seen_tags: set[tuple[str, str, str]] = set()

    for packet in packet_rows:
        race_id, horse_id = _identity(packet)
        if not race_id or not horse_id:
            coverage["packets_invalid_identity"] += 1
            continue
        families = _mapping(packet.get("feature_families"))
        journey = _mapping(families.get("horse_journey_facts"))
        if not journey:
            coverage["packets_missing_journey_family"] += 1
            continue
        if not (journey.get("training_eligible") is True and journey.get("captured_before_off") is True):
            coverage["journey_packets_not_preoff_or_ineligible"] += 1
            continue

        identity = (race_id, horse_id)
        if identity not in seen_candidates:
            seen_candidates.add(identity)
            candidates.append({"race_id": race_id, "horse_id": horse_id})
            coverage["journey_eligible_packets"] += 1
        for tag in journey.get("factual_tags") or []:
            tag_name = str(tag or "").strip()
            tag_identity = (race_id, horse_id, tag_name)
            if tag_name and tag_identity not in seen_tags:
                seen_tags.add(tag_identity)
                tags.append({"race_id": race_id, "horse_id": horse_id, "tag": tag_name})
                coverage["journey_tag_rows"] += 1
    return tags, candidates, coverage


def _render(report: Mapping[str, Any]) -> str:
    lines = [
        f"# Horse Journey Matched-Control Report — {report['date']}",
        "",
        "> immutable pre-off Journey evidence · exact race/horse identity only · shadow research only",
        "",
        f"Status: **{report['status']}**",
        "",
        "| Tag | Tagged n | Control n | Tag win% | Control win% | Δ win pp | Tag top-3% | Control top-3% | Δ top-3 pp |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for card in report.get("tag_scorecards") or []:
        treatment = card.get("treatment") or {}
        control = card.get("same_race_control") or {}
        lines.append(
            "| {tag} | {tn} | {cn} | {tw} | {cw} | {dw} | {tt} | {ct} | {dt} |".format(
                tag=card.get("tag") or "—", tn=treatment.get("n", 0), cn=control.get("n", 0),
                tw=treatment.get("win_rate_pct") if treatment.get("win_rate_pct") is not None else "—",
                cw=control.get("win_rate_pct") if control.get("win_rate_pct") is not None else "—",
                dw=card.get("delta_win_rate_pp") if card.get("delta_win_rate_pp") is not None else "—",
                tt=treatment.get("top_3_rate_pct") if treatment.get("top_3_rate_pct") is not None else "—",
                ct=control.get("top_3_rate_pct") if control.get("top_3_rate_pct") is not None else "—",
                dt=card.get("delta_top_3_rate_pp") if card.get("delta_top_3_rate_pp") is not None else "—",
            )
        )
    lines += [
        "",
        "Only packets proven captured before off enter either treatment or control. This is descriptive evidence, not a profitability claim, promotion decision, or betting recommendation.",
    ]
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--date", required=True, help="race date YYYY-MM-DD")
    args = parser.parse_args()
    date_str = args.date

    packet_rows = _fetch_all("rich_context_shadow_packets", date_str, "race_id,horse_id,feature_families")
    tags, candidates, coverage = build_evaluation_inputs(packet_rows)
    report = evaluate(
        tags,
        candidates,
        _fetch_all("racing_horse_runs", date_str, "race_id,horse_id,position_int,position,sp_dec"),
    )
    report.update({
        "report_version": REPORT_VERSION,
        "date": date_str,
        "generated_at": datetime.now(UTC).isoformat(),
        "journey_packet_coverage": coverage,
        "guardrails": {
            **report["guardrails"],
            "source": "append_only_rich_context_packets_pre_off_only",
            "journey_recomputation": "DISALLOWED",
            "training_effect": "NONE",
        },
    })
    tag = date_str.replace("-", "_")
    output = ROOT / "data" / "reports" / f"horse_journey_matched_control_{tag}.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    output.with_suffix(".md").write_text(_render(report), encoding="utf-8")
    print(f"HORSE JOURNEY MATCHED-CONTROL — {date_str}: {report['status']} ({len(report['tag_scorecards'])} tags)")
    raise SystemExit(0 if report["status"] == "OK" else 2)


if __name__ == "__main__":
    main()
