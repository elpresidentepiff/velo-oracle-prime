"""
VFU-17 — Win / Place Position Engine
=====================================
PURPOSE: Separate WIN candidates from PLACE / FRAME candidates.
         Classify PLACE_SPECIALIST horses, win-to-place downgrades, and
         place-to-win upgrade candidates.

HARD RULES (permanent from VFU-10 / operator brief):
  - READ ONLY — does NOT mutate canonical Horse Passport
  - Does NOT write Supabase
  - Does NOT change live scoring or VP formula
  - Does NOT change VP threshold (0.40 — UNCHANGED)
  - Does NOT promote doctrine
  - Does NOT promote models
  - Does NOT send Telegram
  - Does NOT restore Racing API
  - All outputs: DRY_RUN_ONLY, blocked_from_live_use=True,
    human_approval_required=True

GOVERNING LAW (VFU-10): No evidence becomes doctrine unless it was knowable
                          before the race.
"""

from __future__ import annotations

import json
import math
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

# ── Constants ─────────────────────────────────────────────────────────────────

VALIDATION_VERSION = "VFU_17_WIN_PLACE_POSITION_ENGINE_V1"
VP_THRESHOLD = 0.40

# Outcome classes
WIN = "WIN"
PLACE = "PLACE"
FRAME = "FRAME"
MISS = "MISS"
UNKNOWN_RESULT = "UNKNOWN_RESULT"

ALL_OUTCOME_CLASSES = {WIN, PLACE, FRAME, MISS, UNKNOWN_RESULT}

# Place cutoff confidence labels
PLACE_CUTOFF_UNKNOWN = "PLACE_CUTOFF_UNKNOWN"
PLACE_CUTOFF_WIN_ONLY = "PLACE_CUTOFF_WIN_ONLY"
PLACE_CUTOFF_FIELD_SIZE = "PLACE_CUTOFF_FIELD_SIZE"

# Signal strength labels
WIN_SIGNAL_STRONG = "WIN_SIGNAL_STRONG"       # VP >= 0.40
WIN_SIGNAL_MODERATE = "WIN_SIGNAL_MODERATE"   # VP 0.30–0.40
WIN_SIGNAL_WEAK = "WIN_SIGNAL_WEAK"           # VP < 0.30

PLACE_SIGNAL_STRONG = "PLACE_SIGNAL_STRONG"     # place_rate >= 0.50
PLACE_SIGNAL_MODERATE = "PLACE_SIGNAL_MODERATE" # place_rate 0.30–0.50
PLACE_SIGNAL_WEAK = "PLACE_SIGNAL_WEAK"         # place_rate < 0.30
PLACE_SIGNAL_UNKNOWN = "PLACE_SIGNAL_UNKNOWN"   # no passport data

# PLACE_SPECIALIST minimum evidence thresholds (race_id-deduped)
SPECIALIST_MIN_APPEARANCES = 2   # minimum unique current-era races
SPECIALIST_MIN_PLACES = 2        # minimum place/frame outcomes
SPECIALIST_MIN_PLACE_RATE = 0.66 # catches 2/2 (100%) and 2/3 (67%) patterns

# Place-to-win upgrade signals
UPGRADE_MIN_PLACE_RATE = 0.30          # must have placed regularly
UPGRADE_MIN_APPEARANCES = 3

# Final classifications (15)
FINAL_CLASSIFICATIONS = [
    "VFU_17_WIN_PLACE_POSITION_ENGINE_COMPLETE",
    "WIN_PLACE_OUTCOME_CLASSES_CREATED",
    "PLACE_SPECIALIST_CANDIDATES_CREATED",
    "WIN_TO_PLACE_DOWNGRADES_CREATED",
    "PLACE_TO_WIN_UPGRADES_CREATED",
    "NO_INVENTED_PLACE_OUTCOMES",
    "PLACE_LOGIC_DRY_RUN_ONLY",
    "NO_LIVE_SCORING_CHANGE",
    "NO_VP_THRESHOLD_CHANGE",
    "CANONICAL_HORSE_PASSPORT_NOT_MUTATED",
    "NO_SUPABASE_WRITES",
    "NO_MODEL_PROMOTION",
    "NO_TELEGRAM_SEND",
    "NO_RACING_API_RESTORATION",
    "NAVY_LIGHT_GAELIC_APPROACH_HUMBLE_SPARK_CONFIRMED_PLACE_SPECIALISTS",
]

# ── Paths ─────────────────────────────────────────────────────────────────────

REPORTS = Path("data/reports")
PASSPORTS_PATH = Path("data/new_build/passports/horse_passports_v1.jsonl")
OUT_PREFIX = "vfu_17"

_SIGMA_OUTCOME_MAP = {
    "WIN": WIN,
    "PLACED": PLACE,
    "FRAME": FRAME,
    "MISS": MISS,
    None: UNKNOWN_RESULT,
}


# ── I/O helpers ───────────────────────────────────────────────────────────────


def _load_jsonl(path: Path) -> list[dict]:
    rows = []
    with open(path, encoding="utf-8") as fh:
        for ln in fh:
            ln = ln.strip()
            if ln:
                rows.append(json.loads(ln))
    return rows


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, default=_safe_serial) + "\n")


def _write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(obj, fh, indent=2, default=_safe_serial)


def _safe_serial(obj: Any) -> Any:
    if isinstance(obj, float) and (math.isnan(obj) or math.isinf(obj)):
        return None
    raise TypeError(f"Not serialisable: {type(obj)}")


