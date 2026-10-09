"""
VÉLØ Racecard Loader — source-contract fix (Issue #83).

Provides load_racecards() with a strict priority order and clear fallback doctrine:

  Source order (auto):
    1. data/racecards_{date_tag}_standard.json     → 'cache'
    2. data/racecard_merged/racecard_*_{date}.json → 'rp_merged'

  CLI / env overrides:
    --source cache|rp|auto
    VELO_RACECARD_SOURCE=cache|rp|auto

Hard constraints:
  No scoring changes. No routing changes. No execution changes.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from src.velo.jurisdiction import (
    normalize_jurisdiction_code,
    resolve_jurisdiction_values,
)

# Venue-code fallback is deliberately allowlisted.  RP's per-race country/region
# metadata is authoritative; these sets are used only for older merged files that
# genuinely pre-date that metadata.  An unrecognised venue must remain unknown so
# the downstream UK/IRE jurisdiction filter fails closed.
_IRE_VENUE_CODES = frozenset({
    "GOW", "LEO", "NAV", "CUR", "TIP", "GAL", "KIL", "KLN", "BAL", "BEL",
    "CLO", "DUN", "FAI", "LIM", "NAA", "PAR", "ROS", "SLI", "THU",
    "WEX", "NAS", "DRO", "DWR", "FFA", "GRA", "KIG",
    "PTK", "DPT", "DOW", "COR", "KLB", "PUN", "TRA", "TRM", "TRAMORE",
    "LIT", "SLIGO", "WEXFORD",
})

_GB_VENUE_CODES = frozenset({
    "AIN", "ASC", "AYR", "BAN", "BANGOR-ON-DEE", "BAT", "BATH_GB", "BEV",
    "BRI", "BRIGHTON", "CAR", "CARLISLE", "CARTMEL", "CAT", "CHE", "CHEPSTOW_GB",
    "CHESTER", "CHM", "CHP", "CHS", "CMS", "CRL", "CRT", "DON", "EPS", "EXE",
    "FAK", "FFO", "FLK", "FOL", "FON", "GOO", "HAM", "HAY", "HER", "HEX",
    "HUN", "HUNTINGDON",
    "KEL", "KELSO", "KEM", "LEI", "LIN", "LINAW", "LINGFIELD_AW_GB", "LUD",
    "MAR", "MUS", "NAB", "NBY", "NCS", "NEW", "NEWCASTLE_AW", "NEWMARKET_JULY",
    "NEWTON_ABBOT", "NMK", "NOT", "PER", "PLU", "PON", "RED", "REDCAR",
    "RIP", "SAL", "SALISBURY", "SAN", "SEDGEFIELD", "SOUTHWELL", "STH", "STR",
    "TAU", "THI", "UTT", "UTTOXETER", "WAR", "WARWICK", "WDR", "WET", "WIN",
    "WINDSOR", "WOL", "WOR", "YAR", "YOR",
})


def _normalise_region_code(value: Any) -> str:
    """Return a normalizer-compatible region code without guessing jurisdiction."""
    return normalize_jurisdiction_code(value)


def _resolve_rp_merged_region(
    rp: dict[str, Any], race_data: dict[str, Any], venue_code: str
) -> str:
    """Resolve jurisdiction from RP metadata, using venue codes only as fallback.

    The most granular race-level metadata wins.  In particular, a non-GB/IRE
    country such as ``FR`` must survive even when ``region`` is blank.  Venue
    fallback is used only when every authoritative field is empty, and unknown
    venues stay blank so ``normalize_race`` classifies them as ``unknown``.
    """
    race_info = race_data.get("race_info")
    metadata_sources = (
        race_info if isinstance(race_info, dict) else {},
        race_data,
        rp,
    )
    metadata_values = [
        source.get(key)
        for source in metadata_sources
        for key in ("region", "country")
    ]
    if any(_normalise_region_code(value) for value in metadata_values):
        return resolve_jurisdiction_values(metadata_values)

    if venue_code in _IRE_VENUE_CODES:
        return "IRE"
    if venue_code in _GB_VENUE_CODES:
        return "GB"
    return ""


def _parse_betting_forecast(forecast_str: str | None) -> dict[str, float]:
    """
    Parse a RP betting forecast string into {horse_name_lower: decimal_odds}.

    Handles: "4/6 One Knight, 5/2 The Flaggy Shore, 100/1 Kenobi"
             "EVS Bluegrass, 2/1 Crystal Queen" (EVS = 2.0)
    Strips favourite markers (F, JF, CF) from odds tokens.
    Segments that cannot be parsed are skipped; returns {} for None/empty input.
    """
    if not forecast_str:
        return {}
    result: dict[str, float] = {}
    for part in forecast_str.split(","):
        part = part.strip()
        if not part:
            continue
        tokens = part.split(None, 1)
        if len(tokens) != 2:
            continue
        odds_tok, horse_name = tokens
        # Strip favourite markers (trailing F, JF, CF)
        odds_tok = odds_tok.rstrip("FJCfjc")
        try:
            if odds_tok.upper() in ("EVS", "EVENS"):
                dec = 2.0
            elif "/" in odds_tok:
                num, den = odds_tok.split("/")
                dec = round(int(num) / int(den) + 1, 3)
            else:
                # Bare tokens are NET prices: 0.25 -> 1.25, 3.0 -> 4.0.
                #
                # There used to be a branch here that treated a sub-1 result as
                # a probability and inverted it (1/0.25 = 4.00). It existed to
                # absorb the negative tokens that build_betting_forecast emitted
                # for odds-on runners, and it turned a 1/4 favourite into a 3/1
                # chance that nothing downstream could distinguish from a real
                # one. Both sides are fixed now: the writer emits the net price
                # unchanged and a genuine odds-on runner lands correctly here.
                dec = round(float(odds_tok) + 1, 3)
                if dec < 1.0:
                    # Impossible as decimal odds. Treat as unavailable rather
                    # than repair it into a plausible-looking wrong price.
                    continue
            result[horse_name.strip().lower()] = dec
        except (ValueError, ZeroDivisionError):
            continue
    return result


def _fuzzy_odds_lookup(name: str, forecast_odds: dict[str, float]) -> float:
    """
    Look up a horse's forecast odds by fuzzy name match (strips non-alpha chars).

    Returns 0.0 when no match found (caller uses 0.0 as 'odds unavailable').
    """
    import re as _re
    if not forecast_odds:
        return 0.0
    name_key = _re.sub(r"[^a-z]", "", name.lower())
    for fname, dec in forecast_odds.items():
        fname_key = _re.sub(r"[^a-z]", "", fname)
        if fname_key == name_key or (len(fname_key) > 4 and (fname_key in name_key or name_key in fname_key)):
            return dec
    return 0.0


def load_rp_merged_as_racecards(date_str: str, data_root: Path) -> list[dict[str, Any]]:
    """
    Synthesise Racing API-compatible race dicts from RP merged JSON files.

    Reads all {data_root}/racecard_merged/racecard_*_{date_str}.json files and
    builds race dicts with enough structure for normalize_race() to process.

    Hydration improvements (Issue #85 — RP_MERGED differentiation collapse):
      - betting_forecast parsed and injected as per-horse "odds" → normalizer
        converts to best_odds_decimal, driving sp_dec/sp_rank differentiation
      - ts_latest, ts_master wired as "ts" and "ts_master" for TS-based scoring
      - postdata_score, or_compression_score, plot_conviction wired as "pdf_intel"
        so _build_live_features() reads them on the first pass
      - going and race_class extracted from race_info when present

    Fields absent from RP data remain None. RP race country/region metadata is
    authoritative; known venue-code fallback is used only when it is absent.
    Returns an empty list if no RP merged files exist for the date.
    """
    import re as _re

    merged_dir = data_root / "racecard_merged"
    rp_files = list(merged_dir.glob(f"racecard_*_{date_str}.json"))
    if not rp_files:
        return []

    races: list[dict[str, Any]] = []
    for rp_path in sorted(rp_files):
        try:
            rp = json.loads(rp_path.read_text())
        except Exception:
            continue

        venue_name: str = rp.get("venue", rp_path.stem.split("_")[1])
        filename_prefix = "racecard_"
        filename_suffix = f"_{date_str}"
        stem = rp_path.stem
        if stem.startswith(filename_prefix) and stem.endswith(filename_suffix):
            venue_code = stem[len(filename_prefix):-len(filename_suffix)].upper()
        else:
            venue_code = str(rp.get("venue_code") or "").strip().upper()
        for race_time, race_data in rp.get("races", {}).items():
            horses = race_data.get("horses", [])
            if not horses:
                continue

            region = _resolve_rp_merged_region(rp, race_data, venue_code)

            # ── Betting forecast → per-horse odds ────────────────────────────
            forecast_raw = race_data.get("betting_forecast", "")
            forecast_odds = _parse_betting_forecast(forecast_raw)

            # ── Race-level metadata ───────────────────────────────────────────
            race_info = race_data.get("race_info", "")
            going_str: str | None = None
            race_class: str | None = None
            race_type_str: str | None = None
            if isinstance(race_info, dict):
                going_str = race_info.get("going") or None
                rc = race_info.get("race_class")
                race_class = str(rc) if rc is not None else None
                race_type_str = race_info.get("race_type") or None
            else:
                race_info_str = str(race_info) if race_info else ""
                m_going = _re.search(r"\b(Good|Firm|Soft|Heavy|Yielding|Standard)[^\)]*", race_info_str, _re.I)
                if m_going:
                    going_str = m_going.group(0).strip()
                m_class = _re.search(r"Class\s*(\d)", race_info_str, _re.I)
                if m_class:
                    race_class = m_class.group(1)

            runners = []
            for h in horses:
                name = h.get("horse_name") or h.get("horse", "")
                if not name:
                    continue

                # Odds from betting forecast
                odds_dec = _fuzzy_odds_lookup(name, forecast_odds)

                # TS: prefer ts_latest, fall back to ts_adjusted / ts_master
                ts_val = (
                    h.get("ts_latest")
                    or h.get("ts_adjusted")
                    or h.get("ts_master")
                )

                # Build pdf_intel dict for immediate use in _build_live_features()
                pdf_intel: dict[str, Any] = {
                    "postdata_score": h.get("postdata_score", 0.0) or 0.0,
                    "or_compression_score": h.get("or_compression_score", 0.0) or 0.0,
                    "plot_conviction": h.get("plot_conviction", 0.0) or 0.0,
                    "ts_master": float(h.get("ts_master") or h.get("ts_adjusted") or 0),
                    "or_delta_to_best_win": 0.0,
                    "trainer_form_signal": h.get("trainer_form_signal", 0.0) or 0.0,
                    "ts_trend_signal": h.get("ts_trend_signal", 0.0) or 0.0,
                    "or_trend_signal": h.get("or_trend_signal", 0.0) or 0.0,
                    "handicap_plot_score": h.get("handicap_plot_score") or 0.0,
                    # Pass through the raw RP horse dict for downstream enrichment
                    "_rp_raw": h,
                }

                runners.append({
                    "horse": name,
                    "horse_id": h.get("horse_id") or f"rp_{venue_code}_{name.lower().replace(' ', '_')}",
                    "age": h.get("age") or None,
                    "sex": None,
                    "lbs": h.get("weight") or None,
                    "draw": h.get("draw") or None,
                    "trainer": h.get("trainer") or h.get("trainer_name") or None,
                    "jockey": h.get("jockey") or h.get("jockey_name") or None,
                    "ofr": h.get("current_or") or None,
                    "rpr": h.get("rpr_master") or None,
                    "rp_rpr_archive_only": h.get("rpr_master") or None,
                    "rp_rpr_velo_allowed": True,
                    "ts": ts_val,
                    "ts_master": h.get("ts_master"),
                    "form": None,
                    "last_run": None,
                    # Odds: set so normalizer converts to best_odds_decimal
                    "odds": odds_dec if odds_dec > 0 else None,
                    # RP passthrough fields
                    "_rp_horse_name": name,
                    "_rp_ts_base": h.get("ts_base"),
                    "_rp_plot_conviction": h.get("plot_conviction"),
                    "_rp_or_compression_score": h.get("or_compression_score"),
                    "_rp_postdata_score": h.get("postdata_score"),
                    # Spotlight text — scorer looks for "spotlight", rp_merged stores as "spotlight_comment"
                    "spotlight": h.get("spotlight_comment") or h.get("diomed_comment") or "",
                    # Pre-built pdf_intel so _build_live_features() reads it immediately
                    # (before the post-normalization pdf_intel_cache loop runs)
                    "pdf_intel": pdf_intel,
                })

            time_parts = race_time.replace(":", "_")
            races.append({
                "race_id": str(
                    race_data.get("race_id")
                    or f"rp_{venue_code}_{date_str.replace('-', '')}_{time_parts}"
                ),
                "course": venue_name,
                "course_id": venue_code.lower(),
                "date": date_str,
                "off_time": race_time,
                "race_name": (race_info.get("race_title", "") if isinstance(race_info, dict) else str(race_info))[:80],
                "distance_f": None,
                "going": going_str,
                "race_class": race_class,
                "type": race_type_str,
                "region": region,
                "runners": runners,
                # Keep raw forecast for diagnostics
                "_rp_betting_forecast": forecast_raw,
            })

    return races


def load_racecards(
    date_tag: str,
    date_str: str,
    data_root: Path,
    racing_base: str = "",
    racing_user: str = "",
    racing_pass: str = "",
    source: str | None = None,
) -> tuple[list[dict[str, Any]], str]:
    """
    Return (races_list, source_label) for the given date.

    Source priority (auto):
      1. data/racecards_{date_tag}_standard.json  → 'cache'
      2. data/racecard_merged/racecard_*_{date_str}.json  → 'rp_merged'

    Env overrides:
      VELO_RACECARD_SOURCE=cache|rp|auto

    source labels returned: 'cache' | 'rp_merged'
    """
    _source = (source or os.getenv("VELO_RACECARD_SOURCE", "auto")).lower()
    cache_path = data_root / f"racecards_{date_tag}_standard.json"

    if _source == "cache":
        if not cache_path.exists():
            raise RuntimeError(f"--source cache specified but {cache_path} not found")
        raw = json.loads(cache_path.read_text())
        races = raw if isinstance(raw, list) else raw.get("racecards", [])
        return races, "cache"

    if _source == "rp":
        races = load_rp_merged_as_racecards(date_str, data_root)
        if not races:
            raise RuntimeError(
                f"--source rp specified but no RP merged files found for {date_str}\n"
                f"  Expected: {data_root}/racecard_merged/racecard_*_{date_str}.json"
            )
        return races, "rp_merged"

    # ── Auto: cache → rp_merged ─────────────────────────────────────────
    if cache_path.exists():
        raw = json.loads(cache_path.read_text())
        races = raw if isinstance(raw, list) else raw.get("racecards", [])
        return races, "cache"

    rp_races = load_rp_merged_as_racecards(date_str, data_root)
    if rp_races:
        return rp_races, "rp_merged"

    raise RuntimeError(
        f"No racecard source available for {date_str}.\n"
        f"  Tried: cache ({cache_path.name}) → RP merged\n"
        "  Fix: supply a cache file or run RP PDF ingestion."
    )
