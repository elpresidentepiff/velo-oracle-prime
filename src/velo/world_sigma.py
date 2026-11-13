"""World Sigma: settle Velo's own frozen World picks against stored provider results.

PAPER/SHADOW only. Pure functions: no network, no clock. ``scripts/ops/run_world_sigma.py``
does the I/O. This is NOT ``formfav_global_eod`` - that grades FormFav's predictions. This grades
the scorecard Velo froze before the off (``world_model_scorecards``) against ``formfav_results``.

Rules taken from docs/current/WORLD_ONE_TRUTH.md:
* a provisional result is stored and visible but never learning-eligible;
* a failed gate blocks consumption, it never deletes evidence;
* a blocked row is never relabelled as eligible, and a final result is never downgraded.
"""
from __future__ import annotations

import hashlib
import re
from datetime import UTC, datetime
from typing import Any

from src.velo.race_identity import VERIFIED, verify_selection

SIGMA_VERSION = "WORLD_SIGMA_V1"
PRICE_PLACEHOLDER = 10.0
# The only blocks that may later clear: the result simply had not arrived or been confirmed.
TRANSIENT_BLOCKS = frozenset({"RESULT_NOT_FINAL", "NO_RESULT"})


def _key(*parts: object) -> str:
    return hashlib.sha256("|".join(str(p) for p in parts).encode()).hexdigest()


def _int(value: Any) -> int | None:
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _float(value: Any) -> float | None:
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def norm_name(value: Any) -> str:
    """Lower-case, drop a trailing country tag such as "(USA)", keep letters and digits only."""
    text = re.sub(r"\s*\([^)]*\)\s*$", "", str(value or "").lower())
    return re.sub(r"[^a-z0-9]+", "", text)


def price_state_of(row: dict[str, Any]) -> str:
    """REAL only when the freeze recorded a dated pre-off price. Legacy rows that stored the
    scorer's 10.0 default are MISSING; any other legacy price is UNVERIFIED (no capture time)."""
    state = (row.get("feature_payload") or {}).get("price_state")
    if state:
        return str(state)
    price = _float(row.get("captured_price"))
    if price is None or price == PRICE_PLACEHOLDER:
        return "MISSING"
    return "UNVERIFIED"


def _tie_size(rows: list[dict[str, Any]]) -> int:
    scores = [round(s, 6) for r in rows if (s := _float(r.get("score"))) is not None]
    return sum(1 for s in scores if s == max(scores)) if scores else 0