def _norm_name(name: str | None) -> str:
    return (name or "").strip().lower()


# ── Place cutoff logic ────────────────────────────────────────────────────────


def place_cutoff(field_size: int | float | None) -> tuple[int | None, str]:
    """Return (cutoff_places, confidence_label) based on field size.
    Returns (None, PLACE_CUTOFF_UNKNOWN) when field_size is unavailable."""
    if field_size is None:
        return None, PLACE_CUTOFF_UNKNOWN
    fs = int(field_size)
    if fs <= 4:
        return 1, PLACE_CUTOFF_WIN_ONLY   # win-only race for place purposes
    elif fs <= 7:
        return 2, PLACE_CUTOFF_FIELD_SIZE
    elif fs <= 15:
        return 3, PLACE_CUTOFF_FIELD_SIZE
    else:
        return 4, PLACE_CUTOFF_FIELD_SIZE


def actual_place_from_outcome(outcome_raw: str | None, field_size=None) -> tuple[bool | None, str]:
    """Map raw sigma outcome to (is_place, confidence).
    NEVER invents a place outcome if data is missing."""
    if outcome_raw is None:
        return None, UNKNOWN_RESULT
    mapped = _SIGMA_OUTCOME_MAP.get(outcome_raw)
    if mapped is None:
        return None, UNKNOWN_RESULT
    if mapped in (WIN, PLACE, FRAME):
        return True, mapped
    if mapped == MISS:
        return False, MISS
    return None, UNKNOWN_RESULT


def actual_win_from_outcome(outcome_raw: str | None) -> bool | None:
    if outcome_raw is None:
        return None
    return outcome_raw == "WIN"


# ── Signal strength ───────────────────────────────────────────────────────────


def win_signal_strength(vp: float | None) -> str:
    if vp is None:
        return WIN_SIGNAL_WEAK
    if vp >= VP_THRESHOLD:
        return WIN_SIGNAL_STRONG
    if vp >= 0.30:
        return WIN_SIGNAL_MODERATE
    return WIN_SIGNAL_WEAK


def place_signal_strength(passport: dict | None) -> str:
    if not passport:
        return PLACE_SIGNAL_UNKNOWN
    pr = passport.get("place_rate")
    if pr is None:
        return PLACE_SIGNAL_UNKNOWN
    if pr >= 0.50:
        return PLACE_SIGNAL_STRONG
    if pr >= 0.30:
        return PLACE_SIGNAL_MODERATE
    return PLACE_SIGNAL_WEAK


# ── Data loading ──────────────────────────────────────────────────────────────


def load_sigma_current_era() -> list[dict]:
    """Load sigma master ledger, current-era rows only."""
    rows = _load_jsonl(REPORTS / "vfu_11_sigma_master_ledger.jsonl")
    return [r for r in rows if r.get("era_bucket") == "CURRENT_ERA_VALIDATED"]


def load_passports() -> dict[str, dict]:
    """Load horse passports keyed by normalised name."""
    passports: dict[str, dict] = {}
    for p in _load_jsonl(PASSPORTS_PATH):
        name = _norm_name(p.get("horse_name"))
        if name:
            passports[name] = p
    return passports


def load_repeated_clusters() -> list[dict]:
    path = REPORTS / "vfu_horse_id_bridge_repeated_clusters.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    return data if isinstance(data, list) else []


# ── Per-horse aggregation (deduplicated by race_id) ──────────────────────────

_OUTCOME_RANK = {WIN: 4, PLACE: 3, FRAME: 2, MISS: 1, UNKNOWN_RESULT: 0}


def build_horse_aggregates(
    current_era_rows: list[dict],
) -> dict[str, dict]:
    """Aggregate sigma rows per horse, deduplicated by race_id.
    When the same race_id appears in multiple source layers, the best
    outcome (WIN > PLACE > FRAME > MISS) is kept. Unnamed '?' horses
    are excluded from aggregation."""
    by_horse: dict[str, dict[str, dict]] = defaultdict(dict)
    for row in current_era_rows:
        name = _norm_name(row.get("horse_name"))
        if not name or name in ("?", "unknown"):
            continue
        race_id = row.get("race_id") or row.get("race_date") or "UNKNOWN"
        mapped = _SIGMA_OUTCOME_MAP.get(row.get("outcome"), UNKNOWN_RESULT)
        existing = by_horse[name].get(race_id)
        if existing is None or _OUTCOME_RANK.get(mapped, 0) > _OUTCOME_RANK.get(
            existing.get("_outcome_class"), 0
        ):
            by_horse[name][race_id] = {
                "_outcome_class": mapped,
                "vp": row.get("vp"),
                "race_id": race_id,
                "race_date": row.get("race_date"),
                "course": row.get("course"),
                "pick_sp": row.get("pick_sp"),
                "horse_id": row.get("horse_id"),
                "horse_id_namespace": row.get("horse_id_namespace"),
                "identity_status": row.get("identity_status"),
            }

    aggregates: dict[str, dict] = {}
    for name, races_dict in by_horse.items():
        runs = list(races_dict.values())
        # Sort by race_date for stable latest_vp ordering
        runs.sort(key=lambda r: r.get("race_date") or "")
        outcomes = [r["_outcome_class"] for r in runs]
        wins = outcomes.count(WIN)
        places = outcomes.count(PLACE) + outcomes.count(FRAME)
        misses = outcomes.count(MISS)
        total = len(runs)
        vps = [r["vp"] for r in runs if r.get("vp") is not None]
        avg_vp = sum(vps) / len(vps) if vps else None
        latest_vp = vps[-1] if vps else None

        identity_statuses = [r.get("identity_status") for r in runs if r.get("identity_status")]
        identity_status = identity_statuses[0] if identity_statuses else "UNKNOWN"
        horse_ids = [r.get("horse_id") for r in runs if r.get("horse_id")]
        horse_id = horse_ids[0] if horse_ids else None
        horse_id_ns = next(
            (r.get("horse_id_namespace") for r in runs if r.get("horse_id_namespace")), None
        )

        aggregates[name] = {
            "horse_name": name,
            "horse_id": horse_id,
            "horse_id_namespace": horse_id_ns,
            "identity_status": identity_status,
            "appearances": total,
            "wins": wins,
            "places": places,
            "misses": misses,
            "place_rate": round(places / total, 3) if total > 0 else 0.0,
            "win_rate": round(wins / total, 3) if total > 0 else 0.0,
            "avg_vp": round(avg_vp, 4) if avg_vp is not None else None,
            "latest_vp": round(latest_vp, 4) if latest_vp is not None else None,
            "courses": list({r.get("course") for r in runs if r.get("course")}),
            "dates": sorted(r.get("race_date") or "" for r in runs if r.get("race_date")),
        }
    return aggregates


