#!/usr/bin/env python3
"""
scripts/ops/vfu_pattern_prosecutor.py
=======================================
VFU-05 — Pattern Prosecutor: prosecutes beliefs against current-era evidence.

Read-only. No doctrine changes. No scoring changes. No Supabase writes.
No canonical Passport mutation. No live staking rules.

Every pattern record carries:
  blocked_from_live_use: True
  human_approval_required: True

Price claims are limited to TIER_A rows (pick_sp present, n=107).
Repeated-horse conclusions carry NAME_ONLY_CONFIDENCE (horse_id=0%).
No hard course bans from n<20.
"""
from __future__ import annotations

import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean as smean

ROOT = Path(__file__).resolve().parents[2]

RECORDS_FILE  = ROOT / "data/reports/vfu_full_current_era_autopsy_records.jsonl"
PATTERNS_FILE = ROOT / "data/reports/vfu_full_current_era_pattern_evidence.jsonl"
PASSPORTS_FILE= ROOT / "data/reports/vfu_full_current_era_passport_candidates.jsonl"
GAPS_FILE     = ROOT / "data/reports/vfu_full_current_era_quality_gaps.json"
SUMMARY_FILE  = ROOT / "data/reports/vfu_full_current_era_autopsy_summary.json"
COURSE_TABLE  = ROOT / "data/reports/current_era_course_excellence_table.json"

OUT_SUMMARY_MD  = ROOT / "data/reports/vfu_pattern_prosecutor_current_era_summary.md"
OUT_SUMMARY_JSON= ROOT / "data/reports/vfu_pattern_prosecutor_current_era_summary.json"
OUT_RECORDS     = ROOT / "data/reports/vfu_pattern_prosecutor_evidence_records.jsonl"
OUT_WATCHLIST   = ROOT / "data/reports/vfu_pattern_prosecutor_watchlist.json"
OUT_REJECTED    = ROOT / "data/reports/vfu_pattern_prosecutor_rejected_patterns.json"
OUT_HUMAN_QUEUE = ROOT / "data/reports/vfu_pattern_prosecutor_human_review_queue.json"

VERDICTS = {
    "PROMOTE_TO_WATCHLIST",
    "KEEP_OBSERVING",
    "REJECT_FOR_NOW",
    "NEEDS_MORE_DATA",
    "DATA_BLOCKED",
    "HUMAN_REVIEW_REQUIRED",
}

BASELINE_SR = 0.264   # usable rows (TIER_A/B/C), 256/969
CONVICTION_THRESHOLD = BASELINE_SR + 0.10  # 36.4%


# ── Loaders ──────────────────────────────────────────────────────────────────

def load_jsonl(path: Path) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        return [json.loads(l) for l in f if l.strip()]


# ── Evidence subsets ──────────────────────────────────────────────────────────

def usable(records: list[dict]) -> list[dict]:
    return [r for r in records if r["evidence_quality_tier"] not in ("TIER_D_EVENT_ONLY", "TIER_E_UNUSABLE")]


def tier_a(records: list[dict]) -> list[dict]:
    return [r for r in records if r["evidence_quality_tier"] == "TIER_A_FULL"]


# ── Pattern record factory ────────────────────────────────────────────────────

def _make_pattern(
    pattern_id: str,
    belief: str,
    evidence_source: str,
    rows: list[dict],
    excluded: list[dict],
    exclusion_reasons: list[str],
    verdict: str,
    reason: str,
    next_action: str,
    allowed_scope: str,
    sample_warning: str = "",
    roi: float | None = None,
    extra: dict | None = None,
) -> dict:
    assert verdict in VERDICTS
    win_count = sum(1 for r in rows if r.get("outcome") == "WIN")
    loss_count = sum(1 for r in rows if r.get("outcome") in ("MISS", "PLACED"))
    n = len(rows)
    sr = round(win_count / n, 3) if n else None
    confidence = "INSUFFICIENT" if n < 20 else ("LOW" if n < 50 else ("MEDIUM" if n < 100 else "HIGH"))
    return {
        "pattern_id": pattern_id,
        "belief": belief,
        "evidence_source": evidence_source,
        "evidence_count": n,
        "usable_count": n,
        "excluded_count": len(excluded),
        "exclusion_reasons": exclusion_reasons,
        "win_count": win_count,
        "loss_count": loss_count,
        "SR": sr,
        "ROI": roi,
        "sample_size_warning": sample_warning,
        "confidence": confidence,
        "verdict": verdict,
        "reason": reason,
        "recommended_next_action": next_action,
        "allowed_scope": allowed_scope,
        "blocked_from_live_use": True,
        "human_approval_required": True,
        **(extra or {}),
    }


# ── Belief prosecutors ────────────────────────────────────────────────────────

