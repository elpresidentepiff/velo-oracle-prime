from __future__ import annotations

import argparse
import csv
import itertools
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"

sys.path.insert(0, str(ROOT))

from src.velo.race_metadata_resolver import RaceMetadataResolver

try:
    from src.velo.racing_api_stat_adapter import RacingAPIStatAdapter
except Exception:
    RacingAPIStatAdapter = None


SAFE_ROLES = {"BANKER", "GLUE", "BOOSTER", "WILDCARD"}
SEVERE_TRAPS = {"HIGH_DECOY_RISK", "DX_GOING_BLOCKER", "DX_NO_SIGNAL"}


def normalize_name(value: Any) -> str:
    return str(value or "").upper().split("(")[0].strip()


def normalize_course(value: Any) -> str:
    return str(value or "").upper().replace("  ", " ").strip()


def normalize_time(value: Any) -> str:
    return str(value or "").strip().replace(".", ":")


def date_token(date_str: str) -> str:
    return date_str.replace("-", "_")


def load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def load_verdicts(date_str: str) -> list[dict[str, Any]]:
    path = DATA / f"velo_prime_verdicts_{date_token(date_str)}.json"
    payload = load_json(path, [])
    if isinstance(payload, dict):
        return payload.get("verdicts", [])
    return payload


def load_standard_cards(date_str: str) -> dict[str, dict[str, Any]]:
    path = DATA / f"racecards_{date_token(date_str)}_standard.json"
    payload = load_json(path, {})
    races = payload.get("racecards", [])
    return {race.get("race_id"): race for race in races if race.get("race_id")}


def load_cashrun_index(date_str: str) -> tuple[dict[tuple[str, str], dict[str, Any]], str]:
    path = DATA / f"cashrun_report_{date_str}.csv"
    if not path.exists():
        return {}, "MISSING_OPTIONAL"
    out: dict[tuple[str, str], dict[str, Any]] = {}
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            out[(row.get("race_id", ""), row.get("horse_id", ""))] = row
    return out, "PRESENT"


def load_industry_index(date_str: str) -> tuple[dict[tuple[str, str], dict[str, Any]], str]:
    path = DATA / f"industry_selections_{date_str.replace('-', '')}.json"
    if not path.exists():
        return {}, "MISSING_OPTIONAL"
    payload = load_json(path, {})
    out: dict[tuple[str, str], dict[str, Any]] = {}
    for venue in payload.get("venues", []):
        course = normalize_course(venue.get("course"))
        for time_value in venue.get("race_times", []):
            out.setdefault((course, normalize_time(time_value)), {"horse_counts": {}, "horse_tipsters": {}})
        for tipster, picks in venue.get("tipsters", {}).items():
            for time_value, pick in picks.items():
                key = (course, normalize_time(time_value))
                horse = normalize_name((pick or {}).get("horse"))
                if not horse:
                    continue
                bucket = out.setdefault(key, {"horse_counts": {}, "horse_tipsters": {}})
                bucket["horse_counts"][horse] = bucket["horse_counts"].get(horse, 0) + 1
                bucket["horse_tipsters"].setdefault(horse, []).append(tipster)
    return out, "PRESENT"


def extract_top_prediction(verdict: dict[str, Any]) -> dict[str, Any]:
    top = verdict.get("top")
    if isinstance(top, dict) and top:
        return top
    full_analysis = verdict.get("full_analysis")
    if isinstance(full_analysis, dict):
        predictions = full_analysis.get("predictions") or []
        if predictions:
            return predictions[0]
    if isinstance(full_analysis, list) and full_analysis:
        return full_analysis[0]
    return {}


def build_runner_lookup(race: dict[str, Any]) -> dict[tuple[str, str], dict[str, Any]]:
    return {
        (runner.get("horse_id", ""), normalize_name(runner.get("horse"))): runner
        for runner in race.get("runners", [])
    }