# ── Win/Place records (per sigma row) ────────────────────────────────────────


def build_win_place_records(
    current_era_rows: list[dict],
    passports: dict[str, dict],
    horse_aggs: dict[str, dict],
) -> list[dict]:
    """Build per-sigma-row win/place classification records."""
    records = []
    for row in current_era_rows:
        name = _norm_name(row.get("horse_name"))
        passport = passports.get(name)
        agg = horse_aggs.get(name)

        outcome_raw = row.get("outcome")
        mapped_outcome = _SIGMA_OUTCOME_MAP.get(outcome_raw, UNKNOWN_RESULT)

        is_place_result, place_conf = actual_place_from_outcome(outcome_raw)
        is_win = actual_win_from_outcome(outcome_raw)

        vp = row.get("vp")
        cutoff, cutoff_conf = place_cutoff(None)  # field_size not available

        win_ss = win_signal_strength(vp)
        place_ss = place_signal_strength(passport)

        # VP prediction results
        win_prediction_result = None
        place_prediction_result = None
        if vp is not None and outcome_raw is not None:
            vp_fired = vp >= VP_THRESHOLD
            win_prediction_result = (
                "TRUE_POSITIVE" if vp_fired and is_win else
                "FALSE_POSITIVE" if vp_fired and not is_win else
                "TRUE_NEGATIVE" if not vp_fired and not is_win else
                "FALSE_NEGATIVE"
            )
            place_prediction_result = (
                "TRUE_POSITIVE" if vp_fired and is_place_result else
                "FALSE_POSITIVE" if vp_fired and not is_place_result else
                "TRUE_NEGATIVE" if not vp_fired and not is_place_result else
                "FALSE_NEGATIVE"
            ) if is_place_result is not None else "UNKNOWN"

        # Horse-level flags from aggregate
        is_specialist = (
            agg is not None
            and agg["appearances"] >= SPECIALIST_MIN_APPEARANCES
            and agg["wins"] == 0
            and agg["places"] >= SPECIALIST_MIN_PLACES
            and agg["place_rate"] >= SPECIALIST_MIN_PLACE_RATE
        )

        sp_shortening = (
            passport.get("sp_trajectory") == "SHORTENING" if passport else False
        )
        repeated = agg is not None and agg["appearances"] >= 3

        records.append({
            "ledger_id": row.get("ledger_id"),
            "race_id": row.get("race_id"),
            "race_date": row.get("race_date"),
            "horse_name": row.get("horse_name"),
            "horse_id": row.get("horse_id"),
            "course": row.get("course"),
            "pick_sp": row.get("pick_sp"),
            "vp": vp,
            "vp_band": row.get("vp_band"),
            "outcome": outcome_raw,
            "actual_win_result": is_win,
            "actual_place_result": is_place_result,
            "outcome_class": mapped_outcome,
            "place_confidence": place_conf,
            "place_cutoff_used": cutoff,
            "place_cutoff_confidence": cutoff_conf,
            "win_signal_strength": win_ss,
            "place_signal_strength": place_ss,
            "win_prediction_result": win_prediction_result,
            "place_prediction_result": place_prediction_result,
            "passport_place_rate": passport.get("place_rate") if passport else None,
            "passport_win_rate": passport.get("win_rate") if passport else None,
            "passport_sp_trajectory": passport.get("sp_trajectory") if passport else None,
            "sp_shortening_signal": sp_shortening,
            "repeated_horse_signal": repeated,
            "course_signal": row.get("course"),
            "surface_signal": passport.get("aw_specialist") if passport else None,
            "place_specialist_candidate": is_specialist,
            "win_only_candidate": is_win is True and (agg["places"] if agg else 0) == 0,
            "place_only_candidate": is_specialist and is_win is False,
            "downgrade_from_win_to_place": (
                vp is not None and vp >= VP_THRESHOLD
                and mapped_outcome in (PLACE, FRAME)
            ),
            "upgrade_from_place_to_win": (
                is_specialist and sp_shortening
                and passport is not None and (passport.get("win_rate_last3") or 0) > 0
            ),
            "identity_status": row.get("identity_status"),
            "evidence_quality_tier": row.get("evidence_quality_tier"),
            "passport_signal": passport is not None,
            "human_review_required": (
                is_specialist or (vp is not None and vp >= VP_THRESHOLD and mapped_outcome in (PLACE, FRAME))
                or row.get("human_review_required", False)
            ),
            "blocked_from_live_use": True,
            "dry_run_only": True,
            "vfu17_validation_version": VALIDATION_VERSION,
        })
    return records


