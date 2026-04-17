"""
VÉLØ RPD-C Deterministic Tag Rules
====================================
Pure rules engine — no database, no LLM, no SQLite.

Input:  dict of intelligence stack fields for a single run.
Output: dict with rpdc_tag_base, rpdc_confidence, rpdc_evidence, rpdc_blockers.

Tags (RPD-C):
    T — Target:     Connections intend to win. Structural evidence of deployment.
    H — Honest:     Runs to rating. Default when no stronger evidence present.
    S — Speculative: Insufficient data to classify. High uncertainty.
    P — Prep:       Educational or fitness run. Not expected to win today.
    E — Exhausted:  Regressive profile. Nothing structural supports a win.

This engine is the single source of truth for RPD-C classification.
It uses ONLY the 5-layer intelligence stack. It does NOT use jockey bookings,
gear changes, or market data — those are live-only context added at briefing time.

Blocker logic inherited from rpd_v2.py:
    P blocker: market_shortening (cannot assign P to a shortening horse)
    E blockers: won_last_time, market_shortening

Author: VÉLØ Oracle Prime
Version: 3.0 (Supabase-native, intelligence-stack-driven)
"""

from dataclasses import dataclass, field
from typing import Optional


# ---------------------------------------------------------------------------
# Return type
# ---------------------------------------------------------------------------

@dataclass
class RPDCResult:
    rpdc_tag_base: str          # T / H / S / P / E
    rpdc_confidence: str        # high / medium / low
    rpdc_evidence: list         # list of string codes that fired
    rpdc_blockers: list         # list of blocker codes that triggered
    rpdc_explanation: str       # human-readable explanation for VOX


# ---------------------------------------------------------------------------
# Evidence code constants
# ---------------------------------------------------------------------------

# T — Target evidence codes (derivable from intelligence stack)
T_EVIDENCE = {
    "mr_3plus_codes":    "manual_review_priority=TRUE with 3+ reason codes",
    "mr_4plus_codes":    "manual_review_priority=TRUE with 4+ reason codes (Tier 3)",
    "high_identity":     "identity_confidence=high (clean entity, auditable)",
    "full_restore":      "full_restore_live=TRUE (all three restore dims match prior win)",
    "post_drop_restore": "post_drop_restore=TRUE (first run after mark drop, winning conditions)",
    "compress_restore":  "compression_plus_restore=TRUE (mark dropping AND restored conditions)",
    "near_winning_mark": "current_vs_last_winning_or BETWEEN -8 AND 5",
    "reactivation_restore": "reactivation_candidate=TRUE AND full_restore_live=TRUE",
    "campaign_fitness":  "run 3-6 of current campaign (peak fitness window)",
}

# P — Prep evidence codes
P_EVIDENCE = {
    "long_absence":      "long_layoff_flag=TRUE (60+ days off)",
    "no_restore_signal": "no restore flags active after absence",
    "no_mr":             "manual_review_priority=FALSE with no plot pressure",
    "or_above_peak":     "or_rating_num > career_peak_or_to_date (rated above career peak)",
    "very_long_absence": "days_since_last_run >= 180 (6+ months off)",
}

# S — Speculative evidence codes
S_EVIDENCE = {
    "ambiguous_identity":    "identity_confidence=ambiguous (cannot audit entity reliably)",
    "layoff_no_restore":     "layoff_flag=TRUE AND plot_pressure_flag=FALSE",
    "no_winning_reference":  "no last_winning_or_to_date (never won in dataset)",
    "treadmill_no_restore":  "or_treadmill_flag=TRUE but no restore signal",
}

# E — Exhausted/Irrelevant evidence codes
E_EVIDENCE = {
    "far_above_winning_mark": "current_vs_last_winning_or > 10 (far above last winning OR)",
    "long_losing_run":        "10+ run losing streak from run history analysis",
    "no_pressure_no_restore": "plot_pressure_flag=FALSE AND manual_review_priority=FALSE",
    "ambiguous_long_absent":  "ambiguous identity + 60+ days off + no signals",
}

# Blockers
BLOCKERS = {
    "market_shortening": "Cannot assign P or E — horse shortening in market contradicts narrative",
    "won_last_time":     "Cannot assign E — a recent winner is not exhausted",
}


# ---------------------------------------------------------------------------
# Core tagger
# ---------------------------------------------------------------------------

