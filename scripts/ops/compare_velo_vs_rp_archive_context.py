#!/usr/bin/env python3
"""Compare existing Velo predictions against archive-only Racing Post context."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
PARSED_ROOT = ROOT / "data" / "racing_post_account_parsed"
REPORT_ROOT = ROOT / "data" / "reports"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _load(path: Path, default: Any) -> Any:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default


def _norm(value: Any) -> str:
    return "".join(ch for ch in str(value or "").lower() if ch.isalnum())


def _find_velo_sources(date: str) -> list[Path]:
    tag = date.replace("-", "_")
    compact = date.replace("-", "")
    patterns = [
        f"*{date}*verdict*.json",
        f"*{tag}*verdict*.json",
        f"*{compact}*verdict*.json",
        f"*rp_velo_convergence*{date}*.json",
        f"*rp_velo_convergence*{tag}*.json",
    ]
    roots = [
        ROOT / "data",
        ROOT / "data" / "reports",
        ROOT / "data" / "phase4_daily_reports",
        ROOT / "data" / "ops_worker_dry_run",
    ]
    found: list[Path] = []
    for root in roots:
        if not root.exists():
            continue
        for pattern in patterns:
            found.extend(root.glob(pattern))
    return sorted(set(p for p in found if "racing_post_account_parsed" not in str(p)))


def _extract_picks(path: Path) -> list[dict[str, Any]]:
    try:
        payload = _load(path, {})
    except Exception:
        return []
    rows: list[dict[str, Any]] = []
    if isinstance(payload, dict):
        candidates = payload.get("verdicts") or payload.get("races") or payload.get("items") or payload.get("comparisons")
        if isinstance(candidates, list):
            for item in candidates:
                if not isinstance(item, dict):
                    continue
                horse = item.get("horse") or item.get("top_pick") or item.get("velo_top_pick")
                if horse:
                    rows.append({
                        "horse": horse,
                        "course": item.get("course"),
                        "off_time": item.get("off_time") or item.get("race_time"),
                        "vp": item.get("velo_prime_prob") or item.get("vp_probability") or item.get("prob"),
                        "tier": item.get("decision_tier") or item.get("tier"),
                        "source_file": str(path),
                    })
    return rows


def _classify(pick: dict[str, Any], dossier: dict[str, Any] | None) -> str:
    if not dossier:
        return "INSUFFICIENT_ARCHIVE_DATA"
    flags = set(dossier.get("archive_flags") or [])
    tips = int(dossier.get("tip_count") or 0)
    if "MARKET_OVERHYPE_RISK" in flags and tips >= 6:
        return "VELO_CONFIRMED_BY_CONTEXT"
    if tips == 0 and "INSUFFICIENT_PROFILE" not in flags:
        return "QUIET_PROFILE_POSITIVE"
    if "INSUFFICIENT_PROFILE" in flags:
        return "ARCHIVE_CONTEXT_WARNING"
    if tips >= 7:
        return "PUBLIC_OVERLOAD_TRAP"
    return "VELO_AGAINST_HYPE"


def build(date: str, execute: bool) -> dict[str, Any]:
    day = PARSED_ROOT / date
    dossiers_payload = _load(day / "horse_dossiers.json", {})
    dossiers = {_norm(d.get("horse")): d for d in dossiers_payload.get("dossiers") or []}
    sources = _find_velo_sources(date)
    picks: list[dict[str, Any]] = []
    for source in sources:
        picks.extend(_extract_picks(source))
    comparisons = []
    for pick in picks:
        dossier = dossiers.get(_norm(pick.get("horse")))
        comparisons.append({
            "horse": pick.get("horse"),
            "course": pick.get("course"),
            "off_time": pick.get("off_time"),
            "vp": pick.get("vp"),
            "tier": pick.get("tier"),
            "archive_classification": _classify(pick, dossier),
            "archive_flags": (dossier or {}).get("archive_flags") or [],
            "tip_count": (dossier or {}).get("tip_count"),
            "trust_policy": "ARCHIVE_CONTEXT_ONLY_NOT_SCORING",
            "velo_scoring_allowed": False,
        })
    payload = {
        "date": date,
        "generated_at": _utc_now(),
        "status": "DRY_RUN",
        "velo_sources_found": [str(p) for p in sources],
        "velo_pick_count": len(picks),
        "comparison_count": len(comparisons),
        "scoring_impact": "NONE",
        "comparisons": comparisons,
    }
    if execute:
        REPORT_ROOT.mkdir(parents=True, exist_ok=True)
        out_json = REPORT_ROOT / f"velo_vs_archive_context_{date.replace('-', '_')}.json"
        out_md = REPORT_ROOT / f"velo_vs_archive_context_{date.replace('-', '_')}.md"
        out_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        lines = [f"# Velo vs RP Archive Context - {date}", "", f"- Velo sources: `{len(sources)}`", f"- Comparisons: `{len(comparisons)}`", "- Scoring impact: `NONE`", ""]
        if not comparisons:
            lines.append("No local Velo verdict source found. Archive comparison is waiting for official predictions.")
        for row in comparisons[:40]:
            lines.append(f"- **{row['horse']}**: {row['archive_classification']} ({', '.join(row['archive_flags'])})")
        out_md.write_text("\n".join(lines) + "\n", encoding="utf-8")
        payload["status"] = "PASS"
        payload["json_path"] = str(out_json)
        payload["md_path"] = str(out_md)
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare Velo predictions against archive-only RP context.")
    parser.add_argument("--date", required=True)
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    print(json.dumps(build(args.date, args.execute), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