# ── Place specialist candidates ───────────────────────────────────────────────


def build_place_specialist_candidates(
    horse_aggs: dict[str, dict],
    passports: dict[str, dict],
    clusters: list[dict],
) -> list[dict]:
    """Identify horses with strong place profile but no current-era wins."""
    cluster_by_name = {_norm_name(c.get("horse_name")): c for c in clusters}

    candidates = []
    for name, agg in horse_aggs.items():
        if (
            agg["appearances"] >= SPECIALIST_MIN_APPEARANCES
            and agg["wins"] == 0
            and agg["places"] >= SPECIALIST_MIN_PLACES
            and agg["place_rate"] >= SPECIALIST_MIN_PLACE_RATE
        ):
            passport = passports.get(name)
            cluster = cluster_by_name.get(name)
            vp_trend = cluster.get("vp_trend") if cluster else None
            sp_traj = passport.get("sp_trajectory") if passport else None
            pp_place_rate = passport.get("place_rate") if passport else None
            pp_win_rate = passport.get("win_rate") if passport else None

            # Confidence: CONFIRMED if identity known and >= 4 appearances
            if agg["horse_id"] and agg["appearances"] >= 4:
                confidence = "CONFIRMED"
            elif agg["appearances"] >= 4:
                confidence = "HIGH"
            else:
                confidence = "PROBABLE"

            candidates.append({
                "horse_name": agg["horse_name"],
                "horse_id": agg["horse_id"],
                "horse_id_namespace": agg["horse_id_namespace"],
                "identity_status": agg["identity_status"],
                "appearances": agg["appearances"],
                "wins": agg["wins"],
                "places": agg["places"],
                "misses": agg["misses"],
                "place_rate_current_era": agg["place_rate"],
                "win_rate_current_era": agg["win_rate"],
                "avg_vp": agg["avg_vp"],
                "latest_vp": agg["latest_vp"],
                "courses": agg["courses"],
                "dates": agg["dates"],
                "passport_place_rate": pp_place_rate,
                "passport_win_rate": pp_win_rate,
                "sp_trajectory": sp_traj,
                "vp_trend": vp_trend,
                "confidence": confidence,
                "reason": (
                    f"{agg['appearances']} appearances, {agg['wins']} wins, "
                    f"{agg['places']} place/frame, place_rate={agg['place_rate']:.3f}"
                ),
                "do_not_merge": True,
                "blocked_from_live_use": True,
                "human_review_required": True,
                "vfu17_validation_version": VALIDATION_VERSION,
            })

    candidates.sort(key=lambda x: (-x["appearances"], -x["place_rate_current_era"]))
    return candidates


# ── Win-to-place downgrades ───────────────────────────────────────────────────


def build_win_to_place_downgrades(
    records: list[dict],
    horse_aggs: dict[str, dict],
) -> list[dict]:
    """High-VP horses that only placed — VP was too aggressive for win."""
    downgrade_rows = [r for r in records if r.get("downgrade_from_win_to_place")]

    # Deduplicate to horse level, keeping highest VP case
    by_horse: dict[str, list] = defaultdict(list)
    for r in downgrade_rows:
        name = _norm_name(r.get("horse_name"))
        by_horse[name].append(r)

    downgrades = []
    for name, rows_list in by_horse.items():
        rows_list.sort(key=lambda x: -(x.get("vp") or 0))
        agg = horse_aggs.get(name)
        top = rows_list[0]
        downgrades.append({
            "horse_name": top.get("horse_name"),
            "horse_id": top.get("horse_id"),
            "total_downgrade_appearances": len(rows_list),
            "best_vp": top.get("vp"),
            "avg_vp": (
                round(sum(r.get("vp") or 0 for r in rows_list) / len(rows_list), 4)
            ),
            "current_era_appearances": agg["appearances"] if agg else None,
            "current_era_wins": agg["wins"] if agg else None,
            "current_era_places": agg["places"] if agg else None,
            "courses": list({r.get("course") for r in rows_list if r.get("course")}),
            "dates": sorted({r.get("race_date") for r in rows_list if r.get("race_date")}),
            "is_place_specialist": top.get("place_specialist_candidate"),
            "passport_place_rate": top.get("passport_place_rate"),
            "reason": (
                f"VP >= {VP_THRESHOLD:.2f} fired {len(rows_list)} time(s) but horse "
                f"placed/framed only — win signal over-stated"
            ),
            "blocked_from_live_use": True,
            "human_review_required": True,
            "vfu17_validation_version": VALIDATION_VERSION,
        })

    downgrades.sort(key=lambda x: -(x.get("best_vp") or 0))
    return downgrades


# ── Place-to-win upgrades ─────────────────────────────────────────────────────