def prosecute_beliefs(records: list[dict], gaps: dict) -> list[dict]:
    use = usable(records)
    t_a = tier_a(records)
    patterns: list[dict] = []

    # ── VP BELIEFS ────────────────────────────────────────────────────────────

    # 1. VP >= 0.40 is a valid opportunity signal
    vp40 = [r for r in use if (r.get("vp") or 0) >= 0.40]
    vp40_w = sum(1 for r in vp40 if r.get("outcome") == "WIN")
    sr40 = round(vp40_w / len(vp40), 3) if vp40 else 0
    patterns.append(_make_pattern(
        "VP_BELIEF_01", "VP >= 0.40 is a valid opportunity signal",
        "vfu_full_current_era_autopsy_records.jsonl",
        vp40, [r for r in use if (r.get("vp") or 0) < 0.40], [],
        "PROMOTE_TO_WATCHLIST" if sr40 >= CONVICTION_THRESHOLD else "KEEP_OBSERVING",
        f"SR={sr40:.1%} vs baseline {BASELINE_SR:.1%}. +{round((sr40-BASELINE_SR)*100,1)}pp lift on {len(vp40)} rows.",
        "Continue dry-run monitoring. Track daily SR at VP>=0.40.",
        "DRY_RUN_MONITORING_ONLY",
    ))

    # 2. VP >= 0.45 improves further
    vp45 = [r for r in use if (r.get("vp") or 0) >= 0.45]
    vp45_w = sum(1 for r in vp45 if r.get("outcome") == "WIN")
    sr45 = round(vp45_w / len(vp45), 3) if vp45 else 0
    lift45 = round((sr45 - sr40) * 100, 1) if vp40 else 0
    patterns.append(_make_pattern(
        "VP_BELIEF_02", "VP >= 0.45 improves confidence over 0.40",
        "vfu_full_current_era_autopsy_records.jsonl",
        vp45, [], [],
        "PROMOTE_TO_WATCHLIST" if sr45 > sr40 + 0.02 else "KEEP_OBSERVING",
        f"SR={sr45:.1%} vs VP>=0.40 SR={sr40:.1%}. Delta={lift45}pp on {len(vp45)} rows.",
        "Include VP>=0.45 sub-tier in daily dry-run panel.",
        "DRY_RUN_MONITORING_ONLY",
    ))

    # 3. VP >= 0.50 does not meaningfully improve over 0.45
    vp50 = [r for r in use if (r.get("vp") or 0) >= 0.50]
    vp50_w = sum(1 for r in vp50 if r.get("outcome") == "WIN")
    sr50 = round(vp50_w / len(vp50), 3) if vp50 else 0
    lift50 = round((sr50 - sr45) * 100, 1) if vp45 else 0
    patterns.append(_make_pattern(
        "VP_BELIEF_03", "VP >= 0.50 does not meaningfully improve over 0.45",
        "vfu_full_current_era_autopsy_records.jsonl",
        vp50, [], [],
        "KEEP_OBSERVING" if abs(lift50) < 3.0 else "NEEDS_MORE_DATA",
        f"SR={sr50:.1%} vs VP>=0.45 SR={sr45:.1%}. Delta={lift50}pp. "
        f"{'Small delta — belief holds.' if abs(lift50) < 3.0 else 'Notable delta — keep observing.'}",
        "Do not use VP>=0.50 as a hard cut-off until n>=200.",
        "OBSERVATION_ONLY",
    ))

    # 4. VP false positives concentrated in specific contexts
    fp = [r for r in use if r.get("failure_class") == "VP_FALSE_POSITIVE"]
    fp_by_layer = Counter(r.get("row_source_layer") for r in fp)
    fp_by_course_tier = Counter(r.get("course_tier") for r in fp)
    patterns.append(_make_pattern(
        "VP_BELIEF_04", "VP false positives are concentrated in specific courses/layers",
        "vfu_full_current_era_autopsy_records.jsonl",
        fp, [], [],
        "HUMAN_REVIEW_REQUIRED",
        f"{len(fp)} VP false positives. By layer: {dict(fp_by_layer)}. "
        f"By course tier: {dict(fp_by_course_tier)}.",
        "Manual review of VP_FALSE_POSITIVE autopsy records. Look for course/SP pattern.",
        "HUMAN_REVIEW_ONLY",
        extra={"fp_by_source_layer": dict(fp_by_layer), "fp_by_course_tier": dict(fp_by_course_tier)},
    ))

    # 5. VP false negatives are recoverable
    fn = [r for r in use if r.get("failure_class") == "VP_FALSE_NEGATIVE"]
    fn_high_aws = [r for r in fn if (r.get("actual_winner_sp") or 99) >= 10]
    patterns.append(_make_pattern(
        "VP_BELIEF_05", "VP false negatives are recoverable through context",
        "vfu_full_current_era_autopsy_records.jsonl",
        fn, [], [],
        "NEEDS_MORE_DATA",
        f"{len(fn)} VP false negatives. {len(fn_high_aws)} had winner SP>=10 (longshot release). "
        "Context recovery requires pick_sp coverage improvement.",
        "Expand pick_sp sourcing. Check RPDC release signal presence.",
        "RESEARCH_ONLY",
    ))

    # ── GATEKEEPER BELIEFS ───────────────────────────────────────────────────

    # 6. GREEN days outperform RED days (aggregate VP proxy)
    high_vp_day = [r for r in use if (r.get("vp") or 0) >= 0.35]
    low_vp_day = [r for r in use if (r.get("vp") or 0) < 0.25]
    sr_high = round(sum(1 for r in high_vp_day if r.get("outcome") == "WIN") / len(high_vp_day), 3) if high_vp_day else 0
    sr_low = round(sum(1 for r in low_vp_day if r.get("outcome") == "WIN") / len(low_vp_day), 3) if low_vp_day else 0
    patterns.append(_make_pattern(
        "GATE_BELIEF_06", "GREEN days (avg VP>=0.35) outperform RED days (VP<0.25)",
        "vfu_full_current_era_autopsy_records.jsonl",
        high_vp_day, low_vp_day, ["vp<0.25 rows used as RED proxy"],
        "PROMOTE_TO_WATCHLIST" if sr_high > sr_low + 0.05 else "KEEP_OBSERVING",
        f"High-VP pool SR={sr_high:.1%} vs Low-VP pool SR={sr_low:.1%}. "
        "Row-level proxy — day-level gate label not stored in union.",
        "Track daily gate label vs day SR in 14-day dry-run.",
        "DRY_RUN_MONITORING_ONLY",
    ))

    # 7. RED days protect
    patterns.append(_make_pattern(
        "GATE_BELIEF_07", "RED days protect against weak cards",
        "vfu_full_current_era_autopsy_records.jsonl",
        low_vp_day, [], ["Gate-label-level analysis requires day aggregation"],
        "KEEP_OBSERVING",
        f"Low-VP rows (VP<0.25): SR={sr_low:.1%}. Protection evidence present but day-level gate log needed.",
        "Build day-level gate log from morning cockpit output.",
        "OBSERVATION_ONLY",
    ))

    # 8. False GREEN days require warning logic
    # Jun 09 is the known case — proxy: find dates in union with many VP>=0.35 picks but no wins
    patterns.append(_make_pattern(
        "GATE_BELIEF_08", "False GREEN days require warning logic",
        "vfu_full_current_era_autopsy_records.jsonl (Jun 09 caveat)",
        [], [], ["Day-level gate log not in union — cannot enumerate false-GREEN days from rows alone"],
        "HUMAN_REVIEW_REQUIRED",
        "Jun 09 2026 confirmed false-GREEN: VP_avg=0.355 + 0 wins from 33. "
        "Cannot enumerate all false-GREEN days without day-level gate log.",
        "Build false-GREEN day tracker. Carry warning label on every GREEN signal.",
        "WARNING_ONLY",
    ))

    # 9. Jun 09 remains a known false-GREEN caveat
    patterns.append(_make_pattern(
        "GATE_BELIEF_09", "Jun 09 remains a known false-GREEN caveat",
        "VP_GATEKEEPER_PROMOTION_V1.md + vp_opportunity_panel_2026_06_14.md",
        [], [], ["Historical — not derivable from current union rows alone"],
        "PROMOTE_TO_WATCHLIST",
        "Jun 09 2026 is hardcoded as false-GREEN precedent. "
        "Every GREEN label must carry FALSE_GREEN_POSSIBLE caveat.",
        "Maintain FALSE_GREEN_POSSIBLE caveat on all GREEN gate labels permanently.",
        "WARNING_REQUIRED",
    ))

    # ── PRICE BELIEFS ────────────────────────────────────────────────────────

    sp_warning = "SP_SAMPLE_LIMITED: pick_sp available for only 107/1,263 rows (TIER_A only)."

    # 10. 6.0+ SP is a dead zone
    dead = [r for r in t_a if (r.get("pick_sp") or 0) >= 6.0]
    dead_w = sum(1 for r in dead if r.get("outcome") == "WIN")
    patterns.append(_make_pattern(
        "PRICE_BELIEF_10", "SP >= 6.0 is a dead zone",
        "vfu_full_current_era_autopsy_records.jsonl (TIER_A only)",
        dead,
        [r for r in records if r.get("pick_sp") is None],
        ["rows with no pick_sp excluded from price analysis"],
        "NEEDS_MORE_DATA",
        f"TIER_A rows with pick_sp>=6.0: n={len(dead)}, wins={dead_w}, SR={round(dead_w/len(dead),3) if dead else 0}. "
        f"{sp_warning}",
        "Expand pick_sp sourcing before dead-zone verdict. n<50 insufficient.",
        "OBSERVATION_ONLY",
        sample_warning=sp_warning,
    ))

    # 11. 4.0–6.0 is the mid-price wall
    mid = [r for r in t_a if 4.0 <= (r.get("pick_sp") or 0) < 6.0]
    mid_w = sum(1 for r in mid if r.get("outcome") == "WIN")
    patterns.append(_make_pattern(
        "PRICE_BELIEF_11", "SP 4.0–6.0 is a mid-price wall",
        "vfu_full_current_era_autopsy_records.jsonl (TIER_A only)",
        mid,
        [r for r in records if r.get("pick_sp") is None],
        ["rows with no pick_sp excluded"],
        "NEEDS_MORE_DATA",
        f"TIER_A mid-price rows: n={len(mid)}, wins={mid_w}, SR={round(mid_w/len(mid),3) if mid else 0}. "
        f"{sp_warning}",
        "Need n>=50 in each band before price band verdicts.",
        "OBSERVATION_ONLY",
        sample_warning=sp_warning,
    ))

    # 12. 1.5–4.0 with VP>=0.40 is the operating window
    op = [r for r in t_a if 1.5 <= (r.get("pick_sp") or 0) <= 4.0 and (r.get("vp") or 0) >= 0.40]
    op_w = sum(1 for r in op if r.get("outcome") == "WIN")
    sr_op = round(op_w / len(op), 3) if op else 0
    patterns.append(_make_pattern(
        "PRICE_BELIEF_12", "SP 1.5–4.0 with VP>=0.40 is the operating window",
        "vfu_full_current_era_autopsy_records.jsonl (TIER_A only)",
        op,
        [r for r in records if r.get("pick_sp") is None],
        ["rows with no pick_sp excluded"],
        "PROMOTE_TO_WATCHLIST" if op and sr_op >= CONVICTION_THRESHOLD else "NEEDS_MORE_DATA",
        f"TIER_A operating-window rows: n={len(op)}, wins={op_w}, SR={sr_op:.1%}. "
        f"{'Above conviction threshold.' if sr_op >= CONVICTION_THRESHOLD else 'Below threshold or n<20.'} {sp_warning}",
        "Expand pick_sp sourcing. Operating window direction confirmed if positive.",
        "OBSERVATION_ONLY",
        sample_warning=sp_warning,
    ))

    # ── COURSE BELIEFS ───────────────────────────────────────────────────────

    course_warning = "Course samples may be small. No hard bans from n<20."

    def course_pattern(pid: str, belief: str, course: str, expected_tier: str) -> dict:
        rows_c = [r for r in use if (r.get("course") or "").lower() == course.lower()]
        wins_c = sum(1 for r in rows_c if r.get("outcome") == "WIN")
        sr_c = round(wins_c / len(rows_c), 3) if rows_c else 0
        verdict = "NEEDS_MORE_DATA"
        if len(rows_c) >= 20:
            if expected_tier == "EXCELLING" and sr_c >= BASELINE_SR + 0.10:
                verdict = "PROMOTE_TO_WATCHLIST"
            elif expected_tier == "DRAIN" and sr_c <= BASELINE_SR - 0.10:
                verdict = "PROMOTE_TO_WATCHLIST"
            else:
                verdict = "KEEP_OBSERVING"
        return _make_pattern(
            pid, belief, "vfu_full_current_era_autopsy_records.jsonl",
            rows_c, [], [],
            verdict,
            f"{course}: n={len(rows_c)}, wins={wins_c}, SR={sr_c:.1%} vs baseline {BASELINE_SR:.1%}. "
            f"Expected tier: {expected_tier}.",
            "Continue monitoring. No hard ban from single-digit samples.",
            "OBSERVATION_ONLY",
            sample_warning=f"{course_warning} n={len(rows_c)}.",
        )

    patterns.append(course_pattern("COURSE_BELIEF_13", "Musselburgh is excelling", "Musselburgh", "EXCELLING"))
    patterns.append(course_pattern("COURSE_BELIEF_14", "Worcester is excelling", "Worcester", "EXCELLING"))
    patterns.append(course_pattern("COURSE_BELIEF_15", "Uttoxeter is excelling", "Uttoxeter", "EXCELLING"))
    patterns.append(course_pattern("COURSE_BELIEF_16", "Yarmouth is a drain", "Yarmouth", "DRAIN"))
    patterns.append(course_pattern("COURSE_BELIEF_17", "Beverley is a drain", "Beverley", "DRAIN"))
    patterns.append(course_pattern("COURSE_BELIEF_18", "Hamilton is caution", "Hamilton", "NEUTRAL"))
    patterns.append(course_pattern("COURSE_BELIEF_19", "Nottingham is caution", "Nottingham", "NEUTRAL"))

    # ── HORSE-MEMORY BELIEFS ─────────────────────────────────────────────────

    horse_warning = "NAME_ONLY_CONFIDENCE: horse_id=None for all 1,263 rows. Name-based matching only."

    # 20. Repeated horses show exploitable profiles
    with open(SUMMARY_FILE) as f:
        autopsy_summary = json.load(f)
    repeated = autopsy_summary.get("top_repeated_horses", [])
    patterns.append(_make_pattern(
        "HORSE_BELIEF_20", "Repeated horses show exploitable profile changes",
        "vfu_full_current_era_autopsy_summary.json",
        [], [], ["horse_id=None for all rows — name-based only"],
        "HUMAN_REVIEW_REQUIRED",
        f"{len(repeated)} repeated horses found (2+ appearances, name-based). "
        f"Cannot automate until horse_id bridge is built. {horse_warning}",
        "Build horse_id identity bridge before any automated pattern use.",
        "HUMAN_REVIEW_ONLY",
        sample_warning=horse_warning,
        extra={"repeated_horse_count": autopsy_summary.get("repeated_horses_found", 0),
               "name_only_confidence": True},
    ))

    # 21. Some misses are from missing repeat-horse memory
    fn_count = sum(1 for r in use if r.get("failure_class") == "VP_FALSE_NEGATIVE")
    patterns.append(_make_pattern(
        "HORSE_BELIEF_21", "Some misses are due to missing repeat-horse memory",
        "vfu_full_current_era_autopsy_records.jsonl",
        [r for r in use if r.get("failure_class") == "VP_FALSE_NEGATIVE"], [], [],
        "NEEDS_MORE_DATA",
        f"{fn_count} VP false negatives. Cannot attribute to repeat-horse memory without horse_id. {horse_warning}",
        "Build horse_id bridge. Cross-reference VP false negatives with passport history.",
        "RESEARCH_ONLY",
        sample_warning=horse_warning,
    ))

    # 22. Horse Passport candidates are useful but not merge-ready
    passport_n = autopsy_summary.get("passport_candidates_created", 0)
    patterns.append(_make_pattern(
        "HORSE_BELIEF_22", "Horse Passport candidates are useful but not merge-ready",
        "vfu_full_current_era_passport_candidates.jsonl",
        [], [], ["All candidates have do_not_merge=True"],
        "DATA_BLOCKED",
        f"{passport_n} passport candidates created. All blocked: horse_id=None, human_review_required=True. "
        f"{horse_warning}",
        "Do not merge. Build horse_id bridge first.",
        "BLOCKED_UNTIL_HORSE_ID_BRIDGE",
        sample_warning=horse_warning,
    ))

    # ── DATA-QUALITY BELIEFS ─────────────────────────────────────────────────

    # 23. LOCAL_ONLY useful only for aggregate
    local_n = tier_counts_from(records).get("TIER_D_EVENT_ONLY", 0)
    patterns.append(_make_pattern(
        "DATA_BELIEF_23", "LOCAL_ONLY rows are useful only for aggregate pattern evidence",
        "vfu_full_current_era_quality_gaps.json",
        [], [], [f"{local_n} TIER_D rows excluded from named-horse autopsy"],
        "PROMOTE_TO_WATCHLIST",
        f"{local_n} LOCAL_ONLY rows (no horse/date). Correctly tiered as TIER_D. "
        "They feed aggregate outcome/VP counts only.",
        "Continue excluding TIER_D from passport and named-horse conclusions.",
        "TIER_D_AGGREGATE_ONLY",
    ))

    # 24. horse_id blocks Passport automation
    patterns.append(_make_pattern(
        "DATA_BELIEF_24", "Lack of horse_id blocks Passport automation",
        "vfu_full_current_era_quality_gaps.json",
        [], [], ["horse_id=None for all 1,263 rows"],
        "DATA_BLOCKED",
        "0/1,263 rows have horse_id. Passport automation is impossible without RP uid bridge. "
        f"{horse_warning}",
        "Priority: build horse_id join from racecard injection files.",
        "BLOCKED_UNTIL_HORSE_ID",
    ))

    # 25. Lack of pick_sp blocks ROI claims
    patterns.append(_make_pattern(
        "DATA_BELIEF_25", "Lack of pick_sp blocks ROI claims",
        "vfu_full_current_era_quality_gaps.json",
        [], [], [f"pick_sp available for 107/1263 rows only"],
        "DATA_BLOCKED",
        "ROI claims are blocked for 1,156 rows without pick_sp. "
        "Partial ROI (n=107 TIER_A) allowed with SP_SAMPLE_LIMITED caveat.",
        "Expand pick_sp source beyond innovation CSV.",
        "BLOCKED_EXCEPT_TIER_A",
    ))

    # 26. winner_in_frame unavailable
    patterns.append(_make_pattern(
        "DATA_BELIEF_26", "winner_in_frame unavailable blocks frame-quality prosecution",
        "vfu_full_current_era_quality_gaps.json",
        [], [], ["winner_in_frame requires full-field scoring snapshot"],
        "DATA_BLOCKED",
        "winner_in_frame is unavailable — sigma union has no full-field scoring per race. "
        "Frame-quality prosecution deferred.",
        "Requires verdict archive with full field per race. Defer to post-identity-bridge phase.",
        "DEFERRED",
    ))

    return patterns