def settle_pick(
    score_rows: list[dict[str, Any]],
    result: dict[str, Any] | None,
    *,
    computed_at: datetime | None = None,
    identity: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    """Return one ``world_sigma_audits`` row for a race's frozen rank-1 pick, or None.

    ``identity`` is the race's ``verify_race_identity`` verdict. When the race cannot be proved
    to be one race, or the frozen pick is not in its verified field, the row is quarantined as
    ``identity_blocked`` with ``RACECARD_MISMATCH`` first among its block reasons (#189).
    """
    rows = sorted(score_rows, key=lambda r: _int(r.get("runner_rank")) or 10**6)
    if not rows:
        return None
    top = rows[0]
    computed_at = computed_at or datetime.now(UTC)

    placings = [
        p for p in ((result or {}).get("results_payload") or {}).get("placings") or []
        if isinstance(p, dict)
    ]
    live = [p for p in placings if not p.get("scratched")]
    winners = [p for p in live if _int(p.get("position")) == 1]

    if not result or not winners:
        basis = "no_result"
    elif result.get("interim") is False:
        basis = "final"
    else:
        basis = "provisional"

    wanted = norm_name(top.get("horse_name"))
    matches = [p for p in placings if norm_name(p.get("name")) == wanted]
    if basis != "no_result" and len(matches) != 1:
        basis = "identity_blocked"
    pick_check = (
        verify_selection(identity, top.get("horse_name")) if identity is not None else None
    )
    race_quarantined = bool(
        identity is not None
        and (identity.get("status") != VERIFIED or pick_check["status"] in ("NOT_IN_FIELD", "RACECARD_MISMATCH"))
    )
    if race_quarantined:
        basis = "identity_blocked"
        matches = []
    placing = matches[0] if len(matches) == 1 else None

    settled = basis in ("final", "provisional") and placing is not None
    scratched = bool(settled and placing.get("scratched"))
    position = _int(placing.get("position")) if settled and not scratched else None
    win = (position == 1) if settled and not scratched else None
    frame = (position is not None and 1 <= position <= 3) if settled and not scratched else None

    state = price_state_of(top)
    price = _float(top.get("captured_price"))
    profit: float | None = None
    if settled:
        if scratched:
            profit = 0.0  # stake void
        elif state == "REAL" and price is not None and price > 1.0:
            profit = round(price / len(winners) - 1.0 if win else -1.0, 4)

    tie = _tie_size(rows)
    reasons: list[str] = []
    if race_quarantined:
        reasons.append("RACECARD_MISMATCH")
        reasons += [f"RACE_IDENTITY_{r}" for r in identity.get("reasons") or []]
        if pick_check["status"] != "RACECARD_MISMATCH":
            reasons.append("TOP_PICK_NOT_IN_VERIFIED_FIELD")
    elif basis == "no_result":
        reasons.append("NO_RESULT")
    elif basis == "provisional":
        reasons.append("RESULT_NOT_FINAL")
    elif basis == "identity_blocked":
        reasons.append("TOP_PICK_NAME_AMBIGUOUS" if matches else "TOP_PICK_NOT_IN_RESULT")
    if scratched:
        reasons.append("TOP_PICK_SCRATCHED")
    if str(top.get("identity_grade") or "").upper().startswith("D"):
        reasons.append("IDENTITY_GRADE_D_NAME_COUNTRY_ONLY")
    if state != "REAL":
        reasons.append("PRICE_BLIND")
    if tie > 1:
        reasons.append("TIED_TOP_PICK")
    if not top.get("generated_pre_off"):
        reasons.append("NOT_PRE_OFF")
    if top.get("provider_predictions_consumed"):
        reasons.append("PROVIDER_OPINION_CONSUMED")

    return {
        "sigma_key": _key(SIGMA_VERSION, top.get("provider_race_key"), top.get("model_name")),
        "provider_race_key": top.get("provider_race_key"),
        "race_date": top.get("race_date"),
        "country": top.get("country"),
        "model_name": top.get("model_name"),
        "basis": basis,
        "top1_horse_key": top.get("horse_key"),
        "top1_horse_name": top.get("horse_name"),
        "top1_rank": _int(top.get("runner_rank")),
        "top1_finish_position": position,
        "top1_win": win,
        "top1_frame": frame,
        "winner_names": [p.get("name") for p in winners] or None,
        "captured_price": price if state == "REAL" else None,
        "level_stake_profit": profit,
        "identity_grade": top.get("identity_grade"),
        "learning_eligible": not reasons,
        "learning_block_reason": reasons[0] if reasons else None,
        "computed_at": computed_at.isoformat(),
        "details": {
            "sigma_version": SIGMA_VERSION,
            "block_reasons": reasons,
            "price_state": state,
            "top_tie_size": tie,
            # The sample a strike-rate claim may use: a confirmed result, a real choice.
            "skill_sample": basis == "final" and win is not None and tie == 1,
            "n_winners": len(winners),
            "dead_heat": len(winners) > 1,
            "result_stage": (result or {}).get("result_stage"),
            "interim": (result or {}).get("interim"),
            "placings": len(placings),
            "field_size": len(rows),
            "race_identity": None if identity is None else {
                "status": identity.get("status"),
                "reasons": identity.get("reasons"),
                "local_race_date": identity.get("local_race_date"),
                "start_time_utc": identity.get("start_time_utc"),
                "pick_status": pick_check["status"] if pick_check else None,
                "quarantined": race_quarantined,
            },
        },
    }


def build_event(audit: dict[str, Any]) -> dict[str, Any]:
    """One retained learning event per distinct outcome. A changed final result (a stewards'
    inquiry) gets a new event key; the old event stays."""
    basis = audit["basis"]
    reasons = (audit.get("details") or {}).get("block_reasons") or []
    if basis == "no_result":
        event_class = "NO_RESULT"
    elif basis == "identity_blocked":
        event_class = "IDENTITY_UNMATCHED"
    elif "TOP_PICK_SCRATCHED" in reasons:
        event_class = "TOP_PICK_SCRATCHED"
    elif audit.get("top1_win"):
        event_class = "TOP_PICK_WIN"
    elif audit.get("top1_frame"):
        event_class = "TOP_PICK_FRAME"
    else:
        event_class = "TOP_PICK_MISS"
    return {
        "event_key": _key(
            "WORLD_LEARNING_EVENT_V1", audit["sigma_key"], basis, event_class,
            audit.get("top1_finish_position"), "|".join(audit.get("winner_names") or []),
        ),
        "sigma_key": audit["sigma_key"],
        "provider_race_key": audit["provider_race_key"],
        "race_date": audit["race_date"],
        "country": audit["country"],
        "model_name": audit["model_name"],
        "event_class": event_class,
        "retained": True,
        "learning_eligible": bool(audit["learning_eligible"]),
        "learning_block_reason": audit.get("learning_block_reason"),
        "consumed": False,
        "evidence": {
            "basis": basis,
            "top1": audit.get("top1_horse_name"),
            "finish_position": audit.get("top1_finish_position"),
            "winners": audit.get("winner_names"),
            "price": audit.get("captured_price"),
            "profit": audit.get("level_stake_profit"),
            "block_reasons": reasons,
        },
    }


def merge_audit(new: dict[str, Any], existing: dict[str, Any] | None) -> dict[str, Any]:
    """Apply the no-downgrade and no-relabel laws when a sigma row is recomputed."""
    if not existing:
        return new
    # A race-identity quarantine is not a result downgrade: the "final" result belonged to a race
    # that cannot be proved to be the one the pick was made for, so it must stop counting.
    if ((new.get("details") or {}).get("race_identity") or {}).get("quarantined"):
        return new
    if existing.get("basis") == "final" and new.get("basis") != "final":
        return existing
    out = dict(new)
    if out.get("learning_eligible") and not existing.get("learning_eligible"):
        if existing.get("learning_block_reason") not in TRANSIENT_BLOCKS:
            out["learning_eligible"] = False
            out["learning_block_reason"] = existing.get("learning_block_reason") or "NEVER_RELABEL_BLOCKED_ROW"
    return out