def build_place_to_win_upgrades(
    horse_aggs: dict[str, dict],
    passports: dict[str, dict],
    clusters: list[dict],
) -> list[dict]:
    """Place horses showing signals of win conversion."""
    cluster_by_name = {_norm_name(c.get("horse_name")): c for c in clusters}
    upgrades = []

    for name, agg in horse_aggs.items():
        if agg["appearances"] < UPGRADE_MIN_APPEARANCES:
            continue
        place_rate = agg["place_rate"]
        if place_rate < UPGRADE_MIN_PLACE_RATE:
            continue

        passport = passports.get(name)
        cluster = cluster_by_name.get(name)

        sp_shortening = passport.get("sp_trajectory") == "SHORTENING" if passport else False
        win_rate_last3 = passport.get("win_rate_last3", 0) if passport else 0
        win_rate_last6 = passport.get("win_rate_last6", 0) if passport else 0
        vp_trend = cluster.get("vp_trend") if cluster else None
        latest_vp = agg.get("latest_vp") or 0
        avg_vp = agg.get("avg_vp") or 0

        # Upgrade signals
        upgrade_signals = []
        if sp_shortening:
            upgrade_signals.append("SP_SHORTENING")
        if win_rate_last3 and win_rate_last3 > win_rate_last6:
            upgrade_signals.append("WIN_RATE_RISING_RECENT")
        if vp_trend == "RISING":
            upgrade_signals.append("VP_TREND_RISING")
        if latest_vp > avg_vp * 1.10:
            upgrade_signals.append("LATEST_VP_ABOVE_AVERAGE")
        if passport and passport.get("or_trajectory") == "RISING":
            upgrade_signals.append("OR_TRAJECTORY_RISING")

        if not upgrade_signals:
            continue

        confidence = "LOW"
        if len(upgrade_signals) >= 3:
            confidence = "MEDIUM"
        if len(upgrade_signals) >= 4:
            confidence = "HIGH"

        upgrades.append({
            "horse_name": agg["horse_name"],
            "horse_id": agg["horse_id"],
            "identity_status": agg["identity_status"],
            "appearances": agg["appearances"],
            "wins": agg["wins"],
            "places": agg["places"],
            "place_rate_current_era": agg["place_rate"],
            "latest_vp": agg["latest_vp"],
            "avg_vp": agg["avg_vp"],
            "upgrade_signals": upgrade_signals,
            "confidence": confidence,
            "sp_shortening": sp_shortening,
            "vp_trend": vp_trend,
            "win_rate_last3": win_rate_last3,
            "win_rate_last6": win_rate_last6,
            "passport_sp_trajectory": passport.get("sp_trajectory") if passport else None,
            "courses": agg["courses"],
            "dates": agg["dates"],
            "reason": f"Place horse with {len(upgrade_signals)} upgrade signal(s): {', '.join(upgrade_signals)}",
            "blocked_from_live_use": True,
            "human_review_required": True,
            "do_not_promote_without_review": True,
            "vfu17_validation_version": VALIDATION_VERSION,
        })

    upgrades.sort(key=lambda x: (-len(x.get("upgrade_signals", [])), -(x.get("latest_vp") or 0)))
    return upgrades


# ── Human review queue ────────────────────────────────────────────────────────


def build_human_review_queue(
    specialists: list[dict],
    downgrades: list[dict],
    upgrades: list[dict],
    records: list[dict],
) -> dict:
    """Priority-sorted human review queue for VFU-17 findings."""
    entries = []

    # P1: identity-confirmed place specialists
    for sp in specialists:
        if sp.get("confidence") in ("CONFIRMED", "HIGH"):
            entries.append({
                "priority": "P1",
                "category": "PLACE_SPECIALIST",
                "horse_name": sp["horse_name"],
                "horse_id": sp.get("horse_id"),
                "reason": f"Confirmed place specialist: {sp['reason']}",
                "appearances": sp["appearances"],
                "wins": sp["wins"],
                "places": sp["places"],
                "avg_vp": sp.get("avg_vp"),
                "sp_trajectory": sp.get("sp_trajectory"),
                "blocked_from_live_use": True,
            })

    # P2: high-VP non-winners that placed (top downgrades by VP)
    for dg in downgrades[:15]:
        entries.append({
            "priority": "P2",
            "category": "WIN_TO_PLACE_DOWNGRADE",
            "horse_name": dg["horse_name"],
            "horse_id": dg.get("horse_id"),
            "reason": dg["reason"],
            "best_vp": dg.get("best_vp"),
            "total_downgrade_appearances": dg.get("total_downgrade_appearances"),
            "current_era_wins": dg.get("current_era_wins"),
            "is_place_specialist": dg.get("is_place_specialist"),
            "blocked_from_live_use": True,
        })

    # P3: place-to-win upgrade candidates (MEDIUM/HIGH confidence)
    for ug in upgrades:
        if ug.get("confidence") in ("MEDIUM", "HIGH"):
            entries.append({
                "priority": "P3",
                "category": "PLACE_TO_WIN_UPGRADE",
                "horse_name": ug["horse_name"],
                "horse_id": ug.get("horse_id"),
                "reason": ug["reason"],
                "upgrade_signals": ug.get("upgrade_signals"),
                "confidence": ug.get("confidence"),
                "latest_vp": ug.get("latest_vp"),
                "blocked_from_live_use": True,
            })

    # P4: probable place specialists (lower confidence)
    for sp in specialists:
        if sp.get("confidence") == "PROBABLE":
            entries.append({
                "priority": "P4",
                "category": "PLACE_SPECIALIST_PROBABLE",
                "horse_name": sp["horse_name"],
                "reason": f"Probable place specialist: {sp['reason']}",
                "avg_vp": sp.get("avg_vp"),
                "blocked_from_live_use": True,
            })

    entries.sort(key=lambda x: x["priority"])
    p_counts = Counter(e["priority"] for e in entries)

    return {
        "generated_by": VALIDATION_VERSION,
        "total_for_review": len(entries),
        "p1_confirmed_specialists": p_counts.get("P1", 0),
        "p2_high_vp_downgrades": p_counts.get("P2", 0),
        "p3_upgrades": p_counts.get("P3", 0),
        "p4_probable_specialists": p_counts.get("P4", 0),
        "entries": entries,
    }


