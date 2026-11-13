"""Pure helpers for the world-day / VELO-vs-FormFav dashboard endpoints.

Kept free of FastAPI and I/O so they are unit-testable. Everything here is a
read-only presentation of shadow data: FormFav never feeds Prime scoring.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import Any
from zoneinfo import ZoneInfo

from src.velo.race_identity import (
    BLOCKED_LABEL,
    VERIFIED,
    parse_race_key,
    slugify,
    verify_race_identity,
    verify_selection,
)

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

    The pick is Prime's own: Rich Context has no fitted model and re-ranks nothing here.
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


# --- #189: no selection is shown for a race that is not proved to be one race -----------------
EVIDENCE_UNAVAILABLE = {
    "status": "RACECARD_MISMATCH",
    "reasons": ["IDENTITY_EVIDENCE_UNAVAILABLE"],
    "warnings": [],
    "active_runners": [],
    "non_runners": [],
    "label": BLOCKED_LABEL,
}


def build_identities(
    race_rows: list[dict[str, Any]] | None,
    runner_rows: list[dict[str, Any]] | None,
    now: datetime | None = None,
) -> dict[str, dict[str, Any]] | None:
    """``verify_race_identity`` for every stored race of a day. None when the evidence could not be
    read at all, which callers must treat as blocked, never as verified."""
    if race_rows is None or runner_rows is None:
        return None
    now = now or datetime.now(UTC)
    by_key: dict[str, list[dict[str, Any]]] = {}
    for row in runner_rows:
        by_key.setdefault(str(row.get("provider_race_key")), []).append(row)
    out: dict[str, dict[str, Any]] = {}
    for race in race_rows:
        key = str(race.get("provider_race_key"))
        ident = verify_race_identity(race, by_key.get(key, []), now=now)
        parsed = parse_race_key(key) or {}
        ident["country"] = str(race.get("country") or parsed.get("country") or "").lower()
        # formfav_race_picks has no race key: it is matched on (country, track, race number), and the
        # key slug is the stable spelling of the track when the display name is absent.
        ident["track_slug"] = slugify(race.get("track")) if race.get("track") else parsed.get("slug")
        out[key] = ident
    return out


def identity_for(identities: dict[str, dict[str, Any]] | None, key: Any) -> dict[str, Any]:
    if identities is None:
        return EVIDENCE_UNAVAILABLE
    return identities.get(str(key)) or {**EVIDENCE_UNAVAILABLE, "reasons": ["RACE_NOT_IN_RACECARD_STORE"]}


def _off_uk(value: Any) -> str:
    off = _when(value)
    return off.astimezone(ZoneInfo("Europe/London")).strftime("%H:%M") if off else ""


def _identity_view(ident: dict[str, Any]) -> dict[str, Any]:
    """What the dashboard shows about a race's verification, scratchings and source timestamps."""
    return {
        "identity_status": ident.get("status"),
        "identity_reasons": ident.get("reasons") or [],
        "identity_warnings": ident.get("warnings") or [],
        "local_race_date": ident.get("local_race_date"),
        "off_utc": ident.get("start_time_utc"),
        "racecard_checked_at": ident.get("racecard_checked_at"),
        "verified_field_size": len(ident.get("active_runners") or []) if ident.get("status") == VERIFIED else None,
        "non_runners": [r.get("name") for r in ident.get("non_runners") or []],
    }


def certify_formfav_picks(
    picks: list[dict[str, Any]],
    identities: dict[str, dict[str, Any]] | None,
) -> list[dict[str, Any]]:
    """FormFav's own picks with every one that is not in a verified field replaced by the block label.

    ``formfav_race_picks`` has no race key, so the race is found by (country, track, race number)
    inside the same racing date. The original names stay under ``audit_original_picks``.
    """
    by_race: dict[tuple, dict[str, Any]] = {}
    for i in (identities or {}).values():
        race_key = (i.get("country"), i.get("track_slug"), i.get("race_number"))
        # Two stored races answering to one (country, track, number) on one date is itself a collision.
        by_race[race_key] = (
            EVIDENCE_UNAVAILABLE | {"reasons": ["DUPLICATE_RACE_FOR_TRACK_AND_NUMBER"]} if race_key in by_race else i
        )
    out = []
    for p in picks:
        if identities is None:
            ident = EVIDENCE_UNAVAILABLE
        else:
            ident = by_race.get(
                (str(p.get("country") or "").lower(), slugify(p.get("track")), _int(p.get("race_number")))
            ) or {**EVIDENCE_UNAVAILABLE, "reasons": ["RACE_NOT_IN_RACECARD_STORE"]}
        shown = dict(p)
        audit = {}
        status = None
        for slot in ("pick1", "pick2", "pick3"):
            check = verify_selection(ident, p.get(f"{slot}_name"), p.get(f"{slot}_number"))
            audit[slot] = p.get(f"{slot}_name")
            if check["status"] not in (VERIFIED, "NO_PICK"):
                shown[f"{slot}_name"] = None
                shown[f"{slot}_win"] = None
            if slot == "pick1":
                status = check["status"]
        if ident.get("status") != VERIFIED:
            status = "RACECARD_MISMATCH"
        shown.update(_identity_view(ident))
        shown["selection_status"] = status
        shown["selection_label"] = BLOCKED_LABEL if status not in (VERIFIED, "NO_PICK") else None
        shown["audit_original_picks"] = audit
        if ident.get("start_time_utc"):
            shown["off_uk"] = _off_uk(ident.get("start_time_utc"))
        out.append(shown)
    return out