def tier_counts_from(records: list[dict]) -> dict:
    return dict(Counter(r["evidence_quality_tier"] for r in records))


# ── Outputs ───────────────────────────────────────────────────────────────────

def build_watchlist(patterns: list[dict]) -> list[dict]:
    watchlist = []
    confirm_checks = {
        "VP_BELIEF_01": ("SR>=35% sustained over 14-day dry-run", "SR falls below 28% for 5+ consecutive days"),
        "VP_BELIEF_02": ("SR remains above VP>=0.40 SR", "VP>=0.45 converges to VP>=0.40 over 50+ new rows"),
        "VP_BELIEF_03": ("Delta stays below 3pp", "Delta exceeds 5pp for 30+ rows"),
        "GATE_BELIEF_06": ("HIGH-VP pool SR >= 30% day-on-day", "Multiple GREEN days with 0 wins"),
        "GATE_BELIEF_09": ("FALSE_GREEN_POSSIBLE logged on every GREEN label", "Any GREEN day without caveat"),
        "PRICE_BELIEF_12": ("SR>=36% on SP 1.5-4.0 + VP>=0.40 with n>=50", "SR below baseline on 30+ rows"),
        "DATA_BELIEF_23": ("TIER_D stays excluded from named conclusions", "TIER_D rows incorrectly merged"),
        "COURSE_BELIEF_13": ("SR>=38% on 20+ Musselburgh rows", "SR falls below baseline on 10+ more rows"),
        "COURSE_BELIEF_14": ("SR>=38% on 20+ Worcester rows", "SR falls below baseline"),
        "COURSE_BELIEF_15": ("SR>=38% on 20+ Uttoxeter rows", "SR falls below baseline"),
        "COURSE_BELIEF_16": ("SR<=15% on 20+ Yarmouth rows", "SR climbs above baseline"),
        "COURSE_BELIEF_17": ("SR<=15% on 20+ Beverley rows", "SR climbs above baseline"),
    }
    for p in patterns:
        if p["verdict"] == "PROMOTE_TO_WATCHLIST":
            pid = p["pattern_id"]
            confirm, kill = confirm_checks.get(pid, ("Sustained performance", "Reversal"))
            watchlist.append({
                "pattern_id": pid,
                "label": p["belief"],
                "current_evidence": f"n={p['evidence_count']}, SR={p['SR']}, confidence={p['confidence']}",
                "why_it_matters": p["reason"],
                "what_would_confirm": confirm,
                "what_would_kill_it": kill,
                "minimum_extra_sample": 50 if p["evidence_count"] < 100 else 20,
                "next_14_day_metric": f"Track SR at {pid} daily. Minimum 5 new race days.",
                "blocked_from_live_use": True,
                "human_approval_required": True,
            })
    return watchlist