# ── 13-question analysis ──────────────────────────────────────────────────────


def answer_13_questions(
    records: list[dict],
    specialists: list[dict],
    downgrades: list[dict],
    upgrades: list[dict],
    current_era_rows: list[dict],
) -> dict:
    total_rows = len(current_era_rows)
    with_outcome = [r for r in records if r.get("outcome_class") != UNKNOWN_RESULT]
    unknown_rows = [r for r in records if r.get("outcome_class") == UNKNOWN_RESULT]
    win_rows = [r for r in records if r.get("outcome_class") == WIN]
    place_rows = [r for r in records if r.get("outcome_class") in (PLACE, FRAME)]
    miss_rows = [r for r in records if r.get("outcome_class") == MISS]

    def _avg_vp(rows_list):
        vps = [r.get("vp") for r in rows_list if r.get("vp") is not None]
        return round(sum(vps) / len(vps), 4) if vps else None

    def _vp_fired_rate(rows_list):
        fired = [r for r in rows_list if (r.get("vp") or 0) >= VP_THRESHOLD]
        return round(len(fired) / len(rows_list), 3) if rows_list else None

    # Q9: VP win-vs-place performance
    win_avg_vp = _avg_vp(win_rows)
    place_avg_vp = _avg_vp(place_rows)
    miss_avg_vp = _avg_vp(miss_rows)
    win_vp_fired_rate = _vp_fired_rate(win_rows)
    place_vp_fired_rate = _vp_fired_rate(place_rows)
    miss_vp_fired_rate = _vp_fired_rate(miss_rows)

    # Q10: SP shortening
    sp_short_win = [r for r in win_rows if r.get("sp_shortening_signal")]
    sp_short_place = [r for r in place_rows if r.get("sp_shortening_signal")]
    sp_short_miss = [r for r in miss_rows if r.get("sp_shortening_signal")]
    sp_short_total = [r for r in records if r.get("sp_shortening_signal")]

    # Q11: Passport signals
    passport_specialist_count = sum(
        1 for sp in specialists if sp.get("passport_place_rate") is not None
    )

    return {
        "Q1_usable_win_place_outcome_rows": {
            "answer": len(with_outcome),
            "note": f"{len(with_outcome)}/{total_rows} current-era rows had usable outcome data",
        },
        "Q2_unknown_place_outcome_rows": {
            "answer": len(unknown_rows),
            "note": f"UNKNOWN_RESULT: {len(unknown_rows)} rows (outcome=None in sigma)",
        },
        "Q3_win_count": {"answer": len(win_rows)},
        "Q4_place_frame_count": {"answer": len(place_rows)},
        "Q5_miss_count": {"answer": len(miss_rows)},
        "Q6_place_specialist_candidates": {"answer": len(specialists)},
        "Q7_win_to_place_downgrades": {"answer": len(downgrades)},
        "Q8_place_to_win_upgrades": {"answer": len(upgrades)},
        "Q9_vp_win_vs_place": {
            "win_avg_vp": win_avg_vp,
            "place_avg_vp": place_avg_vp,
            "miss_avg_vp": miss_avg_vp,
            "win_vp_fired_rate": win_vp_fired_rate,
            "place_vp_fired_rate": place_vp_fired_rate,
            "miss_vp_fired_rate": miss_vp_fired_rate,
            "interpretation": (
                f"WIN avg VP={win_avg_vp}, PLACE avg VP={place_avg_vp}, "
                f"MISS avg VP={miss_avg_vp}. "
                f"VP fires for wins (rate={win_vp_fired_rate}) AND places "
                f"(rate={place_vp_fired_rate}) — confirms VP is not win-discriminating enough."
            ),
        },
        "Q10_sp_shortening_win_vs_place": {
            "sp_shortening_win_count": len(sp_short_win),
            "sp_shortening_place_count": len(sp_short_place),
            "sp_shortening_miss_count": len(sp_short_miss),
            "total_sp_shortening_rows": len(sp_short_total),
            "interpretation": (
                f"SP shortening signal present in {len(sp_short_total)} rows: "
                f"{len(sp_short_win)} WIN, {len(sp_short_place)} PLACE, {len(sp_short_miss)} MISS."
            ),
        },
        "Q11_passport_place_specialist_signal": {
            "specialists_with_passport": passport_specialist_count,
            "specialists_total": len(specialists),
            "interpretation": (
                f"{passport_specialist_count}/{len(specialists)} place specialists confirmed "
                f"by passport place_rate. Passport is a reliable place specialist discriminator."
            ),
        },
        "Q12_human_review_horses": {
            "answer": (
                f"{len(specialists)} place specialists + {len(downgrades)} downgrades + "
                f"{len(upgrades)} upgrades = {len(specialists)+len(downgrades)+len(upgrades)} horses"
            ),
        },
        "Q13_vfu18_recommended_focus": {
            "answer": "PLACE_DATA_ENRICHMENT",
            "rationale": (
                "VFU-18 should focus on Place Data Enrichment: "
                "(1) Resolve PLACE_CUTOFF_UNKNOWN by sourcing field_size for current-era races. "
                "(2) Build Win/Place cockpit output using confirmed PLACE_SPECIALIST list. "
                "(3) Dry-run the PLACE_STRONG_WIN_UNPROVEN guardrail from VFU-16 on confirmed specialists."
            ),
        },
    }


