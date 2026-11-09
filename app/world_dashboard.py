"""Pure helpers for the world-day / VELO-vs-FormFav dashboard endpoints.

Kept free of FastAPI and I/O so they are unit-testable. Everything here is a
read-only presentation of shadow data: FormFav never feeds Prime scoring.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime
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


RICH_CONTEXT_FITTED_STATUS = "SHADOW_FITTED"
RICH_CONTEXT_UNSCORED_STATUS = "NO_SCORES_FOR_DATE"

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


def _utc_datetime(value: Any) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(UTC)


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
        out.update(
            {
                f"{family}_before": before,
                f"{family}_now": now,
                f"{family}_before_pct": pct(before),
                f"{family}_now_pct": pct(now),
            }
        )
    out["formfav_now"] = total("formfav_now")
    out["formfav_now_pct"] = pct(out["formfav_now"])
    out["packet_batches"] = max((_int(r.get("packet_batches")) or 0 for r in rows), default=0)
    out["latest_packet_at"] = max((r["latest_packet_at"] for r in rows if r.get("latest_packet_at")), default=None)
    return out


def rich_context_challenger_overlay(
    packets: list[dict[str, Any]] | None,
    scores: list[dict[str, Any]] | None,
    runner_rows: list[dict[str, Any]] | None = None,
    *,
    packet_read_status: str | None = None,
    score_read_status: str | None = None,
    runner_read_status: str | None = None,
) -> dict[str, Any]:
    """Join fitted challenger scores to immutable packets by the packet hash.

    This is deliberately a presentation-only exact-identity join.  A score is
    displayable only when it points at a packet from the requested date and
    retains the hard shadow boundary.  Horse names are attached only through
    the canonical ``(race_id, horse_id)`` pair; names are never identity keys.

    If several fitted versions exist for a date, only the version with the
    newest score timestamp is shown. Within that version, each race uses only
    its newest exact ``scored_at`` batch. Versions and repeated batches are
    never blended. A failed mandatory read returns no partial selection.
    """
    reads = {
        "packets": packet_read_status or ("OK" if packets is not None else "READ_FAILED"),
        "scores": score_read_status or ("OK" if scores is not None else "READ_FAILED"),
        "runner_labels": runner_read_status or ("OK" if runner_rows is not None else "READ_FAILED"),
    }
    mandatory_failures = [name for name in ("packets", "scores") if reads[name] != "OK"]
    if mandatory_failures:
        return {
            "status": "OVERLAY_UNAVAILABLE",
            "model_version": None,
            "read_availability": reads,
            "read_failures": mandatory_failures,
            "packet_rows": None,
            "immutable_packet_rows": None,
            "observed_score_rows": None,
            "score_rows": None,
            "version_score_rows": None,
            "current_score_rows": None,
            "linked_rows": 0,
            "linked_current_rows": 0,
            "orphan_scores": 0,
            "unsafe_rows": 0,
            "invalid_batch_rows": 0,
            "superseded_rows": 0,
            "other_model_version_rows": 0,
            "ambiguous_batch_races": 0,
            "ranked_rows": 0,
            "races": 0,
            "rank_one_rows": 0,
            "coverage_pct": None,
            "current_coverage_pct": None,
            "latest_scored_at": None,
            "runners": [],
            "selections": [],
        }

    packet_by_hash = {
        str(row.get("input_sha256")): row
        for row in (packets or [])
        if row.get("input_sha256")
    }
    safe_scores = [
        row
        for row in (scores or [])
        if row.get("production_influence") is False and row.get("paper_sim_only") is True
    ]
    unsafe_rows = len(scores or []) - len(safe_scores)
    timestamped_scores = [
        row for row in safe_scores if _utc_datetime(row.get("scored_at")) is not None and row.get("model_version")
    ]
    invalid_batch_rows = len(safe_scores) - len(timestamped_scores)

    versions: dict[str, list[dict[str, Any]]] = {}
    for row in timestamped_scores:
        version = str(row.get("model_version") or "")
        if version:
            versions.setdefault(version, []).append(row)

    if not versions:
        status = "OVERLAY_INTEGRITY_FAILED" if invalid_batch_rows or unsafe_rows else RICH_CONTEXT_UNSCORED_STATUS
        return {
            "status": status,
            "model_version": None,
            "read_availability": reads,
            "read_failures": [],
            "packet_rows": len(packet_by_hash),
            "immutable_packet_rows": len(packet_by_hash),
            "observed_score_rows": len(scores or []),
            "score_rows": 0,
            "version_score_rows": 0,
            "current_score_rows": 0,
            "linked_rows": 0,
            "linked_current_rows": 0,
            "orphan_scores": 0,
            "unsafe_rows": unsafe_rows,
            "invalid_batch_rows": invalid_batch_rows,
            "superseded_rows": 0,
            "other_model_version_rows": 0,
            "ambiguous_batch_races": 0,
            "ranked_rows": 0,
            "races": 0,
            "rank_one_rows": 0,
            "coverage_pct": None,
            "current_coverage_pct": None,
            "latest_scored_at": None,
            "runners": [],
            "selections": [],
        }

    def version_order(item: tuple[str, list[dict[str, Any]]]) -> tuple[datetime, str]:
        version, rows = item
        latest = max(_utc_datetime(row["scored_at"]) for row in rows)
        return latest, version

    model_version, selected_scores = max(versions.items(), key=version_order)
    other_model_version_rows = len(timestamped_scores) - len(selected_scores)

    # A model version may score several immutable packet batches on the same
    # date. Select exactly one latest timestamp batch per race and report every
    # older row as superseded. ``scored_at`` is the persisted batch discriminator
    # available in v1; missing timestamps were excluded above rather than guessed.
    by_race: dict[str, dict[str, list[dict[str, Any]]]] = {}
    for row in selected_scores:
        batch_timestamp = _utc_datetime(row["scored_at"])
        assert batch_timestamp is not None  # filtered above
        by_race.setdefault(str(row.get("race_id") or ""), {}).setdefault(
            batch_timestamp.isoformat(), []
        ).append(row)
    current_scores: list[dict[str, Any]] = []
    superseded_rows = 0
    ambiguous_batch_races = 0
    for batches in by_race.values():
        latest_timestamp = max(batches)
        current_batch = batches[latest_timestamp]
        superseded_rows += sum(len(batch) for timestamp, batch in batches.items() if timestamp != latest_timestamp)
        horse_ids = [str(row.get("horse_id") or "") for row in current_batch]
        ranks = [_int(row.get("challenger_rank")) for row in current_batch]
        coherent_ranks = all(rank is not None for rank in ranks) and sorted(ranks) == list(
            range(1, len(current_batch) + 1)
        )
        if len(set(horse_ids)) != len(horse_ids) or not all(horse_ids) or not coherent_ranks:
            ambiguous_batch_races += 1
            continue
        current_scores.extend(current_batch)
    overlay_status = RICH_CONTEXT_FITTED_STATUS
    if invalid_batch_rows or ambiguous_batch_races:
        # Without a timestamp/version or a coherent 1..N ranking, v1 cannot
        # identify one complete batch safely. Fail the whole overlay rather
        # than publish a plausible-looking partial ranking.
        overlay_status = "OVERLAY_INTEGRITY_FAILED"
        current_scores = []

    # Latest exact-id runner label wins only for presentation.  It never changes
    # packet/score identity and cannot rescue a missing packet hash.
    runner_names: dict[tuple[str, str], tuple[str, str]] = {}
    for row in runner_rows or []:
        key = (str(row.get("race_id") or ""), str(row.get("horse_id") or ""))
        name = str(row.get("horse_name") or "")
        created = str(row.get("created_at") or "")
        if all(key) and name and created >= runner_names.get(key, ("", ""))[0]:
            runner_names[key] = (created, name)

    linked: list[dict[str, Any]] = []
    orphan_scores = 0
    for score in current_scores:
        packet = packet_by_hash.get(str(score.get("packet_input_sha256") or ""))
        if packet is None:
            orphan_scores += 1
            continue
        # The packet hash is authoritative, but mismatched duplicated identity
        # columns are a corrupt overlay row and must never be displayed.
        if str(score.get("race_id")) != str(packet.get("race_id")) or str(score.get("horse_id")) != str(
            packet.get("horse_id")
        ):
            orphan_scores += 1
            continue
        race_id = str(packet.get("race_id"))
        horse_id = str(packet.get("horse_id"))
        linked.append(
            {
                "race_id": race_id,
                "horse_id": horse_id,
                "horse_name": runner_names.get((race_id, horse_id), ("", None))[1],
                "packet_input_sha256": packet.get("input_sha256"),
                "model_version": model_version,
                "challenger_probability": score.get("challenger_probability"),
                "challenger_rank": _int(score.get("challenger_rank")),
                "scored_at": score.get("scored_at"),
                "paper_sim_only": True,
                "production_influence": False,
            }
        )

    linked.sort(
        key=lambda row: (
            row["race_id"],
            row["challenger_rank"] is None,
            row["challenger_rank"] or 0,
            row["horse_id"],
        )
    )
    selections = [row for row in linked if row["challenger_rank"] == 1]
    packet_rows = len(packet_by_hash)
    current_score_rows = len(current_scores)
    coverage = (
        round(100.0 * len(linked) / current_score_rows, 1)
        if current_score_rows and overlay_status == RICH_CONTEXT_FITTED_STATUS
        else None
    )
    return {
        "status": overlay_status,
        "model_version": model_version,
        "read_availability": reads,
        "read_failures": [],
        "packet_rows": packet_rows,
        "immutable_packet_rows": packet_rows,
        "observed_score_rows": len(scores or []),
        "score_rows": current_score_rows,
        "version_score_rows": len(selected_scores),
        "current_score_rows": current_score_rows,
        "linked_rows": len(linked),
        "linked_current_rows": len(linked),
        "orphan_scores": orphan_scores,
        "unsafe_rows": unsafe_rows,
        "invalid_batch_rows": invalid_batch_rows,
        "superseded_rows": superseded_rows,
        "other_model_version_rows": other_model_version_rows,
        "ambiguous_batch_races": ambiguous_batch_races,
        "ranked_rows": sum(1 for row in linked if row["challenger_rank"] is not None),
        "races": len({row["race_id"] for row in linked}),
        "rank_one_rows": len(selections),
        "coverage_pct": coverage,
        "current_coverage_pct": coverage,
        "latest_scored_at": max((str(row.get("scored_at") or "") for row in linked), default=None),
        "runners": linked,
        "selections": selections,
    }


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
        board.append(
            {
                "model": name,
                "label": label,
                "note": note,
                "lane": rows[0].get("lane_name"),
                "races": len(rows),
                "clean": len(clean),
                "unclean": len(rows) - len(clean),
                "comparable_with_prime": len(comparable),
                "agree_with_prime": sum(1 for r in comparable if r.get("agrees_with_prime")),
                "settled": len(settled),
                "settled_from_ingested": sum(1 for r in settled if r.get("result_source") == "ingested_results"),
                "won": sum(1 for r in settled if r.get("win")),
                "top3": sum(1 for r in settled if (_int(r.get("result_position")) or 99) <= 3),
            }
        )
    return board


def race_grid(picks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """One row per race with every model's top pick, in card order."""
    races: dict[str, dict[str, Any]] = {}
    for row in picks:
        race = races.setdefault(
            str(row.get("race_id")),
            {
                "race_id": row.get("race_id"),
                "course": row.get("course"),
                "off_time": row.get("off_time"),
                "off_minutes": row.get("off_minutes"),
                "prime_horse": row.get("prime_horse"),
                "cells": {},
            },
        )
        race["cells"][str(row.get("model_name"))] = {
            "horse": row.get("top_horse"),
            "clean": is_clean_pick(row),
            "agrees": bool(row.get("agrees_with_prime")),
            "position": _int(row.get("result_position")),
            "won": row.get("win"),
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

    The pick remains Prime's own.  A fitted Rich Context challenger is displayed
    separately and never substitutes for or mutates this production selection.
    """
    races = [
        {
            **r,
            "history": _obj(r.get("history")),
            "pace": _obj(r.get("pace")),
            "class_fit": _obj(r.get("class_fit")),
            "evidence_grade": evidence_grade(r),
        }
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


WORLD_MODEL = "existing_velo_prime_stack"
_NAME_SUFFIX = re.compile(r"\s*\([a-z]{2,3}\)\s*$", re.IGNORECASE)


def _name_key(name: Any) -> str:
    """Match a horse across providers: drop a trailing state/country tag like ``(Ny)``, keep letters."""
    return re.sub(r"[^a-z0-9]", "", _NAME_SUFFIX.sub("", str(name or "")).lower())


def _when(value: Any) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00").replace(" ", "T"))
    except (TypeError, ValueError):
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def _outcome(row: dict[str, Any]) -> str:
    basis = row.get("result_basis")
    if basis == "no_result":
        return "NO_RESULT"
    if basis not in ("final", "provisional"):
        return "PENDING"
    if row.get("won"):
        return "WON"
    return "PLACED" if row.get("framed") else "LOST"


def world_picks(
    rows: list[dict[str, Any]],
    formfav: list[dict[str, Any]],
    now: datetime | None = None,
) -> dict[str, Any]:
    """VELO's frozen World pick per race, with how much of a read each one is.

    The pick is the first-complete, pre-off freeze and is never rewritten. A pick is a clean read only
    when it is not tied and the lane wrote a single rank-1 row; with no market the score is price-blind;
    where a market exists the pick is nearly always the shortest price, so its strike rate is the
    favourite's. Nothing here feeds Prime and nothing is staked.
    """
    now = now or datetime.now(UTC)
    ff_by_race = {
        (str(f.get("country") or "").lower(), str(f.get("track") or "").lower(), _int(f.get("race_number"))): f
        for f in formfav
    }
    races: list[dict[str, Any]] = []
    for r in rows:
        off = _when(r.get("start_time"))
        ff = (
            ff_by_race.get(
                (str(r.get("country") or "").lower(), str(r.get("track") or "").lower(), _int(r.get("race_number")))
            )
            or {}
        )
        flags = []
        if r.get("tied_top"):
            flags.append("TIED")
        if (_int(r.get("rank1_rows")) or 1) > 1:
            flags.append("DUP_RANK")
        if r.get("price_state") != "REAL":
            flags.append("NO_MARKET")
        ff_pick = ff.get("pick1_name")
        races.append(
            {
                **r,
                "off_label": ff.get("off_uk") or (off.strftime("%H:%M") if off else ""),
                "upcoming": bool(off and off > now),
                "outcome": _outcome(r),
                "result_is_final": r.get("result_basis") == "final",
                "clean": "TIED" not in flags and "DUP_RANK" not in flags,
                "flags": flags,
                "formfav_pick": ff_pick,
                "formfav_win_prob": ff.get("pick1_win"),
                "agrees_with_formfav": (_name_key(ff_pick) == _name_key(r.get("pick_name"))) if ff_pick else None,
            }
        )
    races.sort(
        key=lambda x: (
            x["upcoming"] is False,
            _when(x.get("start_time")) or now,
            str(x.get("country")),
            str(x.get("track")),
            _int(x.get("race_number")) or 0,
        )
    )
    priced = [x for x in races if x.get("price_state") == "REAL"]
    final = [x for x in races if x["outcome"] != "PENDING" and x["result_is_final"] and x["outcome"] != "NO_RESULT"]
    final_clean = [x for x in final if x["clean"]]
    with_ff = [x for x in races if x["agrees_with_formfav"] is not None]
    by_country: dict[str, int] = {}
    for x in races:
        by_country[str(x.get("country"))] = by_country.get(str(x.get("country")), 0) + 1
    return {
        "races": races,
        "summary": {
            "races": len(races),
            "by_country": by_country,
            "upcoming": sum(1 for x in races if x["upcoming"]),
            "priced": len(priced),
            "no_market": len(races) - len(priced),
            "tied": sum(1 for x in races if "TIED" in x["flags"]),
            "dup_rank": sum(1 for x in races if "DUP_RANK" in x["flags"]),
            "priced_pick_is_shortest": sum(1 for x in priced if x.get("pick_is_shortest_price")),
            "agree_with_formfav": sum(1 for x in with_ff if x["agrees_with_formfav"]),
            "with_formfav": len(with_ff),
            "settled_final": len(final),
            "settled_provisional": sum(1 for x in races if x.get("result_basis") == "provisional"),
            "no_result": sum(1 for x in races if x["outcome"] == "NO_RESULT"),
            "won_final": sum(1 for x in final if x["outcome"] == "WON"),
            "placed_final": sum(1 for x in final if x["outcome"] in ("WON", "PLACED")),
            "clean_settled_final": len(final_clean),
            "clean_won_final": sum(1 for x in final_clean if x["outcome"] == "WON"),
            "note": (
                "Frozen before the off and never rewritten. With no market the score is price-blind. "
                "Where a market exists the pick is almost always the shortest price, so a strike rate "
                "there is the favourite's, not evidence of skill."
            ),
        },
    }