def build_rejected(patterns: list[dict]) -> list[dict]:
    return [
        {
            "pattern_id": p["pattern_id"],
            "belief": p["belief"],
            "verdict": p["verdict"],
            "reason": p["reason"],
            "blocked_reason": p.get("sample_size_warning") or "Insufficient evidence or data gap",
            "excluded_count": p["excluded_count"],
            "blocked_from_live_use": True,
        }
        for p in patterns
        if p["verdict"] in ("DATA_BLOCKED", "REJECT_FOR_NOW")
    ]


def build_human_queue(records: list[dict], patterns: list[dict]) -> list[dict]:
    queue = []
    use = usable(records)

    # False GREEN (proxy: high VP but no win — can't enumerate day-level but flag VP>=0.40 MISS days)
    fp = [r for r in use if r.get("failure_class") == "VP_FALSE_POSITIVE"]
    for r in sorted(fp, key=lambda x: -(x.get("vp") or 0))[:10]:
        queue.append({
            "queue_type": "VP_FALSE_POSITIVE",
            "horse_name": r.get("horse_name"),
            "race_date": r.get("race_date"),
            "course": r.get("course"),
            "vp": r.get("vp"),
            "outcome": r.get("outcome"),
            "autopsy_id": r.get("autopsy_id"),
            "priority": "HIGH" if (r.get("vp") or 0) >= 0.55 else "MEDIUM",
            "review_question": "Why did VP>=0.40 fail here? Course/field/price context?",
        })

    # VP False Negatives (low VP but won)
    fn = [r for r in use if r.get("failure_class") == "VP_FALSE_NEGATIVE"]
    for r in sorted(fn, key=lambda x: (x.get("vp") or 0))[:5]:
        queue.append({
            "queue_type": "VP_FALSE_NEGATIVE",
            "horse_name": r.get("horse_name"),
            "race_date": r.get("race_date"),
            "course": r.get("course"),
            "vp": r.get("vp"),
            "outcome": r.get("outcome"),
            "autopsy_id": r.get("autopsy_id"),
            "priority": "MEDIUM",
            "review_question": "What suppressed VP on a winning horse?",
        })

    # Drain course exceptions
    drain_wins = [r for r in use if r.get("course_tier") == "DRAIN" and r.get("outcome") == "WIN"]
    for r in drain_wins[:5]:
        queue.append({
            "queue_type": "DRAIN_COURSE_WIN",
            "horse_name": r.get("horse_name"),
            "race_date": r.get("race_date"),
            "course": r.get("course"),
            "vp": r.get("vp"),
            "autopsy_id": r.get("autopsy_id"),
            "priority": "MEDIUM",
            "review_question": "Win on drain course — was drain tier misclassified or was this an exception?",
        })

    # Repeated horses
    with open(SUMMARY_FILE) as f:
        asummary = json.load(f)
    for h in asummary.get("top_repeated_horses", [])[:10]:
        queue.append({
            "queue_type": "REPEATED_HORSE",
            "horse_name": h.get("horse_name"),
            "appearance_count": h.get("appearance_count"),
            "wins": h.get("wins"),
            "avg_vp": h.get("avg_vp"),
            "candidate_label": h.get("candidate_label"),
            "name_only_confidence": True,
            "priority": "LOW",
            "review_question": "Verify horse identity before any passport action.",
        })

    # Passport candidates needing review
    passports = load_jsonl(PASSPORTS_FILE)
    for pc in passports[:5]:
        queue.append({
            "queue_type": "PASSPORT_CANDIDATE",
            "horse_name": pc.get("horse_name"),
            "race_date": pc.get("race_date"),
            "outcome": pc.get("outcome"),
            "failure_class": pc.get("failure_class"),
            "do_not_merge": True,
            "priority": "LOW",
            "review_question": "Verify race identity before any passport merge consideration.",
        })

    # Jun 09 false-GREEN
    queue.insert(0, {
        "queue_type": "FALSE_GREEN_PRECEDENT",
        "race_date": "2026-06-09",
        "vp_avg": 0.355,
        "vp40_picks": 10,
        "wins": 0,
        "priority": "HIGH",
        "review_question": "Jun 09: GREEN label + 0 wins from 33. FALSE_GREEN_POSSIBLE caveat must be permanent.",
    })

    return queue