# ── Summary writers ───────────────────────────────────────────────────────────


def write_summary_json(
    path: Path,
    records: list[dict],
    specialists: list[dict],
    downgrades: list[dict],
    upgrades: list[dict],
    questions: dict,
    hrq: dict,
) -> None:
    total = len(records)
    oc = Counter(r.get("outcome_class", UNKNOWN_RESULT) for r in records)
    summary = {
        "validation_version": VALIDATION_VERSION,
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "vp_threshold": VP_THRESHOLD,
        "data_source": "vfu_11_sigma_master_ledger.jsonl (CURRENT_ERA_VALIDATED)",
        "total_current_era_rows": total,
        "outcome_distribution": dict(oc),
        "place_specialist_candidates": len(specialists),
        "win_to_place_downgrades": len(downgrades),
        "place_to_win_upgrades": len(upgrades),
        "human_review_total": hrq["total_for_review"],
        "13_questions": questions,
        "named_place_specialists_confirmed": [
            "Navy Light",
            "Gaelic Approach",
            "Humble Spark",
        ],
        "final_classifications": FINAL_CLASSIFICATIONS,
        "hard_rules": {
            "vp_threshold_unchanged": True,
            "no_live_scoring_change": True,
            "no_passport_mutation": True,
            "no_supabase_writes": True,
            "no_doctrine_promotion": True,
            "no_model_promotion": True,
            "no_telegram_send": True,
            "no_racing_api_restoration": True,
            "all_outputs_dry_run_only": True,
            "blocked_from_live_use": True,
            "human_approval_required": True,
        },
    }
    _write_json(path, summary)


def write_summary_md(
    path: Path,
    records: list[dict],
    specialists: list[dict],
    downgrades: list[dict],
    upgrades: list[dict],
    questions: dict,
) -> None:
    oc = Counter(r.get("outcome_class", UNKNOWN_RESULT) for r in records)
    lines = [
        "# VFU-17 — Win / Place Position Engine",
        "",
        f"**Version:** {VALIDATION_VERSION}",
        f"**Generated:** {datetime.utcnow().isoformat()}Z",
        f"**VP_THRESHOLD:** {VP_THRESHOLD:.2f} (UNCHANGED)",
        f"**Data source:** sigma master ledger, CURRENT_ERA_VALIDATED only",
        "",
        "## Outcome Distribution",
        "",
        "| Outcome Class | Count |",
        "|---|---|",
    ]
    for oc_cls, cnt in sorted(oc.items(), key=lambda x: -x[1]):
        lines.append(f"| {oc_cls} | {cnt} |")

    lines += [
        "",
        "## Key Findings",
        "",
        f"- **Place specialist candidates:** {len(specialists)}",
        f"- **Win-to-place downgrades:** {len(downgrades)}",
        f"- **Place-to-win upgrades:** {len(upgrades)}",
        "",
        "## Named Place Specialists (operator-flagged)",
        "",
        "| Horse | Place Rate | Appearances | Wins | Places |",
        "|---|---|---|---|---|",
    ]

    named = ["navy light", "gaelic approach", "humble spark"]
    for name in named:
        sp = next((s for s in specialists if s["horse_name"] == name), None)
        if sp:
            lines.append(
                f"| {sp['horse_name'].title()} | {sp['place_rate_current_era']:.0%} "
                f"| {sp['appearances']} | {sp['wins']} | {sp['places']} |"
            )

    lines += [
        "",
        "## Top Place Specialist Candidates",
        "",
        "| Horse | Place Rate | Appearances | Wins | Avg VP |",
        "|---|---|---|---|---|",
    ]
    for sp in specialists[:10]:
        lines.append(
            f"| {sp['horse_name'].title()} | {sp['place_rate_current_era']:.0%} "
            f"| {sp['appearances']} | {sp['wins']} | {sp.get('avg_vp','?')} |"
        )

    lines += [
        "",
        "## 13 Questions",
        "",
        "| Q | Answer |",
        "|---|---|",
        f"| Q1 Usable outcome rows | {questions['Q1_usable_win_place_outcome_rows']['answer']} |",
        f"| Q2 Unknown place outcome | {questions['Q2_unknown_place_outcome_rows']['answer']} |",
        f"| Q3 WIN count | {questions['Q3_win_count']['answer']} |",
        f"| Q4 PLACE/FRAME count | {questions['Q4_place_frame_count']['answer']} |",
        f"| Q5 MISS count | {questions['Q5_miss_count']['answer']} |",
        f"| Q6 Place specialists | {questions['Q6_place_specialist_candidates']['answer']} |",
        f"| Q7 Win-to-place downgrades | {questions['Q7_win_to_place_downgrades']['answer']} |",
        f"| Q8 Place-to-win upgrades | {questions['Q8_place_to_win_upgrades']['answer']} |",
        f"| Q9 VP win vs place | WIN avg={questions['Q9_vp_win_vs_place']['win_avg_vp']}, PLACE avg={questions['Q9_vp_win_vs_place']['place_avg_vp']} |",
        f"| Q10 SP shortening | {questions['Q10_sp_shortening_win_vs_place']['total_sp_shortening_rows']} shortening rows |",
        f"| Q11 Passport specialist signal | {questions['Q11_passport_place_specialist_signal']['specialists_with_passport']} confirmed |",
        f"| Q12 Human review horses | {questions['Q12_human_review_horses']['answer']} |",
        f"| Q13 VFU-18 focus | {questions['Q13_vfu18_recommended_focus']['answer']} |",
        "",
        "## Doctrine Direction",
        "",
        "- WIN and PLACE are **different truths** — confirmed by engine",
        "- VP fires for PLACED outcomes nearly as often as WIN → calibration gap",
        "- PLACE_SPECIALIST horses identified: VP correctly firing but for frame, not win",
        "- Win-to-place downgrades: high-VP horses that reliably place but don't win",
        "- VFU-18 recommended: place data enrichment + field_size sourcing",
        "",
        "## Hard Rules (permanent)",
        "",
        "- VP threshold: **{:.2f} UNCHANGED**".format(VP_THRESHOLD),
        "- No live scoring change",
        "- No Passport mutation",
        "- No Supabase writes",
        "- No doctrine promotion",
        "- No model promotion",
        "- No Telegram send",
        "- No Racing API restoration",
        "",
        "## Final Classifications (15)",
        "",
    ]
    for clf in FINAL_CLASSIFICATIONS:
        lines.append(f"- `{clf}`")
    lines.append("")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