def coerce_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item) for item in value if str(item).strip()]
    return [str(value)]


def enrichment_from_top(top: dict[str, Any]) -> dict[str, Any]:
    score = top.get("racing_api_enrichment_shadow_score")
    return {
        "racing_api_connection_shadow_score": top.get("racing_api_connection_shadow_score"),
        "racing_api_course_shadow_score": top.get("racing_api_course_shadow_score"),
        "racing_api_distance_shadow_score": top.get("racing_api_distance_shadow_score"),
        "racing_api_enrichment_shadow_score": score,
        "racing_api_stat_status": "EMBEDDED" if score is not None else "MISSING",
    }


def maybe_enrich_from_adapter(adapter: Any, runner: dict[str, Any] | None, race: dict[str, Any] | None, top: dict[str, Any]) -> dict[str, Any]:
    if adapter is None or runner is None or race is None:
        return enrichment_from_top(top)
    try:
        enriched = adapter.enrich_runner(runner, race)
        if enriched.get("racing_api_enrichment_shadow_score") is not None:
            return enriched
    except Exception:
        pass
    return enrichment_from_top(top)


def trap_flags_for_candidate(tier: str, top: dict[str, Any], metadata_complete: bool, industry_conflicts: bool) -> tuple[list[str], list[str]]:
    router_reasons = coerce_list(top.get("router_reasons"))
    blockers = list(router_reasons)
    trap_flags: list[str] = []

    if tier == "X":
        trap_flags.append("TIER_X")
    favourite_trap = str(top.get("favourite_trap_risk") or "").upper()
    if favourite_trap in {"HIGH", "ELEVATED"}:
        trap_flags.append("HIGH_DECOY_RISK")
    if top.get("a_tier_weak_place_flag"):
        trap_flags.append("WEAK_MARGIN")
    for reason in router_reasons:
        text = str(reason).upper()
        if "WEAK_MARGIN" in text:
            trap_flags.append("WEAK_MARGIN")
        if "DECOY" in text:
            trap_flags.append("HIGH_DECOY_RISK")
        if "GOING" in text:
            trap_flags.append("DX_GOING_BLOCKER")
        if "NO_SIGNAL" in text:
            trap_flags.append("DX_NO_SIGNAL")
    if not metadata_complete:
        trap_flags.append("UNRESOLVED_METADATA")
    if industry_conflicts:
        trap_flags.append("INDUSTRY_CONFLICT")

    seen: set[str] = set()
    ordered: list[str] = []
    for flag in trap_flags:
        if flag and flag not in seen:
            seen.add(flag)
            ordered.append(flag)
    return blockers, ordered


def cashrun_bonus(cashrun_row: dict[str, Any] | None) -> tuple[float, str]:
    if not cashrun_row:
        return 0.0, "MISSING_OPTIONAL"
    label = str(cashrun_row.get("label") or "").strip() or "UNKNOWN"
    if label == "CASHRUN_READY":
        return 10.0, label
    if label == "CASHRUN_WATCH":
        return 6.0, label
    if label == "WEAK_SIGNAL":
        return 2.0, label
    return 0.0, label


def source_completeness(metadata_complete: bool, industry_count: int, cashrun_row: dict[str, Any] | None, enrichment: dict[str, Any]) -> str:
    optional_hits = 0
    if industry_count > 0:
        optional_hits += 1
    if cashrun_row:
        optional_hits += 1
    if enrichment.get("racing_api_enrichment_shadow_score") is not None:
        optional_hits += 1
    if metadata_complete and optional_hits >= 2:
        return "FULL"
    if metadata_complete and optional_hits >= 1:
        return "PARTIAL"
    if metadata_complete:
        return "LOW_SOURCE"
    return "BLOCKED_SOURCE"