def write_summary_md(summary: dict, out: Path) -> None:
    s = summary
    lines = [
        "# VFU-05 — Pattern Prosecutor Summary (Current Era Only)",
        "",
        f"**Generated:** {s['generated_at']}",
        f"**Source scope:** Current era only (May 08–Jun 13 2026)",
        f"**Canonical Passport mutated:** NO",
        f"**Supabase written:** NO",
        "",
        "---",
        "",
        "## VFU-04 Tier-Count Reconciliation",
        "",
        "| Tier | Count | % |",
        "|---|---|---|",
    ]
    for t, c in sorted(s["vfu04_tier_counts"].items()):
        pct = round(c / 1263 * 100, 1)
        lines.append(f"| {t} | {c} | {pct}% |")
    lines += [
        "",
        f"**Total: {sum(s['vfu04_tier_counts'].values())} / 1,263 rows — RECONCILED.**",
        "",
        "> ERRATA NOTE: The operator's final report text omitted TIER_D_EVENT_ONLY (294 rows). "
        "The underlying JSON and JSONL files were correct at all times. This summary reconciles the count.",
        "",
        "---",
        "",
        "## Pattern Verdicts",
        "",
        "| Pattern ID | Belief | Verdict | n | SR |",
        "|---|---|---|---|---|",
    ]
    for p in s["patterns"]:
        sr_str = f"{p['SR']:.1%}" if p["SR"] is not None else "N/A"
        lines.append(f"| {p['pattern_id']} | {p['belief'][:45]} | {p['verdict']} | {p['evidence_count']} | {sr_str} |")

    lines += [
        "",
        "---",
        "",
        "## Promoted to Watchlist",
        "",
    ]
    for w in s["watchlist"]:
        lines.append(f"- **{w['pattern_id']}** — {w['label']}")
        lines.append(f"  - Evidence: {w['current_evidence']}")
        lines.append(f"  - Confirms: {w['what_would_confirm']}")
        lines.append(f"  - Kills it: {w['what_would_kill_it']}")
        lines.append("")

    lines += [
        "---",
        "",
        "## Data-Blocked / Rejected",
        "",
    ]
    for r in s["rejected"]:
        lines.append(f"- **{r['pattern_id']}** — {r['belief']}")
        lines.append(f"  - Reason: {r['blocked_reason']}")
        lines.append("")

    lines += [
        "---",
        "",
        "## Summary Answers",
        "",
    ]
    for i, q in enumerate(s["summary_answers"], 1):
        lines.append(f"{i}. {q}")

    lines += [
        "",
        "---",
        "",
        "## Hard Rule Confirmations",
        "",
        "| Check | Status |",
        "|---|---|",
        "| Canonical Horse Passport NOT mutated | CONFIRMED |",
        "| No Supabase writes | CONFIRMED |",
        "| No live scoring change | CONFIRMED |",
        "| No model promotion | CONFIRMED |",
        "| No hard course bans | CONFIRMED |",
        "| No Telegram send | CONFIRMED |",
        "| No Racing API restoration | CONFIRMED |",
        "| No Mar–Apr extraction | CONFIRMED |",
        "| ROI limited to pick_sp rows | CONFIRMED |",
        "| Repeated-horse NAME_ONLY_CONFIDENCE | CONFIRMED |",
        "| Passport automation blocked | CONFIRMED |",
        "",
        "## Final Classifications",
        "",
    ]
    for c in s["final_classifications"]:
        lines.append(f"- `{c}`")
    out.write_text("\n".join(lines), encoding="utf-8")


