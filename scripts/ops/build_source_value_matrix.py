#!/usr/bin/env python3
"""Build a source-value matrix across RP archive, Racing API shadows, Velo, Sigma, and RPDC."""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
PARSED_ROOT = ROOT / "data" / "racing_post_account_parsed"
REPORT_ROOT = ROOT / "data" / "reports"

RP_ONLY_FIELDS = {
    "owner", "sire", "dam", "dam_sire", "entries", "quotes", "sales", "notes",
    "headgear", "headgear_first_time", "wind_surgery", "newspaper_comment",
    "spotlight_comment", "tip_count", "rp_rpr_archive_only", "topspeed_archive_only",
}
VELO_FIELDS = {
    "velo_prime_prob", "sqpe_v17_prob", "improvement_score", "market_deception_score",
    "tier", "assigned_product", "execution_allowed", "rpdc_tags", "rpdc_primary_tag",
}
RACING_API_SHADOW_FIELDS = {
    "racing_api_connection_shadow_score", "racing_api_course_shadow_score",
    "racing_api_distance_shadow_score", "racing_api_enrichment_shadow_score",
    "horse_recent_runs_90d", "trainer_course_win_pct", "horse_course_runs",
}
DANGEROUS_FIELDS = {"rp_rpr_archive_only", "rpr", "topspeed_archive_only", "tip_count", "newspaper_comment", "spotlight_comment"}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _load(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def _norm(value: Any) -> str:
    return "".join(ch for ch in str(value or "").lower() if ch.isalnum())


def _verdict_rows(date: str) -> list[dict[str, Any]]:
    path = ROOT / "data" / f"velo_prime_verdicts_{date.replace('-', '_')}.json"
    payload = _load(path, [])
    rows: list[dict[str, Any]] = []
    if isinstance(payload, list):
        for race in payload:
            top = race.get("top") or {}
            if top.get("horse"):
                row = dict(top)
                row["_race_course"] = race.get("course")
                row["_race_time"] = race.get("off_time")
                row["_race_id"] = race.get("race_id")
                row["_verdict_source"] = str(path)
                rows.append(row)
    return rows


def _sigma_rows(date: str) -> dict[str, dict[str, Any]]:
    path = ROOT / "data" / "sigma_results" / f"sigma_results_{date.replace('-', '_')}.json"
    payload = _load(path, {})
    rows = payload.get("learning_candidate_rows") or payload.get("raw_sigma_audits_preserved") or []
    out: dict[str, dict[str, Any]] = {}
    if isinstance(rows, list):
        for row in rows:
            horse = row.get("horse") or row.get("selection") or row.get("top_horse")
            if horse:
                out[_norm(horse)] = row
    return out


def _rpdc_rows() -> dict[str, list[dict[str, Any]]]:
    path = ROOT / "data" / "rpdc_backfill" / "rpdc_tags_historical.jsonl"
    out: dict[str, list[dict[str, Any]]] = defaultdict(list)
    if not path.exists():
        return out
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if row.get("horse"):
                out[_norm(row["horse"])].append(row)
    return out


def _field_class(field: str, present_sources: set[str]) -> list[str]:
    labels: list[str] = []
    if len(present_sources) > 1:
        labels.append("DUPLICATED")
    elif "RP" in present_sources:
        labels.append("UNIQUE_TO_RP")
    elif "RACING_API" in present_sources:
        labels.append("UNIQUE_TO_RACING_API")
    elif "VELO" in present_sources:
        labels.append("UNIQUE_TO_VELO")
    else:
        labels.append("MISSING")
    if field in DANGEROUS_FIELDS:
        labels.append("DO_NOT_USE_FOR_SCORING")
    elif "RP" in present_sources:
        labels.append("USEFUL_FOR_ARCHIVE")
    if field in {"trainer", "jockey", "owner", "sire", "dam", "dam_sire", "headgear_first_time", "wind_surgery", "tip_count", "rpdc_tags"}:
        labels.append("USEFUL_FOR_SHADOW")
    return labels


def build(date: str, execute: bool) -> dict[str, Any]:
    day = PARSED_ROOT / date
    dossiers = _load(day / "horse_dossiers.json", {}).get("dossiers") or []
    profiles_24 = _load(PARSED_ROOT / "2026-05-24" / "horse_profiles.json", {}).get("horse_profiles") or []
    # Pilot explicitly includes Bow Echo even if not on May 25 racecard.
    for profile in profiles_24:
        if _norm(profile.get("horse_name")) == "bowecho":
            dossiers.append({
                "horse": profile.get("horse_name"),
                "rp_horse_id": profile.get("horse_uid"),
                "trainer": profile.get("trainer_name"),
                "owner": profile.get("owner_name"),
                "sire": profile.get("sire_name"),
                "dam": profile.get("dam_name"),
                "dam_sire": profile.get("dam_sire_name"),
                "age": profile.get("age"),
                "country": profile.get("country"),
                "entries": profile.get("entries") or [],
                "quotes": profile.get("quotes") or [],
                "tip_count": profile.get("tips_count"),
                "archive_flags": ["BOW_ECHO_PILOT_PROFILE"],
                "trust_policy": "ARCHIVE_CONTEXT_ONLY_NOT_SCORING",
                "velo_scoring_allowed": False,
                "rpr_policy": "RPR_ARCHIVE_ONLY_EXCLUDED_FROM_VELO",
            })
    verdicts = {_norm(row.get("horse")): row for row in _verdict_rows(date)}
    sigmas = _sigma_rows(date)
    rpdc = _rpdc_rows()
    matrix: list[dict[str, Any]] = []
    source_counter: Counter[str] = Counter()
    field_counter: Counter[str] = Counter()

    for dossier in dossiers:
        horse_key = _norm(dossier.get("horse"))
        verdict = verdicts.get(horse_key) or {}
        sigma = sigmas.get(horse_key) or {}
        rpdc_rows = rpdc.get(horse_key) or []
        racing_api_available = {field: verdict.get(field) for field in RACING_API_SHADOW_FIELDS if verdict.get(field) is not None}
        velo_available = {field: verdict.get(field) for field in VELO_FIELDS if verdict.get(field) not in (None, [], "")}
        rp_available = {field: dossier.get(field) for field in RP_ONLY_FIELDS if dossier.get(field) not in (None, [], "")}
        fields: dict[str, list[str]] = {}
        for field in sorted(RP_ONLY_FIELDS | VELO_FIELDS | RACING_API_SHADOW_FIELDS | {"trainer", "jockey", "age", "country"}):
            present: set[str] = set()
            if dossier.get(field) not in (None, [], ""):
                present.add("RP")
            if verdict.get(field) not in (None, [], ""):
                present.add("VELO")
            if field in racing_api_available:
                present.add("RACING_API")
            fields[field] = _field_class(field, present)
            for label in fields[field]:
                field_counter[label] += 1
        sources_present = ["RP"]
        if racing_api_available:
            sources_present.append("RACING_API")
        if velo_available:
            sources_present.append("VELO")
        if sigma:
            sources_present.append("SIGMA")
        if rpdc_rows:
            sources_present.append("RPDC")
        for source in sources_present:
            source_counter[source] += 1
        matrix.append({
            "horse": dossier.get("horse"),
            "rp_horse_id": dossier.get("rp_horse_id"),
            "racing_api_horse_id": verdict.get("horse_id"),
            "velo_runner_id": verdict.get("horse_id"),
            "trainer": dossier.get("trainer"),
            "jockey": dossier.get("jockey"),
            "owner": dossier.get("owner"),
            "sire": dossier.get("sire"),
            "dam": dossier.get("dam"),
            "dam_sire": dossier.get("dam_sire"),
            "age": dossier.get("age"),
            "sex_country": dossier.get("sex_country"),
            "country": dossier.get("country"),
            "entries_count": len(dossier.get("entries") or []),
            "quotes_count": len(dossier.get("quotes") or []),
            "headgear": dossier.get("headgear"),
            "wind_surgery": dossier.get("wind_surgery"),
            "days_since_run": dossier.get("days_since_run"),
            "tip_count": dossier.get("tip_count"),
            "rp_comments_available": bool(dossier.get("newspaper_comment") or dossier.get("spotlight_comment")),
            "racing_api_fields_available": sorted(racing_api_available),
            "velo_fields_available": sorted(velo_available),
            "rpdc_tags": (rpdc_rows[-1].get("rpdc_tags") if rpdc_rows else dossier.get("rpdc_tags")) or [],
            "sigma_outcome": sigma.get("result") or sigma.get("outcome") or sigma.get("sigma_status"),
            "sources_present": sources_present,
            "field_classifications": fields,
            "trust_policy": "ARCHIVE_CONTEXT_ONLY_NOT_SCORING",
            "velo_scoring_allowed": False,
            "rpr_policy": "RPR_ARCHIVE_ONLY_EXCLUDED_FROM_VELO",
        })
    payload = {
        "date": date,
        "generated_at": _utc_now(),
        "status": "DRY_RUN",
        "horse_count": len(matrix),
        "source_presence_counts": dict(source_counter),
        "field_classification_counts": dict(field_counter),
        "scoring_impact": "NONE",
        "matrix": matrix,
    }
    if execute:
        REPORT_ROOT.mkdir(parents=True, exist_ok=True)
        json_path = REPORT_ROOT / "source_value_matrix_latest.json"
        md_path = REPORT_ROOT / "source_value_matrix_latest.md"
        bow_path = REPORT_ROOT / "bow_echo_source_profile.md"
        uniqueness_path = REPORT_ROOT / "source_uniqueness_audit_latest.md"
        json_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        lines = ["# Source Value Matrix", "", f"- Date: `{date}`", f"- Horses compared: `{len(matrix)}`", "- Scoring impact: `NONE`", "", "## Source Presence"]
        for source, count in source_counter.most_common():
            lines.append(f"- {source}: `{count}`")
        lines += ["", "## Sample Rows"]
        for row in matrix[:30]:
            lines.append(f"- **{row['horse']}**: sources={', '.join(row['sources_present'])}; tips={row.get('tip_count')}; RPDC={row.get('rpdc_tags')}")
        md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

        bow = next((row for row in matrix if _norm(row.get("horse")) == "bowecho"), None)
        bow_lines = ["# Bow Echo Source Profile", "", "- Scoring impact: `NONE`", "- RPR policy: `RPR_ARCHIVE_ONLY_EXCLUDED_FROM_VELO`", ""]
        if bow:
            bow_lines += [
                f"- Horse: **{bow.get('horse')}**",
                f"- RP horse id: `{bow.get('rp_horse_id')}`",
                f"- Trainer: `{bow.get('trainer')}`",
                f"- Owner: `{bow.get('owner')}`",
                f"- Sire / dam / dam sire: `{bow.get('sire')}` / `{bow.get('dam')}` / `{bow.get('dam_sire')}`",
                f"- Age / country: `{bow.get('age')}` / `{bow.get('country')}`",
                f"- Entries: `{bow.get('entries_count')}`",
                f"- Quotes: `{bow.get('quotes_count')}`",
                f"- Tips: `{bow.get('tip_count')}`",
                "",
                "## What Each Source Adds",
                "",
                "- Racing Post: profile identity, trainer/owner, pedigree, entries, quotes, tip heat.",
                "- Racing API: no local direct Bow Echo match found in this pilot.",
                "- VÉLØ: no local Bow Echo verdict found in this pilot.",
                "- Sigma: no local Bow Echo outcome found in this pilot.",
                "- RPDC: no local Bow Echo memory found in this pilot.",
                "",
                "## Keep Out Of Scoring",
                "",
                "- RPR, RP comments, tip count, and RP opinion fields remain archive/context only.",
                "",
                "## Shadow Research Candidates",
                "",
                "- Trainer form, ownership change, pedigree, entries, and quote/intent context.",
            ]
        else:
            bow_lines.append("Bow Echo profile was not found in the local matrix inputs.")
        bow_path.write_text("\n".join(bow_lines) + "\n", encoding="utf-8")

        uniqueness_lines = ["# Source Uniqueness Audit", "", "- Scoring impact: `NONE`", ""]
        uniqueness_lines += [
            "## RP-Only Fields",
            "",
            "- owner",
            "- sire / dam / dam sire",
            "- entries",
            "- quotes",
            "- sales / notes when captured",
            "- headgear / wind surgery",
            "- newspaper comment",
            "- tip count",
            "- RP RPR archive-only",
            "",
            "## Racing API-Only Fields",
            "",
            "- structured race/runner/horse IDs where available",
            "- course/distance/connection shadow analysis fields where present in VÉLØ verdict artifacts",
            "",
            "## VÉLØ-Created Fields",
            "",
            "- velo_prime_prob",
            "- SQPE",
            "- MDS",
            "- improvement_score",
            "- tier / product / router decision",
            "- RPDC lookup state when attached",
            "",
            "## Dangerous / Leakage-Prone Fields",
            "",
            "- RPR",
            "- same-race RP ratings",
            "- RP comments if treated as truth",
            "- tip count if treated as winner signal rather than public heat",
            "",
            "## Recommendation",
            "",
            "Keep RP as archive/context. Promote only after shadow evidence, leakage audit, and operator approval.",
        ]
        uniqueness_path.write_text("\n".join(uniqueness_lines) + "\n", encoding="utf-8")
        payload["status"] = "PASS"
        payload["json_path"] = str(json_path)
        payload["md_path"] = str(md_path)
        payload["bow_echo_profile_path"] = str(bow_path)
        payload["source_uniqueness_path"] = str(uniqueness_path)
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description="Build source-value matrix.")
    parser.add_argument("--date", default="2026-05-25")
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    print(json.dumps(build(args.date, args.execute), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