def compute_leg_score(
    vp: float,
    place_prob: float,
    mds: float,
    tier: str,
    trap_flags: list[str],
    cashrun_row: dict[str, Any] | None,
    industry_count: int,
    enrichment: dict[str, Any],
    metadata_complete: bool,
) -> tuple[float, dict[str, float]]:
    vp_score = min(30.0, max(0.0, vp * 60.0))
    place_score = min(20.0, max(0.0, place_prob * 20.0))
    mds_score = min(10.0, max(0.0, mds * 25.0))
    cash_score, _ = cashrun_bonus(cashrun_row)
    industry_score = min(10.0, float(industry_count) * 2.0)

    tier_base = {"A": 18.0, "B": 12.0, "C": 7.0, "D": 4.0, "X": 0.0}.get(tier, 5.0)
    cleanliness_score = min(20.0, tier_base + (2.0 if not trap_flags else 0.0))
    enrichment_score = enrichment.get("racing_api_enrichment_shadow_score")
    if enrichment_score is not None:
        cleanliness_score = min(20.0, cleanliness_score + min(2.0, float(enrichment_score) / 10.0))

    negatives = 0.0
    if "HIGH_DECOY_RISK" in trap_flags:
        negatives += 18.0
    if "DX_GOING_BLOCKER" in trap_flags:
        negatives += 12.0
    if "DX_NO_SIGNAL" in trap_flags:
        negatives += 15.0
    if "WEAK_MARGIN" in trap_flags:
        negatives += 8.0
    if "INDUSTRY_CONFLICT" in trap_flags:
        negatives += 6.0
    if "UNRESOLVED_METADATA" in trap_flags:
        negatives += 12.0
    if tier == "X":
        negatives += 10.0
    if not metadata_complete:
        negatives += 10.0

    total = vp_score + place_score + mds_score + cash_score + industry_score + cleanliness_score - negatives
    return round(max(0.0, min(100.0, total)), 2), {
        "vp_confidence_score": round(vp_score, 2),
        "place_frame_score": round(place_score, 2),
        "mds_market_shape_score": round(mds_score, 2),
        "cashrun_score": round(cash_score, 2),
        "industry_confirmation_score": round(industry_score, 2),
        "tier_cleanliness_score": round(cleanliness_score, 2),
        "negative_adjustments": round(negatives, 2),
    }


def assign_leg_role(score: float, vp: float, place_prob: float, trap_flags: list[str], source_state: str, industry_count: int, cashrun_label: str) -> str:
    if source_state == "BLOCKED_SOURCE":
        return "BLOCKED"
    if any(flag in SEVERE_TRAPS for flag in trap_flags) or "TIER_X" in trap_flags:
        return "TRAP"
    if score >= 75.0 and vp >= 0.30 and place_prob >= 0.70:
        return "BANKER"
    if score >= 62.0 and place_prob >= 0.62:
        return "GLUE"
    if score >= 55.0 and (industry_count >= 2 or cashrun_label in {"CASHRUN_READY", "CASHRUN_WATCH"} or vp >= 0.26):
        return "BOOSTER"
    if score >= 40.0:
        return "WILDCARD"
    return "TRAP"


def parse_sort_time(value: str) -> tuple[int, int]:
    try:
        left, right = normalize_time(value).split(":")
        return int(left), int(right)
    except Exception:
        return 99, 99


def combo_constraints(size: int, roles: list[str], day_regime: str) -> bool:
    bankers = roles.count("BANKER")
    boosters = roles.count("BOOSTER")
    glues = roles.count("GLUE")
    wildcards = roles.count("WILDCARD")
    if size == 2:
        return bankers == 2 or (bankers >= 1 and boosters == 1)
    if size == 3:
        return bankers >= 2 and boosters <= 1
    if size == 4:
        return bankers >= 2 and glues >= 1 and boosters <= 1
    if size == 5:
        return day_regime in {"ACCA_DAY_STRONG", "ACCA_DAY_PLAYABLE"} and bankers >= 3 and boosters <= 1 and wildcards == 0
    if size == 6:
        return day_regime == "ACCA_DAY_STRONG" and bankers >= 3 and boosters <= 1 and wildcards == 0
    return False