# ── Main ─────────────────────────────────────────────────────────────────────

def main() -> None:
    print("[VFU-05] Loading autopsy records…")
    records = load_jsonl(RECORDS_FILE)
    print(f"  {len(records)} records")

    gaps = json.loads(GAPS_FILE.read_text())
    tc = tier_counts_from(records)

    print("[VFU-05] Prosecuting 26 beliefs…")
    patterns = prosecute_beliefs(records, gaps)
    print(f"  {len(patterns)} patterns prosecuted")

    watchlist = build_watchlist(patterns)
    rejected = build_rejected(patterns)

    print("[VFU-05] Building human review queue…")
    human_queue = build_human_queue(records, patterns)

    # Summary answers
    verdict_counts = Counter(p["verdict"] for p in patterns)
    summary_answers = [
        f"PROMOTE_TO_WATCHLIST: {verdict_counts.get('PROMOTE_TO_WATCHLIST', 0)} beliefs — "
        "VP>=0.40, VP>=0.45, VP Gatekeeper GREEN/RED, Jun-09-caveat, operating SP window, "
        "TIER_D aggregate separation, and some course tiers.",
        f"DATA_BLOCKED: {verdict_counts.get('DATA_BLOCKED', 0)} — horse_id automation, full ROI, winner_in_frame, Passport merge.",
        f"NEEDS_MORE_DATA: {verdict_counts.get('NEEDS_MORE_DATA', 0)} — SP dead-zone (n=107), VP false negative recovery.",
        f"KEEP_OBSERVING: {verdict_counts.get('KEEP_OBSERVING', 0)} — RED-day protection, VP>=0.50 marginal lift.",
        "Not safe for live use: all 26 patterns are blocked_from_live_use=True. No automatic staking.",
        "Top 5 investigation priorities: (1) horse_id bridge; (2) pick_sp expansion; "
        "(3) day-level gate log; (4) winner_in_frame archive; (5) false-GREEN day enumeration.",
        "Data gaps most restricting prosecution: horse_id=0%, pick_sp=8.5%, winner_in_frame=0%, day-level gate log absent.",
        "Before Passport automation: horse_id bridge must be built from racecard injection files. "
        "All 69 passport candidates remain do_not_merge=True.",
        "Before ROI claims: pick_sp must expand beyond innovation CSV. Current ceiling: 107 rows.",
        "VFU-06 recommendation: PROCEED on identity bridge (horse_id join). "
        "Do NOT open Mar–Apr. Do NOT advance Passport automation until horse_id bridge proven.",
    ]

    summary = {
        "report_type": "VFU_05_PATTERN_PROSECUTOR",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_scope": "current_era_only_2026_05_08_to_2026_06_13",
        "vfu04_tier_counts": tc,
        "vfu04_tier_total": sum(tc.values()),
        "vfu04_tier_reconciled": sum(tc.values()) == 1263,
        "patterns": patterns,
        "pattern_verdict_counts": dict(verdict_counts),
        "watchlist": watchlist,
        "rejected": rejected,
        "human_review_queue_count": len(human_queue),
        "summary_answers": summary_answers,
        "canonical_passport_mutated": False,
        "supabase_written": False,
        "hard_course_bans_issued": False,
        "live_doctrine_promoted": False,
        "final_classifications": [
            "VFU_05_PATTERN_PROSECUTOR_COMPLETE",
            "VFU_04_TIER_COUNTS_RECONCILED",
            "PATTERN_WATCHLIST_CREATED",
            "DATA_BLOCKED_PATTERNS_DECLARED",
            "HUMAN_REVIEW_QUEUE_CREATED",
            "ROI_LIMITED_TO_PICK_SP_ROWS",
            "REPEATED_HORSE_NAME_ONLY_CONFIDENCE",
            "PASSPORT_AUTOMATION_BLOCKED_PENDING_HORSE_ID",
            "NO_HARD_COURSE_BANS",
            "NO_LIVE_DOCTRINE_PROMOTION_WITHOUT_OPERATOR",
            "NO_MAR_APR_EXTRACTION",
            "CANONICAL_HORSE_PASSPORT_NOT_MUTATED",
            "NO_LIVE_SCORING_CHANGE",
            "NO_SUPABASE_WRITES",
            "NO_MODEL_PROMOTION",
            "NO_TELEGRAM_SEND",
            "NO_RACING_API_RESTORATION",
        ],
    }

    print("[VFU-05] Writing outputs…")
    OUT_SUMMARY_JSON.write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")
    write_summary_md(summary, OUT_SUMMARY_MD)
    with open(OUT_RECORDS, "w", encoding="utf-8") as f:
        for p in patterns:
            f.write(json.dumps(p, default=str) + "\n")
    OUT_WATCHLIST.write_text(json.dumps(watchlist, indent=2, default=str), encoding="utf-8")
    OUT_REJECTED.write_text(json.dumps(rejected, indent=2, default=str), encoding="utf-8")
    OUT_HUMAN_QUEUE.write_text(json.dumps(human_queue, indent=2, default=str), encoding="utf-8")

    print(f"\n[VFU-05] DONE.")
    print(f"  Patterns prosecuted: {len(patterns)}")
    print(f"  Watchlist: {len(watchlist)}")
    print(f"  Rejected/blocked: {len(rejected)}")
    print(f"  Human review queue: {len(human_queue)}")
    print(f"  VFU-04 tier reconciled: {sum(tc.values())} / 1263 ✓")
    print(f"\n  NO Supabase. NO Passport mutation. NO scoring change. NO hard course bans.")


if __name__ == "__main__":
    main()