def world_picks(
    rows: list[dict[str, Any]],
    formfav: list[dict[str, Any]],
    now: datetime | None = None,
    identities: dict[str, dict[str, Any]] | None | bool = False,
) -> dict[str, Any]:
    """VELO's frozen World pick per race, with how much of a read each one is.

    The pick is the first-complete, pre-off freeze and is never rewritten. A pick is a clean read only
    when it is not tied and the lane wrote a single rank-1 row; with no market the score is price-blind;
    where a market exists the pick is nearly always the shortest price, so its strike rate is the
    favourite's. Nothing here feeds Prime and nothing is staked.
    """
    now = now or datetime.now(UTC)
    # identities=False keeps the pre-#189 behaviour for callers that have not been moved yet;
    # None means the evidence could not be read, so every pick is blocked.
    certify = identities is not False
    ff_by_race = {
        (str(f.get("country") or "").lower(), str(f.get("track") or "").lower(), _int(f.get("race_number"))): f
        for f in formfav
    }
    races: list[dict[str, Any]] = []
    for r in rows:
        ident = identity_for(identities, r.get("provider_race_key")) if certify else None
        if ident is not None:
            velo_check = verify_selection(ident, r.get("pick_name"))
        off = _when((ident or {}).get("start_time_utc") or r.get("start_time"))
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
        extra: dict[str, Any] = {}
        if ident is not None:
            ff_check = verify_selection(ident, ff_pick, ff.get("pick1_number"))
            extra = {
                **_identity_view(ident),
                "selection_status": velo_check["status"],
                "selection_label": velo_check["label"],
                "formfav_selection_status": ff_check["status"],
                "audit_original_picks": {
                    "velo": r.get("pick_name"),
                    "velo_second": r.get("second_name"),
                    "velo_third": r.get("third_name"),
                    "formfav": ff_pick,
                },
            }
            if velo_check["status"] != VERIFIED:
                flags.append(
                    "RACECARD_MISMATCH" if velo_check["status"] == "RACECARD_MISMATCH" else velo_check["status"]
                )
            if ident.get("status") != VERIFIED:
                ff_pick = None
            elif ff_check["status"] not in (VERIFIED, "NO_PICK"):
                ff_pick = None
        races.append(
            {
                **r,
                **extra,
                "off_label": (_off_uk(ident.get("start_time_utc")) if ident and ident.get("start_time_utc") else "")
                or ff.get("off_uk")
                or (off.strftime("%H:%M") if off else ""),
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
        if ident is not None and velo_check["status"] != VERIFIED:
            # Shown as RACECARD MISMATCH — NO VERIFIED SELECTION; the frozen pick itself is untouched
            # in world_model_scorecards and kept above under audit_original_picks.
            races[-1].update(
                {
                    "pick_name": None,
                    "second_name": None,
                    "third_name": None,
                    "pick_price": None,
                    "pick_score": None,
                    "clean": False,
                    "agrees_with_formfav": None,
                    "selection_label": BLOCKED_LABEL,
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
    blocked = [x for x in races if certify and x.get("selection_status") != VERIFIED]
    # A blocked race is never counted as a result: its result belongs to an unproved race.
    countable = [x for x in races if x not in blocked]
    priced = [x for x in countable if x.get("price_state") == "REAL"]
    final = [x for x in countable if x["outcome"] != "PENDING" and x["result_is_final"] and x["outcome"] != "NO_RESULT"]
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
            "no_market": len(countable) - len(priced),
            "tied": sum(1 for x in races if "TIED" in x["flags"]),
            "dup_rank": sum(1 for x in races if "DUP_RANK" in x["flags"]),
            "priced_pick_is_shortest": sum(1 for x in priced if x.get("pick_is_shortest_price")),
            "agree_with_formfav": sum(1 for x in with_ff if x["agrees_with_formfav"]),
            "with_formfav": len(with_ff),
            "settled_final": len(final),
            "settled_provisional": sum(1 for x in countable if x.get("result_basis") == "provisional"),
            "no_result": sum(1 for x in countable if x["outcome"] == "NO_RESULT"),
            "verified": len(races) - len(blocked) if certify else None,
            "racecard_mismatch": sum(1 for x in blocked if x.get("selection_status") == "RACECARD_MISMATCH"),
            "pick_non_runner": sum(1 for x in blocked if x.get("selection_status") == "NON_RUNNER"),
            "pick_not_in_field": sum(1 for x in blocked if x.get("selection_status") == "NOT_IN_FIELD"),
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


# --- PVC-DASH-01: Prime beside the Rich Context challenger -------------------------------------------
_RESULTS = ("W", "P", "L")


def _price(value: Any) -> float | None:
    """A returned decimal price counts only when it is a real price (> 1.0)."""
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if number > 1.0 else None


def _record(rows: list[dict[str, Any]], result_key: str, sp_key: str) -> dict[str, Any]:
    """Won / placed and flat one-unit return at the price each horse returned, settled races only."""
    settled = [r for r in rows if r.get(result_key) in _RESULTS]
    units = 0.0
    priced = 0
    for r in settled:
        sp = _price(r.get(sp_key))
        if sp is None:
            continue
        priced += 1
        units += (sp - 1.0) if r[result_key] == "W" else -1.0
    return {
        "settled": len(settled),
        "won": sum(1 for r in settled if r[result_key] == "W"),
        "placed": sum(1 for r in settled if r[result_key] in ("W", "P")),
        "units": round(units, 2),
        "priced": priced,
    }


def prime_vs_challenger(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Race-by-race and summary view of Prime's pick against the Rich Context challenger's pick.

    Read-only presentation of shadow data. The challenger picks nothing Prime reads. Results are counted only
    for races with a recorded winner, and returns only for horses with a real returned price.
    """
    n = len(rows)
    agree = sum(1 for r in rows if r.get("agree"))
    differ = [r for r in rows if not r.get("agree")]
    differ_settled = [r for r in differ if r.get("prime_result") in _RESULTS and r.get("challenger_result") in _RESULTS]
    settled = sum(1 for r in rows if r.get("settled"))
    races = [
        {
            "race_id": r.get("race_id"),
            "course": r.get("course"),
            "off_time": r.get("off_time"),
            "off_minutes": r.get("off_minutes"),
            "agree": bool(r.get("agree")),
            "settled": bool(r.get("settled")),
            "prime": {
                "horse": r.get("prime_horse"),
                "prob": r.get("prime_prob"),
                "price": r.get("prime_price"),
                "result": r.get("prime_result"),
            },
            "challenger": {
                "horse": r.get("challenger_horse"),
                "prob": r.get("challenger_prob"),
                "price": r.get("challenger_price"),
                "result": r.get("challenger_result"),
            },
            "favourite": {
                "horse": r.get("favourite_horse"),
                "price": r.get("favourite_price"),
                "tied": bool(r.get("favourite_tied")),
                "result": r.get("favourite_result"),
            },
        }
        for r in rows
    ]
    note = None
    if settled < 100:
        note = (
            "Small sample: treat this as a lead, not an edge. A challenger that mostly picks the favourite "
            "will track the market, which is a different thing from adding information to Prime."
        )
    return {
        "races": n,
        "agree": agree,
        "disagree": n - agree,
        "agree_pct": round(100.0 * agree / n, 1) if n else None,
        "challenger_is_favourite": sum(
            1 for r in rows if r.get("favourite_horse") and r.get("challenger_horse") == r.get("favourite_horse")
        ),
        "prime_is_favourite": sum(
            1 for r in rows if r.get("favourite_horse") and r.get("prime_horse") == r.get("favourite_horse")
        ),
        "settled": settled,
        "prime": _record(rows, "prime_result", "prime_sp"),
        "challenger": _record(rows, "challenger_result", "challenger_sp"),
        "favourite": _record(rows, "favourite_result", "favourite_sp"),
        "when_they_differ": {
            "settled": len(differ_settled),
            "prime_won": sum(1 for r in differ_settled if r["prime_result"] == "W"),
            "challenger_won": sum(1 for r in differ_settled if r["challenger_result"] == "W"),
        },
        "sample_note": note,
        "races_detail": races,
    }