def compute_combo_score(combo: tuple[dict[str, Any], ...]) -> float:
    leg_total = sum(float(item["leg_score"]) for item in combo)
    avg_place = sum(float(item["place_prob"]) for item in combo) / len(combo)
    avg_vp = sum(float(item["vp"]) for item in combo) / len(combo)
    industry = sum(int(item["industry_confirmation_count"]) for item in combo)
    mds_avg = sum(float(item["mds"]) for item in combo) / len(combo)
    enrichment_values = [item["racing_api_enrichment_score"] for item in combo if item["racing_api_enrichment_score"] is not None]
    enrichment_bonus = (sum(float(v) for v in enrichment_values) / len(enrichment_values) / 10.0) if enrichment_values else 0.0
    return round(leg_total + (avg_place * 10.0) + (avg_vp * 15.0) + min(6.0, industry) + (mds_avg * 6.0) + enrichment_bonus, 2)


def choose_best_fold(candidates: list[dict[str, Any]], size: int, day_regime: str) -> dict[str, Any] | None:
    pool = sorted([item for item in candidates if item["leg_role"] in SAFE_ROLES], key=lambda item: item["leg_score"], reverse=True)[:12]
    if len(pool) < size:
        return None
    best: dict[str, Any] | None = None
    for combo in itertools.combinations(pool, size):
        roles = [item["leg_role"] for item in combo]
        if not combo_constraints(size, roles, day_regime):
            continue
        combo_score = compute_combo_score(combo)
        ordered = sorted(combo, key=lambda item: parse_sort_time(item["off_time"]))
        candidate = {
            "generated": True,
            "size": size,
            "combo_score": combo_score,
            "legs": [
                {
                    "horse": leg["horse"],
                    "course": leg["course"],
                    "off_time": leg["off_time"],
                    "race_name": leg["race_name"],
                    "leg_role": leg["leg_role"],
                    "vp": leg["vp"],
                    "place_prob": leg["place_prob"],
                    "mds": leg["mds"],
                    "leg_score": leg["leg_score"],
                }
                for leg in ordered
            ],
        }
        if best is None or candidate["combo_score"] > best["combo_score"]:
            best = candidate
    return best


def classify_day(candidates: list[dict[str, Any]]) -> str:
    bankers = sum(1 for item in candidates if item["leg_role"] == "BANKER")
    glues = sum(1 for item in candidates if item["leg_role"] == "GLUE")
    boosters = sum(1 for item in candidates if item["leg_role"] == "BOOSTER")
    safe = sum(1 for item in candidates if item["leg_role"] in SAFE_ROLES)
    if bankers >= 4 and safe >= 6:
        return "ACCA_DAY_STRONG"
    if bankers >= 2 and (glues + boosters) >= 2 and safe >= 4:
        return "ACCA_DAY_PLAYABLE"
    if bankers >= 1 and safe >= 3:
        return "ACCA_DAY_THIN"
    return "NO_ACCA_DAY"


