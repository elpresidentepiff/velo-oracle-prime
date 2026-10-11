#!/usr/bin/env python3
"""
Model Suggestions builder — DASHBOARD-MODEL-SUGGESTIONS-01.

Read-only dashboard consumer. Joins together whatever pre-race model
artifacts already exist on disk for a given race day, one row per
(race, model_label, horse). Never scores, trains, promotes, stakes, or
writes anywhere. If an artifact is missing, the lane is reported as
MISSING_ARTIFACT with its expected source_path — it is never silently
dropped and never fabricated.

Every row is a CURRENT-DAY RUNTIME SUGGESTION, not canonical post-race
truth. After results are in, these rows are expected to flow through the
canonical_model_scorecards spine (see scripts/ops/persist_canonical_model_scorecard.py),
not to be read from here.
"""
from __future__ import annotations

import csv
import json
import os
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]

SUGGESTION_STATUS_LABEL = "CURRENT_DAY_RUNTIME_SUGGESTION_NOT_RESULT_TRUTH"

MODEL_LABELS = [
    "MAIN_VELO_PRIME",
    "SQPE_NO_RPR_SHADOW",
    "NEW_BUILD_LANE_A",
    "NEW_BUILD_LANE_B",
    "NEW_BUILD_LANE_C",
    "NEW_BUILD_POLICY_V1",
    "OLD_VELO_WIN",
    "OLD_VELO_PLACE",
    "OLD_VELO_LONGSHOT",
    "CHAMPION_INTENT_SHADOW",
]


# Cloud-native production order.  These names are the canonical identities
# persisted in public.canonical_model_scorecards by the current scoring stack.
# Keep the legacy MODEL_LABELS above for local-artifact fallback only.
CANONICAL_MODEL_ORDER = [
    "MAIN_VELO_PRIME",
    "SQPE_NO_RPR_SHADOW",
    "SQPE_MDS_SHADOW_V1",
    "MDS_HEAVY_SHADOW_V1",
    "MARKET_BLIND_CORE_SHADOW_V1",
    "CALIBRATED_G_SHADOW_V1",
    "CAPTAIN_VELO_VALUE_V1",
    "NEW_BUILD_LANE_A_MODEL",
    "NEW_BUILD_LANE_B_MODEL",
    "NEW_BUILD_LANE_C_MODEL",
    "CHAMPION_INTENT_SHADOW",
    "MIDPRICE_SPECIALIST_SHADOW",
    "OLD_VELO_WIN_ROLE",
    "OLD_VELO_PLACE_ROLE",
    "OLD_VELO_LONGSHOT_ROLE",
    "PASSPORT_STRENGTH_SCORE_PROXY",
]


def _load_json(path: Path, default=None) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    try:
        return [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]
    except Exception:
        return []