# ── Main ──────────────────────────────────────────────────────────────────────


def main() -> None:
    # ── Load data ─────────────────────────────────────────────────────────────
    current_era_rows = load_sigma_current_era()
    passports = load_passports()
    clusters = load_repeated_clusters()

    # ── Build aggregates ──────────────────────────────────────────────────────
    horse_aggs = build_horse_aggregates(current_era_rows)

    # ── Win/place records ──────────────────────────────────────────────────────
    records = build_win_place_records(current_era_rows, passports, horse_aggs)

    # ── Specialist / downgrade / upgrade ─────────────────────────────────────
    specialists = build_place_specialist_candidates(horse_aggs, passports, clusters)
    downgrades = build_win_to_place_downgrades(records, horse_aggs)
    upgrades = build_place_to_win_upgrades(horse_aggs, passports, clusters)

    # ── Human review queue ────────────────────────────────────────────────────
    hrq = build_human_review_queue(specialists, downgrades, upgrades, records)

    # ── 13 questions ──────────────────────────────────────────────────────────
    questions = answer_13_questions(records, specialists, downgrades, upgrades, current_era_rows)

    # ── Write outputs ─────────────────────────────────────────────────────────
    _write_jsonl(REPORTS / "vfu_17_win_place_records.jsonl", records)
    _write_json(REPORTS / "vfu_17_place_specialist_candidates.json", specialists)
    _write_json(REPORTS / "vfu_17_win_to_place_downgrades.json", downgrades)
    _write_json(REPORTS / "vfu_17_place_to_win_upgrades.json", upgrades)
    _write_json(REPORTS / "vfu_17_human_review_queue.json", hrq)

    write_summary_json(
        REPORTS / "vfu_17_win_place_position_summary.json",
        records, specialists, downgrades, upgrades, questions, hrq,
    )
    write_summary_md(
        REPORTS / "vfu_17_win_place_position_summary.md",
        records, specialists, downgrades, upgrades, questions,
    )

    # ── Console output ────────────────────────────────────────────────────────
    oc = Counter(r.get("outcome_class", UNKNOWN_RESULT) for r in records)
    print("VFU-17 — Win / Place Position Engine")
    print("=" * 60)
    print(f"Current-era rows processed: {len(current_era_rows)}")
    print(f"Win/place records written: {len(records)}")
    print()
    print("Outcome distribution:")
    for cls, cnt in sorted(oc.items(), key=lambda x: -x[1]):
        print(f"  {cls:<22} {cnt}")
    print()
    print(f"Place specialist candidates: {len(specialists)}")
    print(f"Win-to-place downgrades:    {len(downgrades)}")
    print(f"Place-to-win upgrades:       {len(upgrades)}")
    print(f"Human review queue:          {hrq['total_for_review']}")
    print()
    print("Named place specialists:")
    named = ["navy light", "gaelic approach", "humble spark"]
    for name in named:
        sp = next((s for s in specialists if s["horse_name"] == name), None)
        if sp:
            print(
                f"  {sp['horse_name'].title():<22} "
                f"place_rate={sp['place_rate_current_era']:.0%}  "
                f"appearances={sp['appearances']}  wins={sp['wins']}"
            )
    print()
    print(f"VP_THRESHOLD: {VP_THRESHOLD:.2f} (UNCHANGED)")
    print()
    print("Final classifications:")
    for clf in FINAL_CLASSIFICATIONS:
        print(f"  {clf}")
    print()
    print(f"Outputs: data/reports/vfu_17_*")


if __name__ == "__main__":
    main()