def render_md(report: dict[str, Any]) -> str:
    lines = [
        f"ACCA LANE REPORT - {report['date']}",
        "",
        f"Status: {report['status']}",
        f"Day regime: {report['day_regime']}",
        f"Candidates scanned: {report['candidates_scanned']}",
        f"CASHRUN status: {report['cashrun_status']}",
        f"Industry status: {report['industry_status']}",
        f"Racing API enrichment status: {report['racing_api_enrichment_status']}",
        "",
        "Role counts:",
    ]
    for role, count in report["role_counts"].items():
        lines.append(f"- {role}: {count}")
    lines.extend(["", "Candidate folds:"])
    for label in ("strongest_2_fold", "strongest_3_fold", "strongest_4_fold", "controlled_5_fold", "speculative_6_fold"):
        fold = report["folds"].get(label)
        if not fold or not fold.get("generated"):
            lines.append(f"- {label}: SUPPRESSED")
            continue
        parts = [f"{leg['off_time']} {leg['course']} {leg['horse']} [{leg['leg_role']}]" for leg in fold["legs"]]
        lines.append(f"- {label}: {' -> '.join(parts)} | combo_score={fold['combo_score']}")
    lines.extend(["", "Trap legs:"])
    for trap in report["trap_legs"][:12]:
        lines.append(f"- {trap['off_time']} {trap['course']} {trap['horse']} | {', '.join(trap['trap_flags'])}")
    lines.extend(["", "Rejected legs:"])
    for rejected in report["rejected_legs"][:12]:
        lines.append(f"- {rejected['off_time']} {rejected['course']} {rejected['horse']} | {rejected['leg_role']} | {', '.join(rejected['reasons'])}")
    return "\n".join(lines) + "\n"