def _read_csv(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _canonical_supabase_top_picks(date_str: str) -> tuple[list[dict], str | None]:
    """Read captured rank-1 model outputs from the shared production truth store.

    Railway runs the web app and the scoring worker in separate containers, so
    today's scorer artifacts are not guaranteed to exist on the web container's
    filesystem.  canonical_model_scorecards is the durable cross-service bridge.
    This is read-only and never performs scoring or writes.
    """
    sb_url = (os.getenv("SUPABASE_URL") or "").rstrip("/")
    sb_key = (
        os.getenv("SUPABASE_SERVICE_ROLE_KEY")
        or os.getenv("SUPABASE_SERVICE_KEY")
        or os.getenv("SUPABASE_KEY")
        or ""
    )
    if not sb_url or not sb_key:
        return [], "Supabase credentials unavailable in dashboard runtime"

    select_cols = ",".join(
        [
            "run_date",
            "race_id",
            "course",
            "off_time",
            "model_name",
            "lane_name",
            "source_path",
            "source_field",
            "rank",
            "horse",
            "horse_id",
            "score",
            "policy_decision",
            "stake_authorised",
            "dashboard_visible",
            "notes",
            "result_position",
            "created_at",
        ]
    )
    query = urllib.parse.urlencode(
        {
            "select": select_cols,
            "run_date": f"eq.{date_str}",
            "rank": "eq.1",
            "order": "off_time.asc,course.asc,model_name.asc",
        }
    )
    req = urllib.request.Request(
        f"{sb_url}/rest/v1/canonical_model_scorecards?{query}",
        headers={
            "apikey": sb_key,
            "Authorization": f"Bearer {sb_key}",
            "Accept": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=12) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except Exception as exc:
        return [], f"{type(exc).__name__}: {exc}"

    if not isinstance(payload, list):
        return [], "Supabase canonical model response was not a list"
    return payload, None


def _canonical_row_to_suggestion(row: dict) -> dict:
    score = row.get("score")
    try:
        score = float(score) if score is not None else None
    except (TypeError, ValueError):
        score = None
    return {
        "date": str(row.get("run_date") or ""),
        "race_id": str(row.get("race_id") or ""),
        "course": row.get("course") or "",
        "off_time": row.get("off_time"),
        "model_label": row.get("model_name") or "UNKNOWN",
        "lane_name": row.get("lane_name") or row.get("model_name") or "UNKNOWN",
        "rank": row.get("rank"),
        "horse": row.get("horse") or "",
        "horse_id": str(row.get("horse_id") or ""),
        "score": score,
        "source_path": row.get("source_path") or "public.canonical_model_scorecards",
        "source_field": row.get("source_field") or "score",
        "policy_decision": row.get("policy_decision"),
        "stake_authorised": bool(row.get("stake_authorised")),
        "promotion_eligible": False,
        "dashboard_visible": bool(row.get("dashboard_visible")),
        "suggestion_status": "CANONICAL_CURRENT_DAY_CAPTURE",
        "notes": row.get("notes") or "Durable rank-1 capture from public.canonical_model_scorecards",
        "capture_source": "public.canonical_model_scorecards",
        "result_position_present": row.get("result_position") is not None,
        "captured_at": row.get("created_at"),
    }


def _base_row(*, date: str, race_id: str, course: str, off_time: Any, model_label: str,
              lane_name: str, rank: Any, horse: str, horse_id: str, score: Any,
              source_path: str, source_field: str, policy_decision: Any = None,
              notes: str = "") -> dict:
    return {
        "date": date,
        "race_id": str(race_id or ""),
        "course": course or "",
        "off_time": off_time,
        "model_label": model_label,
        "lane_name": lane_name,
        "rank": rank,
        "horse": horse or "",
        "horse_id": str(horse_id or ""),
        "score": score,
        "source_path": source_path,
        "source_field": source_field,
        "policy_decision": policy_decision,
        "stake_authorised": False,
        "promotion_eligible": False,
        "dashboard_visible": True,
        "suggestion_status": SUGGESTION_STATUS_LABEL,
        "notes": notes,
    }


def _missing(model_label: str, expected_source_path: str, reason: str) -> dict:
    return {
        "model_label": model_label,
        "status": "MISSING_ARTIFACT",
        "expected_source_path": expected_source_path,
        "reason": reason,
        "dashboard_visible": True,
        "suggestion_status": SUGGESTION_STATUS_LABEL,
    }


def _find_runner_snapshot_path(date_str: str) -> Path | None:
    date_tag = date_str.replace("-", "_")
    candidates = sorted(
        (ROOT / "data").glob(f"runner_snapshots_{date_tag}_*.jsonl"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    return candidates[0] if candidates else None


def _find_intent_shadow_scorecard_path(date_str: str) -> Path | None:
    """The Part-C shadow scorecard used a one-off literal filename
    (data/reports/july06_intent_shadow_scorecard.csv) rather than a
    date-parameterised one. Try the sane future convention first, then the
    known July 06 literal name, so this endpoint still works for other
    dates once that script is generalised."""
    date_tag = date_str.replace("-", "_")
    generic = ROOT / "data" / "reports" / f"intent_shadow_scorecard_{date_tag}.csv"
    if generic.exists():
        return generic
    try:
        from datetime import datetime
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        legacy = ROOT / "data" / "reports" / f"{dt.strftime('%B').lower()}{dt.day:02d}_intent_shadow_scorecard.csv"
        if legacy.exists():
            return legacy
    except ValueError:
        pass
    return generic


def build_main_velo_prime(date_str: str) -> tuple[list[dict], dict | None]:
    path = _find_runner_snapshot_path(date_str)
    expected = str((ROOT / "data" / f"runner_snapshots_{date_str.replace('-', '_')}_*.jsonl").relative_to(ROOT))
    if path is None:
        return [], _missing("MAIN_VELO_PRIME", expected, "No runner_snapshots file found for this date")
    rows = _read_jsonl(path)
    source_path = str(path.relative_to(ROOT))
    by_race: dict[str, list[dict]] = {}
    for r in rows:
        by_race.setdefault(str(r.get("race_id") or ""), []).append(r)
    out = []
    for race_id, race_rows in by_race.items():
        ranked = sorted(race_rows, key=lambda r: -(float(r.get("velo_prime_prob") or 0.0)))
        for i, r in enumerate(ranked, start=1):
            out.append(_base_row(
                date=date_str, race_id=race_id, course=r.get("course"), off_time=r.get("off_time"),
                model_label="MAIN_VELO_PRIME", lane_name="MAIN_VELO_PRIME", rank=i,
                horse=r.get("horse"), horse_id=r.get("horse_id"),
                score=float(r.get("velo_prime_prob") or 0.0),
                source_path=source_path, source_field="velo_prime_prob",
            ))
    return out, None


def build_sqpe_no_rpr_shadow(date_str: str) -> tuple[list[dict], dict | None]:
    path = _find_runner_snapshot_path(date_str)
    expected = str((ROOT / "data" / f"runner_snapshots_{date_str.replace('-', '_')}_*.jsonl").relative_to(ROOT))
    if path is None:
        return [], _missing("SQPE_NO_RPR_SHADOW", expected, "No runner_snapshots file found for this date")
    rows = _read_jsonl(path)
    source_path = str(path.relative_to(ROOT))
    by_race: dict[str, list[dict]] = {}
    for r in rows:
        by_race.setdefault(str(r.get("race_id") or ""), []).append(r)
    out = []
    for race_id, race_rows in by_race.items():
        ranked = sorted(race_rows, key=lambda r: -(float(r.get("sqpe_no_rpr_shadow_prob") or 0.0)))
        for i, r in enumerate(ranked, start=1):
            out.append({
                **_base_row(
                    date=date_str, race_id=race_id, course=r.get("course"), off_time=r.get("off_time"),
                    model_label="SQPE_NO_RPR_SHADOW", lane_name="SQPE_NO_RPR_SHADOW", rank=i,
                    horse=r.get("horse"), horse_id=r.get("horse_id"),
                    score=float(r.get("sqpe_no_rpr_shadow_prob") or 0.0),
                    source_path=source_path, source_field="sqpe_no_rpr_shadow_prob",
                    notes="SHADOW_ONLY: no-RPR feature ablation, not a live model",
                ),
                "suggestion_status": "SHADOW_ONLY",
            })
    return out, None


def build_new_build_lane(date_str: str, lane: str) -> tuple[list[dict], dict | None]:
    """lane in {'a', 'b', 'c'} -> NEW_BUILD_LANE_A/B/C, top-3 only per race."""
    date_tag = date_str.replace("-", "_")
    path = ROOT / "data" / "new_build" / "reports" / f"two_lane_readiness_{date_tag}.json"
    model_label = f"NEW_BUILD_LANE_{lane.upper()}"
    if not path.exists():
        return [], _missing(model_label, str(path.relative_to(ROOT)), "two_lane_readiness report not found for this date")
    report = _load_json(path, {}) or {}
    scorecards = report.get("race_day_scorecards") or []
    source_path = str(path.relative_to(ROOT))
    field = f"lane_{lane}_top3"
    out = []
    for card in scorecards:
        race_id = str(card.get("race_id") or "")
        top3 = card.get(field) or []
        for pick in top3:
            out.append(_base_row(
                date=date_str, race_id=race_id, course=card.get("course"), off_time=card.get("off_time"),
                model_label=model_label, lane_name=model_label, rank=pick.get("rank"),
                horse=pick.get("horse"), horse_id=pick.get("horse_id"),
                score=pick.get("prob"),
                source_path=source_path, source_field=f"race_day_scorecards[].{field}",
                notes="Top-3 only, per two_lane_readiness report shape",
            ))
    if not out:
        return [], _missing(model_label, source_path, "Readiness report present but has no rows for this lane")
    return out, None


def build_new_build_policy_v1(date_str: str) -> tuple[list[dict], dict | None]:
    date_tag = date_str.replace("-", "_")
    path = ROOT / "data" / "new_build" / "reports" / f"decision_policy_v1_{date_tag}.json"
    if not path.exists():
        return [], _missing("NEW_BUILD_POLICY_V1", str(path.relative_to(ROOT)), "decision_policy_v1 report not found for this date")
    report = _load_json(path, {}) or {}
    summary = report.get("summary") or {}
    source_path = str(path.relative_to(ROOT))
    out = []
    lane_pick_keys = {
        "WIN_TRUST": "win_trust_picks",
        "FRAME_TRUST": "frame_trust_picks",
        "NO_EDGE": "no_edge_picks",
        "LOW_DATA": "low_data_picks",
        "SUPPRESS": "suppress_picks",
    }
    for policy_decision, key in lane_pick_keys.items():
        for pick in summary.get(key) or []:
            out.append(_base_row(
                date=date_str, race_id=pick.get("race_id"), course=pick.get("course"), off_time=pick.get("off_time"),
                model_label="NEW_BUILD_POLICY_V1", lane_name="NEW_BUILD_POLICY_V1", rank=pick.get("rank"),
                horse=pick.get("horse"), horse_id=pick.get("horse_id"), score=pick.get("prob"),
                source_path=source_path, source_field=f"summary.{key}",
                policy_decision=policy_decision,
                notes="Policy decision only — not a model rank; see NEW_BUILD_LANE_A/B/C for ranks",
            ))
    if not out:
        return [], _missing("NEW_BUILD_POLICY_V1", source_path, "Policy report present but has no picks")
    return out, None


def build_old_velo_role(date_str: str, role: str) -> tuple[list[dict], dict | None]:
    """role in {'WIN', 'PLACE', 'LONGSHOT'} -> OLD_VELO_WIN/PLACE/LONGSHOT."""
    date_tag = date_str.replace("-", "_")
    path = ROOT / "data" / f"velo_prime_verdicts_{date_tag}.json"
    model_label = f"OLD_VELO_{role}"
    if not path.exists():
        return [], _missing(model_label, str(path.relative_to(ROOT)), "velo_prime_verdicts file not found for this date")
    raw = _load_json(path, [])
    if not isinstance(raw, list):
        return [], _missing(model_label, str(path.relative_to(ROOT)), "velo_prime_verdicts file is not a list")
    field = {"WIN": "velo_prime_prob", "PLACE": "place_prob", "LONGSHOT": "longshot_prob"}[role]
    source_path = str(path.relative_to(ROOT))
    out = []
    for verdict in raw:
        top = verdict.get("top") or {}
        out.append(_base_row(
            date=date_str, race_id=verdict.get("race_id"), course=verdict.get("course"), off_time=verdict.get("off_time"),
            model_label=model_label, lane_name=model_label, rank=1,
            horse=top.get("horse"), horse_id=top.get("horse_id"), score=top.get(field),
            source_path=source_path, source_field=f"top.{field}",
            notes=f"Old VELO {role} role — kept separate from other Old VELO roles, not mixed",
        ))
    return out, None


def build_champion_intent_shadow(date_str: str) -> tuple[list[dict], dict | None]:
    path = _find_intent_shadow_scorecard_path(date_str)
    expected = str(path.relative_to(ROOT)) if path else f"data/reports/intent_shadow_scorecard_{date_str.replace('-', '_')}.csv"
    if not path or not path.exists():
        return [], _missing("CHAMPION_INTENT_SHADOW", expected, "Intent shadow scorecard not found for this date")
    rows = _read_csv(path)
    source_path = str(path.relative_to(ROOT))
    out = []
    for r in rows:
        out.append({
            "date": date_str,
            "race_id": r.get("race_id", ""),
            "course": r.get("course", ""),
            "off_time": r.get("off_time"),
            "model_label": "CHAMPION_INTENT_SHADOW",
            "lane_name": "CHAMPION_INTENT_SHADOW",
            "rank": int(r["rank_in_race"]) if r.get("rank_in_race") else None,
            "horse": r.get("horse", ""),
            "horse_id": r.get("rp_uid", ""),
            "score": float(r["champion_intent_shadow_prob"]) if r.get("champion_intent_shadow_prob") else None,
            "source_path": source_path,
            "source_field": "champion_intent_shadow_prob",
            "policy_decision": None,
            # Hard safety values — never sourced from the CSV, always literal here.
            "stake_authorised": False,
            "promotion_eligible": False,
            "dashboard_visible": True,
            "suggestion_status": "SHADOW_ONLY",
            "notes": "INTENT_ADDS_SIGNAL research verdict on 2025 unseen holdout; not promoted, not staked",
        })
    return out, None


LANE_BUILDERS = {
    "MAIN_VELO_PRIME": lambda d: build_main_velo_prime(d),
    "SQPE_NO_RPR_SHADOW": lambda d: build_sqpe_no_rpr_shadow(d),
    "NEW_BUILD_LANE_A": lambda d: build_new_build_lane(d, "a"),
    "NEW_BUILD_LANE_B": lambda d: build_new_build_lane(d, "b"),
    "NEW_BUILD_LANE_C": lambda d: build_new_build_lane(d, "c"),
    "NEW_BUILD_POLICY_V1": lambda d: build_new_build_policy_v1(d),
    "OLD_VELO_WIN": lambda d: build_old_velo_role(d, "WIN"),
    "OLD_VELO_PLACE": lambda d: build_old_velo_role(d, "PLACE"),
    "OLD_VELO_LONGSHOT": lambda d: build_old_velo_role(d, "LONGSHOT"),
    "CHAMPION_INTENT_SHADOW": lambda d: build_champion_intent_shadow(d),
}


def build_model_suggestions(date_str: str, race_id: str | None = None) -> dict:
    # Production-first: the scoring worker and web dashboard are separate
    # Railway containers.  Read the durable canonical capture from Supabase so
    # the dashboard sees every model lane that actually ran, regardless of
    # which container produced its local artifact.
    canonical_rows, canonical_error = _canonical_supabase_top_picks(date_str)
    if canonical_rows:
        # Anchor every lane to the same production race universe as MAIN_VELO_PRIME.
        # Some research shadows intentionally score wider international cards;
        # those must not leak into the operator's canonical GB/IRE race-day view.
        main_race_ids = {
            str(r.get("race_id") or "")
            for r in canonical_rows
            if r.get("model_name") == "MAIN_VELO_PRIME"
        }
        if main_race_ids:
            canonical_rows = [
                r for r in canonical_rows
                if str(r.get("race_id") or "") in main_race_ids
            ]

        rows = [_canonical_row_to_suggestion(r) for r in canonical_rows]
        if race_id:
            rows = [r for r in rows if r["race_id"] == str(race_id)]

        rows.sort(
            key=lambda r: (
                r.get("off_time") or "",
                r.get("course") or "",
                r.get("model_label") or "",
            )
        )
        counts_by_label: dict[str, int] = {}
        for r in rows:
            label = r["model_label"]
            counts_by_label[label] = counts_by_label.get(label, 0) + 1

        discovered = sorted(counts_by_label.keys())
        requested = list(CANONICAL_MODEL_ORDER)
        for label in discovered:
            if label not in requested:
                requested.append(label)

        missing = [
            _missing(
                label,
                "public.canonical_model_scorecards",
                "No rank-1 canonical capture found for this date",
            )
            for label in requested
            if label not in counts_by_label
        ]
        return {
            "date": date_str,
            "race_id": race_id,
            "source": "SUPABASE_CANONICAL_CAPTURE",
            "suggestion_status": "CANONICAL_CURRENT_DAY_CAPTURE",
            "result_truth": False,
            "staking_instruction": False,
            "promotion_action": False,
            "canonical_post_race_learning": False,
            "no_supabase_writes": True,
            "supabase_read_only": True,
            "models_requested": requested,
            "models_available": discovered,
            "models_missing": [m["model_label"] for m in missing],
            "row_counts_by_model": counts_by_label,
            "missing_artifacts": missing,
            "rows": rows,
        }

    # Local fallback is retained for development / old dates where canonical
    # capture is unavailable. Missing artifacts remain explicit.
    rows: list[dict] = []
    missing: list[dict] = []
    for label in MODEL_LABELS:
        lane_rows, miss = LANE_BUILDERS[label](date_str)
        if miss:
            missing.append(miss)
        rows.extend(lane_rows)

    if race_id:
        rows = [r for r in rows if r["race_id"] == str(race_id)]

    rows.sort(key=lambda r: (r.get("off_time") or "", r.get("course") or "", r.get("model_label"), r.get("rank") or 999))

    counts_by_label: dict[str, int] = {}
    for r in rows:
        counts_by_label[r["model_label"]] = counts_by_label.get(r["model_label"], 0) + 1

    return {
        "date": date_str,
        "race_id": race_id,
        "source": "LOCAL_ARTIFACT_FALLBACK",
        "canonical_read_error": canonical_error,
        "suggestion_status": SUGGESTION_STATUS_LABEL,
        "result_truth": False,
        "staking_instruction": False,
        "promotion_action": False,
        "canonical_post_race_learning": False,
        "no_supabase_writes": True,
        "models_requested": MODEL_LABELS,
        "models_available": sorted(counts_by_label.keys()),
        "models_missing": [m["model_label"] for m in missing],
        "row_counts_by_model": counts_by_label,
        "missing_artifacts": missing,
        "rows": rows,
    }