def tag_from_intelligence_row(row: dict,
                               market_shortening: bool = False,
                               won_last_time: Optional[bool] = None) -> RPDCResult:
    """
    Classify a single run using the intelligence stack.

    Args:
        row: Dict of fields from the intelligence stack (see expected keys below).
        market_shortening: True if BSP/morning price contracted significantly.
        won_last_time: True if horse won its previous race. None = unknown.

    Expected row keys (all optional with sensible None defaults):
        manual_review_priority, plot_pressure_flag, plot_reason_codes,
        identity_confidence, ambiguity_flag,
        layoff_flag, long_layoff_flag, days_since_last_run,
        mark_restore_candidate, setup_restore_candidate,
        reactivation_candidate, compression_plus_restore,
        post_drop_restore, full_restore_live, trip_restore_flag, course_restore_flag,
        or_rating_num, or_change, current_vs_last_winning_or,
        career_peak_or_to_date, last_winning_or_to_date,
        or_treadmill_flag, mark_compression_flag,
        run_number (int — run number in current year)
        is_win (bool — did this run result in a win)

    Returns:
        RPDCResult with tag, confidence, evidence list, blockers list.
    """

    # ── Extract fields with safe defaults ─────────────────────────────────────
    mr              = row.get("manual_review_priority") or False
    pressure        = row.get("plot_pressure_flag") or False
    reason_codes    = row.get("plot_reason_codes") or []
    n_codes         = len(reason_codes)
    identity        = row.get("identity_confidence") or "unknown"
    ambiguous       = row.get("ambiguity_flag") or False

    layoff          = row.get("layoff_flag") or False
    long_layoff     = row.get("long_layoff_flag") or False
    days_off        = row.get("days_since_last_run") or 0

    reactivation    = row.get("reactivation_candidate") or False
    compress_rest   = row.get("compression_plus_restore") or False
    post_drop_rest  = row.get("post_drop_restore") or False
    full_restore    = row.get("full_restore_live") or False
    trip_restore    = row.get("trip_restore_flag") or False
    course_restore  = row.get("course_restore_flag") or False

    or_num          = row.get("or_rating_num")
    career_peak     = row.get("career_peak_or_to_date")
    last_win_or     = row.get("last_winning_or_to_date")
    vs_win_or       = row.get("current_vs_last_winning_or")
    treadmill       = row.get("or_treadmill_flag") or False
    mark_compress   = row.get("mark_compression_flag") or False

    run_number      = row.get("run_number") or row.get("run_number_2025") or row.get("run_number_2024") or 0
    is_win          = row.get("is_win") or False

    # ── Derived helpers ────────────────────────────────────────────────────────
    high_identity   = (identity == "high")
    near_win_mark   = (vs_win_or is not None and -8 <= vs_win_or <= 5)
    above_peak      = (or_num is not None and career_peak is not None and or_num > career_peak + 2)
    far_above_win   = (vs_win_or is not None and vs_win_or > 10)
    in_fitness_win  = (3 <= run_number <= 6)  # peak fitness window
    no_win_ref      = (last_win_or is None)

    blockers_hit = []
    evidence = []

    # ── Evaluate T (Target) ────────────────────────────────────────────────────
    t_evidence = []

    if mr and n_codes >= 4 and high_identity:
        t_evidence.append("mr_4plus_codes")
    elif mr and n_codes >= 3 and high_identity:
        t_evidence.append("mr_3plus_codes")

    if high_identity:
        t_evidence.append("high_identity")

    if full_restore and high_identity:
        t_evidence.append("full_restore")

    if post_drop_rest:
        t_evidence.append("post_drop_restore")

    if compress_rest:
        t_evidence.append("compress_restore")

    if near_win_mark and (full_restore or post_drop_rest or reactivation):
        t_evidence.append("near_winning_mark")

    if reactivation and full_restore:
        t_evidence.append("reactivation_restore")

    if in_fitness_win and mr:
        t_evidence.append("campaign_fitness")

    # T requires at least 2 distinct evidence codes to fire
    t_qualifies = len(t_evidence) >= 2

    # ── Evaluate P (Prep) ──────────────────────────────────────────────────────
    p_evidence = []
    p_blocked_by = []

    if long_layoff:
        p_evidence.append("long_absence")
    if days_off >= 180:
        p_evidence.append("very_long_absence")
    if not pressure and not mr:
        p_evidence.append("no_mr")
    if long_layoff and not full_restore and not trip_restore:
        p_evidence.append("no_restore_signal")
    if above_peak:
        p_evidence.append("or_above_peak")

    if market_shortening and len(p_evidence) >= 1:
        p_blocked_by.append("market_shortening")

    # P requires 2+ evidence and no blockers
    p_qualifies = (len(p_evidence) >= 2) and (len(p_blocked_by) == 0)

    # ── Evaluate S (Speculative) ───────────────────────────────────────────────
    s_evidence = []

    if ambiguous or identity == "ambiguous":
        s_evidence.append("ambiguous_identity")
    if layoff and not pressure:
        s_evidence.append("layoff_no_restore")
    if no_win_ref and not pressure:
        s_evidence.append("no_winning_reference")
    if treadmill and not full_restore and not trip_restore:
        s_evidence.append("treadmill_no_restore")

    # S requires 1+ evidence
    s_qualifies = len(s_evidence) >= 1

    # ── Evaluate E (Exhausted) ─────────────────────────────────────────────────
    e_evidence = []
    e_blocked_by = []

    if far_above_win:
        e_evidence.append("far_above_winning_mark")
    if not pressure and not mr:
        e_evidence.append("no_pressure_no_restore")
    if ambiguous and long_layoff and not pressure:
        e_evidence.append("ambiguous_long_absent")

    # E blockers
    if won_last_time is True:
        e_blocked_by.append("won_last_time")
    if market_shortening:
        e_blocked_by.append("market_shortening")

    # E requires 2+ evidence and no blockers
    e_qualifies = (len(e_evidence) >= 2) and (len(e_blocked_by) == 0)

    # ── Priority decision ──────────────────────────────────────────────────────
    # T overrides everything when qualified.
    # Then P (explicit prep signal).
    # Then S (uncertainty/ambiguity).
    # Then E (regressive profile).
    # H is default when nothing stronger fires.

    if t_qualifies:
        tag        = "T"
        evidence   = t_evidence
        n_ev       = len(t_evidence)
        confidence = "high" if n_ev >= 4 else ("medium" if n_ev >= 2 else "low")
        blockers   = blockers_hit
        explanation = (
            f"Target classification. {n_codes} plot codes active. "
            f"Key signals: {', '.join(t_evidence[:3])}. "
            f"Identity: {identity}."
        )

    elif p_qualifies and not t_qualifies:
        tag        = "P"
        evidence   = p_evidence
        confidence = "high" if len(p_evidence) >= 3 else "medium"
        blockers   = p_blocked_by
        explanation = (
            f"Prep classification. {days_off or '?'} days off. "
            f"No meaningful restore signal found. "
            f"Signals: {', '.join(p_evidence)}."
        )

    elif s_qualifies and not t_qualifies:
        tag        = "S"
        evidence   = s_evidence
        confidence = "medium" if len(s_evidence) >= 2 else "low"
        blockers   = []
        explanation = (
            f"Speculative — insufficient data for clean classification. "
            f"Uncertainty sources: {', '.join(s_evidence)}. "
            f"Identity: {identity}."
        )

    elif e_qualifies:
        tag        = "E"
        evidence   = e_evidence
        confidence = "medium" if len(e_evidence) >= 3 else "low"
        blockers   = e_blocked_by
        explanation = (
            f"Exhausted/Irrelevant. No structural readiness signals. "
            f"Evidence: {', '.join(e_evidence)}."
        )

    else:
        # Default — Honest
        tag        = "H"
        evidence   = ["default_honest"]
        confidence = "medium" if pressure else "low"
        blockers   = []
        explanation = (
            f"Honest — default classification. "
            f"Runs to rating. plot_pressure={pressure}, mr={mr}. "
            f"No stronger classification evidence."
        )

    return RPDCResult(
        rpdc_tag_base=tag,
        rpdc_confidence=confidence,
        rpdc_evidence=evidence,
        rpdc_blockers=blockers,
        rpdc_explanation=explanation,
    )


