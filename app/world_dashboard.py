"""Pure helpers for the world-day / VELO-vs-FormFav dashboard endpoints.

Kept free of FastAPI and I/O so they are unit-testable. Everything here is a
read-only presentation of shadow data: FormFav never feeds Prime scoring.
"""

from __future__ import annotations

import re
from typing import Any

SHADOW_BOUNDARY = {
    "shadow_only": True,
    "production_influence": False,
    "stake_authorised": False,
    "promotion_eligible": False,
}

_DATE = re.compile(r"\d{4}-\d{2}-\d{2}")


def valid_date(value: str | None) -> bool:
    """Dates go into a PostgREST query string, so accept only YYYY-MM-DD."""
    return bool(value and _DATE.fullmatch(value))


def summarise_velo_vs_formfav(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Head-to-head totals. Winners are counted only where a winner is known."""
    n = len(rows)
    agree = sum(1 for r in rows if r.get("agree_on_top_pick"))
    decided = [r for r in rows if r.get("winner_name")]
    final_decided = [r for r in decided if r.get("result_is_final")]
    in_top3 = [r for r in rows if isinstance(r.get("formfav_rank_of_velo_pick"), int)]
    return {
        "races": n,
        "agree": agree,
        "agree_pct": round(100.0 * agree / n, 1) if n else None,
        "with_winner": len(decided),
        "with_final_winner": len(final_decided),
        "velo_won": sum(1 for r in decided if r.get("velo_pick_won")),
        "formfav_won": sum(1 for r in decided if r.get("formfav_pick_won")),
        "velo_won_final": sum(1 for r in final_decided if r.get("velo_pick_won")),
        "formfav_won_final": sum(1 for r in final_decided if r.get("formfav_pick_won")),
        "velo_pick_in_formfav_top3": sum(1 for r in in_top3 if r["formfav_rank_of_velo_pick"] <= 3),
        "sample_note": "Small sample: treat as a lead, not an edge." if len(decided) < 100 else None,
    }


RICH_CONTEXT_STATUS = "AWAITING_FROZEN_MODEL_FIT"

PRIME = "MAIN_VELO_PRIME"

# Display order and honest labels. A lane that is not an independent opinion says so.
MODEL_META: dict[str, tuple[str, str | None]] = {
    "MAIN_VELO_PRIME": ("PRIME (MAIN)", "The production selection."),
    "SQPE_NO_RPR_SHADOW": ("NO-RPR", "Shadow. Same inputs minus RPR/TS."),
    "MDS_HEAVY_SHADOW_V1": ("MDS", "Shadow. Heavily overlaps Prime."),
    "CHAMPION_INTENT_SHADOW": ("CHAMPION INTENT", "Shadow. Writes several lists per race."),
    "NEW_BUILD_LANE_A_MODEL": ("NEW BUILD A", "Shadow lane A."),
    "NEW_BUILD_LANE_B_MODEL": ("NEW BUILD B", "Shadow lane B."),
    "OLD_VELO_WIN_ROLE": ("OLD VELO WIN", "Identical to Prime by construction. Not an independent opinion."),
    "OLD_VELO_PLACE_ROLE": ("OLD VELO PLACE", "Place-market role."),
    "OLD_VELO_LONGSHOT_ROLE": ("OLD VELO LONGSHOT", "Longshot role."),
    "PASSPORT_STRENGTH_SCORE_PROXY": ("PASSPORT (INPUT)", "A feature fed to New Build. Not a model output."),
}


def _int(value: Any) -> int | None:
    try:
        return None if value is None else int(value)
    except (TypeError, ValueError):
        return None


def is_clean_pick(row: dict[str, Any]) -> bool:
    """A top pick is a real read only if it is not tied and the lane wrote one rank-1 row.

    ``tie_status`` is ``N/A`` for lanes where tie detection does not apply; that is not a tie.
    """
    tied = str(row.get("tie_status") or "").upper().startswith(("TIED", "TIE_"))
    several = (_int(row.get("rank1_rows")) or 1) > 1
    return bool(row.get("top_horse")) and not tied and not several


def summarise_rich_context(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Rich Context evidence coverage for one race day, from the first packet batch to the latest."""
    runners = sum(_int(r.get("runners")) or 0 for r in rows)

    def total(key: str) -> int:
        return sum(_int(r.get(key)) or 0 for r in rows)

    def pct(part: int) -> float | None:
        return round(100.0 * part / runners, 1) if runners else None

    out: dict[str, Any] = {"races": len(rows), "runners": runners}
    for family in ("history", "spotlight"):
        before, now = total(f"{family}_before"), total(f"{family}_now")
        out.update({
            f"{family}_before": before, f"{family}_now": now,
            f"{family}_before_pct": pct(before), f"{family}_now_pct": pct(now),
        })
    out["formfav_now"] = total("formfav_now")
    out["formfav_now_pct"] = pct(out["formfav_now"])
    out["packet_batches"] = max((_int(r.get("packet_batches")) or 0 for r in rows), default=0)
    out["latest_packet_at"] = max((r["latest_packet_at"] for r in rows if r.get("latest_packet_at")), default=None)
    return out


def _model_order(name: str) -> tuple[int, str]:
    keys = list(MODEL_META)
    return (keys.index(name), name) if name in MODEL_META else (len(keys), name)


def model_scoreboard(picks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """One row per model: how often it agrees with Prime, and how its clean picks settled.

    Each model is counted on its own clean races, so denominators differ and are shown.
    Outcomes are counted only where a result exists. Never blends tied or multi-list picks in.
    """
    by_model: dict[str, list[dict[str, Any]]] = {}
    for row in picks:
        by_model.setdefault(str(row.get("model_name")), []).append(row)
    prime_clean = {r["race_id"] for r in by_model.get(PRIME, []) if is_clean_pick(r)}
    board: list[dict[str, Any]] = []
    for name in sorted(by_model, key=_model_order):
        rows = by_model[name]
        clean = [r for r in rows if is_clean_pick(r)]
        comparable = [r for r in clean if r["race_id"] in prime_clean]
        settled = [r for r in clean if _int(r.get("result_position")) is not None]
        label, note = MODEL_META.get(name, (name, None))
        board.append({
            "model": name, "label": label, "note": note,
            "lane": rows[0].get("lane_name"),
            "races": len(rows), "clean": len(clean), "unclean": len(rows) - len(clean),
            "comparable_with_prime": len(comparable),
            "agree_with_prime": sum(1 for r in comparable if r.get("agrees_with_prime")),
            "settled": len(settled),
            "won": sum(1 for r in settled if r.get("win")),
            "top3": sum(1 for r in settled if (_int(r.get("result_position")) or 99) <= 3),
        })
    return board


def race_grid(picks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """One row per race with every model's top pick, in card order."""
    races: dict[str, dict[str, Any]] = {}
    for row in picks:
        race = races.setdefault(str(row.get("race_id")), {
            "race_id": row.get("race_id"), "course": row.get("course"),
            "off_time": row.get("off_time"), "off_minutes": row.get("off_minutes"),
            "prime_horse": row.get("prime_horse"), "cells": {},
        })
        race["cells"][str(row.get("model_name"))] = {
            "horse": row.get("top_horse"), "clean": is_clean_pick(row),
            "agrees": bool(row.get("agrees_with_prime")),
            "position": _int(row.get("result_position")), "won": row.get("win"),
        }
    return sorted(
        races.values(),
        key=lambda r: (r["off_minutes"] is None, r["off_minutes"] or 0, str(r["race_id"])),
    )


def _obj(value: Any) -> dict[str, Any]:
    """A JSON object, or {} for missing / JSON null / anything else."""
    return value if isinstance(value, dict) else {}


def evidence_grade(row: dict[str, Any]) -> str:
    """How much beyond the FormFav baseline Velo holds on the pick. Not a quality or confidence score."""
    history = bool(_obj(row.get("history")))
    spotlight = bool(row.get("spotlight_families"))
    if history and spotlight:
        return "FULL"
    if history:
        return "HISTORY"
    if spotlight:
        return "SPOTLIGHT"
    return "FORMFAV ONLY"


def enriched_suggestions(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Prime's picks from the newest run with the evidence held on each pick.

    The pick is Prime's own: Rich Context has no fitted model and re-ranks nothing here.
    """
    races = [
        {**r, "history": _obj(r.get("history")), "pace": _obj(r.get("pace")),
         "class_fit": _obj(r.get("class_fit")), "evidence_grade": evidence_grade(r)}
        for r in rows
    ]
    moved = [r for r in races if abs(float(r.get("prob_delta") or 0.0)) > 0.00005]
    return {
        "races": races,
        "summary": {
            "races": len(races),
            "pick_changed": sum(1 for r in races if r.get("pick_changed")),
            "pick_probability_moved": len(moved),
            "with_history": sum(1 for r in races if r["history"]),
            "with_spotlight": sum(1 for r in races if r.get("spotlight_families")),
            "with_withdrawal": sum(1 for r in races if (_int(r.get("withdrawn")) or 0) > 0),
            "run_at": max((r["run_at"] for r in races if r.get("run_at")), default=None),
        },
    }