def write_csv(path: Path, candidates: list[dict[str, Any]]) -> None:
    fields = [
        "horse", "horse_id", "race_id", "course", "off_time", "race_name",
        "vp", "decision_tier", "place_prob", "mds", "improvement_score",
        "candidate_execution_allowed", "racing_api_enrichment_score",
        "cashrun_class", "industry_confirmation_count", "industry_tipsters",
        "blocker_flags", "suppress_flags", "leg_score", "leg_role",
        "trap_flags", "source_completeness",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in candidates:
            writer.writerow({
                "horse": row["horse"],
                "horse_id": row["horse_id"],
                "race_id": row["race_id"],
                "course": row["course"],
                "off_time": row["off_time"],
                "race_name": row["race_name"],
                "vp": row["vp"],
                "decision_tier": row["decision_tier"],
                "place_prob": row["place_prob"],
                "mds": row["mds"],
                "improvement_score": row["improvement_score"],
                "candidate_execution_allowed": row["candidate_execution_allowed"],
                "racing_api_enrichment_score": row["racing_api_enrichment_score"],
                "cashrun_class": row["cashrun_class"],
                "industry_confirmation_count": row["industry_confirmation_count"],
                "industry_tipsters": "|".join(row["industry_tipsters"]),
                "blocker_flags": "|".join(row["blocker_flags"]),
                "suppress_flags": "|".join(row["suppress_flags"]),
                "leg_score": row["leg_score"],
                "leg_role": row["leg_role"],
                "trap_flags": "|".join(row["trap_flags"]),
                "source_completeness": row["source_completeness"],
            })


def build_detector(date_str: str) -> dict[str, Any]:
    verdicts = load_verdicts(date_str)
    if not verdicts:
        raise SystemExit(f"Missing local verdicts for {date_str}")

    standard_cards = load_standard_cards(date_str)
    resolver = RaceMetadataResolver(date=date_str)
    cashrun_index, cashrun_status = load_cashrun_index(date_str)
    industry_index, industry_status = load_industry_index(date_str)

    adapter = None
    if RacingAPIStatAdapter is not None:
        try:
            adapter = RacingAPIStatAdapter.from_supabase()
        except Exception:
            adapter = None

    candidates: list[dict[str, Any]] = []
    metadata_complete_n = 0
    enrichment_used_n = 0

    for verdict in verdicts:
        top = extract_top_prediction(verdict)
        if not top:
            continue

        race_id = verdict.get("race_id") or top.get("race_id") or ""
        meta = resolver.resolve(race_id, verdict.get("full_analysis"))
        race = standard_cards.get(race_id, {})
        runners = build_runner_lookup(race) if race else {}

        horse_id = top.get("horse_id", "")
        horse_name = top.get("horse") or ""
        runner = runners.get((horse_id, normalize_name(horse_name))) or runners.get(("", normalize_name(horse_name)))

        enrichment = maybe_enrich_from_adapter(adapter, runner, race or None, top)
        if enrichment.get("racing_api_enrichment_shadow_score") is not None:
            enrichment_used_n += 1

        course = verdict.get("course") or meta.course or race.get("course") or ""
        off_time = verdict.get("off_time") or meta.off_time or race.get("off_time") or ""
        race_name = verdict.get("race_name") or meta.race_name or race.get("race_name") or ""
        metadata_complete = bool(course and off_time and race_name)
        if metadata_complete:
            metadata_complete_n += 1

        cashrun_row = cashrun_index.get((race_id, horse_id))
        _, cashrun_label = cashrun_bonus(cashrun_row)

        industry_key = (normalize_course(course), normalize_time(off_time))
        industry_bucket = industry_index.get(industry_key, {})
        industry_counts = industry_bucket.get("horse_counts", {})
        industry_tipsters_map = industry_bucket.get("horse_tipsters", {})
        industry_count = int(industry_counts.get(normalize_name(horse_name), 0))
        industry_tipsters = industry_tipsters_map.get(normalize_name(horse_name), [])
        industry_conflicts = industry_count == 0 and bool(industry_counts)

        tier = str(verdict.get("tier") or verdict.get("decision_tier") or "").upper() or "?"
        blockers, trap_flags = trap_flags_for_candidate(tier, top, metadata_complete, industry_conflicts)
        source_state = source_completeness(metadata_complete, industry_count, cashrun_row, enrichment)

        vp = float(top.get("velo_prime_prob") or 0.0)
        place_prob = float(top.get("place_prob") or 0.0)
        mds = float(top.get("market_deception_score") or 0.0)
        improvement = float(top.get("improvement_score") or 0.0)

        leg_score, score_breakdown = compute_leg_score(
            vp=vp,
            place_prob=place_prob,
            mds=mds,
            tier=tier,
            trap_flags=trap_flags,
            cashrun_row=cashrun_row,
            industry_count=industry_count,
            enrichment=enrichment,
            metadata_complete=metadata_complete,
        )
        leg_role = assign_leg_role(leg_score, vp, place_prob, trap_flags, source_state, industry_count, cashrun_label)

        candidates.append({
            "horse": horse_name,
            "horse_id": horse_id,
            "race_id": race_id,
            "course": course,
            "off_time": normalize_time(off_time),
            "race_name": race_name,
            "vp": round(vp, 4),
            "decision_tier": tier,
            "place_prob": round(place_prob, 4),
            "mds": round(mds, 4),
            "improvement_score": round(improvement, 4),
            "candidate_execution_allowed": top.get("candidate_execution_allowed"),
            "racing_api_enrichment_score": enrichment.get("racing_api_enrichment_shadow_score"),
            "racing_api_connection_score": enrichment.get("racing_api_connection_shadow_score"),
            "racing_api_course_score": enrichment.get("racing_api_course_shadow_score"),
            "racing_api_distance_score": enrichment.get("racing_api_distance_shadow_score"),
            "cashrun_class": cashrun_label,
            "cashrun_score": float(cashrun_row.get("total_score") or 0.0) if cashrun_row else None,
            "industry_confirmation_count": industry_count,
            "industry_tipsters": industry_tipsters,
            "blocker_flags": blockers,
            "suppress_flags": blockers,
            "leg_score": leg_score,
            "leg_role": leg_role,
            "trap_flags": trap_flags,
            "source_completeness": source_state,
            "score_breakdown": score_breakdown,
            "candidate_execution_visibility": "VISIBILITY_ONLY",
        })

    candidates.sort(key=lambda item: (-float(item["leg_score"]), parse_sort_time(item["off_time"])))
    day_regime = classify_day(candidates)

    folds = {
        "strongest_2_fold": choose_best_fold(candidates, 2, day_regime) or {"generated": False, "reason": "SUPPRESSED"},
        "strongest_3_fold": choose_best_fold(candidates, 3, day_regime) or {"generated": False, "reason": "SUPPRESSED"},
        "strongest_4_fold": choose_best_fold(candidates, 4, day_regime) or {"generated": False, "reason": "SUPPRESSED"},
        "controlled_5_fold": choose_best_fold(candidates, 5, day_regime) or {"generated": False, "reason": "SUPPRESSED"},
        "speculative_6_fold": choose_best_fold(candidates, 6, day_regime) or {"generated": False, "reason": "SUPPRESSED"},
    }

    role_counts = {role: 0 for role in ["BANKER", "GLUE", "BOOSTER", "WILDCARD", "TRAP", "BLOCKED"]}
    for candidate in candidates:
        role_counts[candidate["leg_role"]] += 1

    trap_legs = [candidate for candidate in candidates if candidate["leg_role"] == "TRAP"]
    rejected_legs = [
        {
            "horse": candidate["horse"],
            "course": candidate["course"],
            "off_time": candidate["off_time"],
            "leg_role": candidate["leg_role"],
            "reasons": candidate["trap_flags"] or candidate["blocker_flags"] or ["LOW_CHAIN_SCORE"],
        }
        for candidate in candidates
        if candidate["leg_role"] in {"TRAP", "BLOCKED"} or candidate["leg_score"] < 40.0
    ]

    return {
        "date": date_str,
        "status": "SHADOW_OPERATOR_ONLY",
        "lane": "ACCA_LANE_V1",
        "day_regime": day_regime,
        "candidates_scanned": len(candidates),
        "cashrun_status": cashrun_status,
        "industry_status": industry_status,
        "racing_api_enrichment_status": "USED" if enrichment_used_n else "MISSING_OPTIONAL",
        "source_summary": {
            "metadata_complete_n": metadata_complete_n,
            "metadata_total_n": len(candidates),
            "metadata_coverage": round(metadata_complete_n / len(candidates), 4) if candidates else 0.0,
        },
        "role_counts": role_counts,
        "folds": folds,
        "trap_legs": trap_legs,
        "rejected_legs": rejected_legs,
        "candidates": candidates,
    }


def save_report(report: dict[str, Any]) -> None:
    date_str = report["date"]
    base = DATA / f"acca_lane_report_{date_str}"
    base.with_suffix(".json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    base.with_suffix(".md").write_text(render_md(report), encoding="utf-8")
    write_csv(base.with_suffix(".csv"), report["candidates"])

    lines = [
        f"ACCA OPERATOR CARD - {date_str}",
        "",
        f"Day regime: {report['day_regime']}",
        "",
    ]
    for label in ("strongest_2_fold", "strongest_3_fold", "strongest_4_fold", "controlled_5_fold", "speculative_6_fold"):
        fold = report["folds"][label]
        lines.append(f"{label}:")
        if not fold.get("generated"):
            lines.append("SUPPRESSED")
        else:
            for leg in fold["legs"]:
                lines.append(
                    f"- {leg['off_time']} {leg['course']} | {leg['horse']} | {leg['leg_role']} | VP={leg['vp']:.4f} | MDS={leg['mds']:.4f} | PLACE={leg['place_prob']:.4f}"
                )
        lines.append("")
    if report["trap_legs"]:
        lines.append("Trap legs to avoid:")
        for trap in report["trap_legs"][:10]:
            lines.append(f"- {trap['off_time']} {trap['course']} | {trap['horse']} | {', '.join(trap['trap_flags'])}")
        lines.append("")
    (DATA / f"acca_operator_card_{date_str}.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Build ACCA_LANE_V1 shadow operator report")
    parser.add_argument("--date", required=True, help="YYYY-MM-DD")
    args = parser.parse_args()

    report = build_detector(args.date)
    save_report(report)
    print(f"ACCA_LANE_V1 PASS {args.date} {report['day_regime']} scanned={report['candidates_scanned']}")


if __name__ == "__main__":
    main()