# ---------------------------------------------------------------------------
# Confidence scorer (standalone — for use in backfill pipelines)
# ---------------------------------------------------------------------------

def confidence_from_evidence(tag: str, evidence: list) -> str:
    """Map evidence count to confidence level by tag."""
    n = len(evidence)
    if tag == "T":
        return "high" if n >= 4 else ("medium" if n >= 2 else "low")
    if tag == "P":
        return "high" if n >= 3 else "medium"
    if tag == "S":
        return "medium" if n >= 2 else "low"
    if tag == "E":
        return "medium" if n >= 3 else "low"
    return "medium"  # H default


# ---------------------------------------------------------------------------
# Live runner tagger (pre-race, from Racing API data only)
# ---------------------------------------------------------------------------

def tag_from_live_runner(runner: dict,
                          race: dict = None,
                          market_shortening: bool = False) -> RPDCResult:
    """
    Classify a runner using live Racing API data only.

    This is the pre-race tag — confidence will always be 'low' because
    it works without the full intelligence stack. It will be upgraded
    when the run enters the intelligence stack after the season is processed.

    Args:
        runner: Runner dict from Racing API (keys: last_run, headgear_run,
                headgear, trainer_rtf, trainer_14_day_wins, trainer_14_day_runs,
                ofr, wind_surgery_run, odds, form, lbs, draw, etc.)
        race:   Race dict for context (going, class, distance_f, type).
        market_shortening: True if pre-race market shows significant contraction.

    Returns:
        RPDCResult — always confidence='low', evidence codes prefixed 'live_'.
    """
    race = race or {}

    last_run_days   = _safe_int(runner.get("last_run"))
    headgear_run    = _safe_int(runner.get("headgear_run"))
    headgear        = runner.get("headgear") or ""
    trainer_rtf     = _safe_float(runner.get("trainer_rtf"))
    t14_wins        = _safe_int(runner.get("trainer_14_day_wins")) or 0
    t14_runs        = _safe_int(runner.get("trainer_14_day_runs")) or 1
    wind_surg_run   = _safe_int(runner.get("wind_surgery_run"))
    form_str        = runner.get("form") or ""
    ofr             = _safe_int(runner.get("ofr"))

    t14_strike = (t14_wins / max(t14_runs, 1)) if t14_runs >= 3 else 0.0
    long_layoff     = (last_run_days is not None and last_run_days >= 60)
    very_long       = (last_run_days is not None and last_run_days >= 180)
    first_headgear  = (headgear_run == 1 and headgear)
    wind_first_back = (wind_surg_run == 1)
    trainer_form    = (t14_strike >= 0.25)

    # Derive evidence
    t_ev, p_ev, s_ev = [], [], []

    # T signals from live data
    if trainer_form:
        t_ev.append("live_trainer_in_form")
    if first_headgear:
        t_ev.append("live_first_time_headgear")
    if wind_first_back:
        t_ev.append("live_wind_surgery_first_back")
    if market_shortening and trainer_form:
        t_ev.append("live_market_shortening")

    # P signals
    if long_layoff and not first_headgear:
        p_ev.append("live_long_absence")
    if very_long:
        p_ev.append("live_very_long_absence")
    if not trainer_form and long_layoff:
        p_ev.append("live_trainer_not_in_form")

    # S signals
    if long_layoff and not trainer_form and not first_headgear:
        s_ev.append("live_layoff_no_signals")
    recent_poor = ("0" in form_str[-3:] or "P" in form_str[-3:] or "U" in form_str[-3:])
    if recent_poor and not trainer_form:
        s_ev.append("live_recent_poor_form")

    # Blockers
    p_blocked = market_shortening and len(p_ev) >= 1

    # Decision — same priority as intelligence-stack tagger
    if len(t_ev) >= 2:
        tag, evidence, blockers = "T", t_ev, []
        explanation = f"Live T: {', '.join(t_ev[:2])}. Confidence limited — live data only."
    elif len(p_ev) >= 2 and not p_blocked:
        tag, evidence, blockers = "P", p_ev, []
        explanation = f"Live P: {last_run_days}d off, no intent signals. Confidence limited."
    elif len(s_ev) >= 1:
        tag, evidence, blockers = "S", s_ev, []
        explanation = f"Live S: uncertainty sources: {', '.join(s_ev)}. Confidence limited."
    else:
        tag, evidence, blockers = "H", ["live_default_honest"], []
        explanation = "Live H (default): insufficient live data for stronger classification."

    return RPDCResult(
        rpdc_tag_base=tag,
        rpdc_confidence="low",   # always low for live-only tags
        rpdc_evidence=evidence,
        rpdc_blockers=blockers,
        rpdc_explanation=explanation,
    )


def _safe_int(v) -> Optional[int]:
    try:
        return int(v) if v is not None else None
    except (ValueError, TypeError):
        return None


def _safe_float(v) -> Optional[float]:
    try:
        return float(v) if v is not None else None
    except (ValueError, TypeError):
        return None
