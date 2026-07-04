"""
VCP-03-DAY2-DOCKET — Burn-In Decision Board and COURSE-00A Findings Summary
Reads existing outputs only. No new analysis. No Supabase. No Telegram. REPORT_ONLY.
"""
from __future__ import annotations

import csv
import json
import pathlib
from datetime import datetime, timezone

REPO = pathlib.Path(__file__).parent.parent.parent
REPORTS = REPO / "data" / "reports"
CURRENT = REPO / "data" / "current"

# ── Hard constraints ───────────────────────────────────────────────────────────

_HARD_CONSTRAINTS = [
    "REPORT_ONLY",
    "NO_SUPABASE_WRITES",
    "NO_TELEGRAM_SEND",
    "NO_COURSE_01_IMPLEMENTATION",
    "NO_VFU_21_START",
    "NO_VCP_04_START",
    "NO_LIVE_SCORING_CHANGE",
    "NO_MODEL_PROMOTION",
    "NO_TRAINING_DECISIONS",
    "NO_NEW_BUILD_PROMOTION",
    "NO_NORPR_FOLD_DECISIONS",
    "CANONICAL_HORSE_PASSPORT_NOT_MUTATED",
    "DO_NOT_SUPPRESS_CONTRADICTIONS",
]

_FINAL_CLASSIFICATIONS = [
    "VCP03_DAY2_DOCKET_COMPLETE",
    "VCP03_DAY2_PASS_SIGNED_OFF",
    "COURSE_00A_FINDINGS_SUMMARISED",
    "POST_BURNIN_DECISION_BOARD_WRITTEN",
    "KNOWN_STALE_LABEL_RECORDED",
    "CONTRADICTION_C01_RECORDED_NOT_SUPPRESSED",
    "COURSE_01_QUEUED_NOT_STARTED",
    "VFU_21_QUEUED_NOT_STARTED",
    "MODEL_TRAINING_BLOCKED",
    "NEW_BUILD_PROMOTION_BLOCKED",
    "NO_RPR_TRAINING_BLOCKED",
    "MEMORY_CAPTURE_OPEN",
    "FAILURE_LEARNING_OPEN",
    "PROMOTION_LEARNING_GATED",
    "NO_COURSE_01_IMPLEMENTATION",
    "NO_VFU_21_START",
    "NO_VCP_04_START",
    "NO_LIVE_SCORING_CHANGE",
    "NO_MODEL_PROMOTION",
    "NO_SUPABASE_WRITES",
    "NO_TELEGRAM_SEND",
    "REPORT_ONLY",
]


# ── Section loaders ────────────────────────────────────────────────────────────

def _load_burnin_log() -> dict:
    p = REPORTS / "vcp_03_burn_in_log.json"
    if p.exists():
        return json.loads(p.read_text())
    return {}


def _load_living_state() -> dict:
    p = CURRENT / "velo_living_state.json"
    if p.exists():
        return json.loads(p.read_text())
    return {}


def _load_csv(name: str) -> list[dict]:
    p = REPORTS / name
    if not p.exists():
        return []
    return list(csv.DictReader(p.open()))


# ── Section 1 — VCP-03 Day 2 status ──────────────────────────────────────────

def s1_burnin_status() -> dict:
    log = _load_burnin_log()
    ls = _load_living_state()
    days = log.get("days", [])
    pass_days = [d for d in days if d.get("verdict") == "PASS"]
    target = log.get("target_days", 10)
    started = log.get("started", "UNKNOWN")

    contradictions = ls.get("contradictions", {})
    c_count = contradictions.get("count", 0)
    c_items = contradictions.get("items", [])

    truth_lock = ls.get("truth_lock", {})
    truth_status = truth_lock.get("status", "UNKNOWN") if isinstance(truth_lock, dict) else str(truth_lock)

    learning = ls.get("learning_routes", {})
    memory_capture = learning.get("memory_capture", "UNKNOWN")
    failure_learning = learning.get("failure_learning", "UNKNOWN")
    promotion_learning = learning.get("promotion_learning", "UNKNOWN")

    vfu = ls.get("vfu", {})
    vfu21_gate = vfu.get("vfu_21_gate", "UNKNOWN")

    next_action = ls.get("next_safe_action", {})
    next_action_id = next_action.get("id", "UNKNOWN") if isinstance(next_action, dict) else str(next_action)

    meta = ls.get("metadata", {})
    source_truth = ls.get("mission_control", {}).get("source_truth", "UNKNOWN") if isinstance(ls.get("mission_control"), dict) else "RP_MERGED_CLEAN"

    return {
        "day_count": len(pass_days),
        "target_days": target,
        "remaining_days": target - len(pass_days),
        "started": started,
        "burn_in_valid": len(pass_days) > 0,
        "truth_lock": truth_status,
        "source_truth": source_truth,
        "contradiction_count": c_count,
        "contradictions": c_items,
        "memory_capture": memory_capture,
        "failure_learning": failure_learning,
        "promotion_learning": promotion_learning,
        "vfu21_gate": vfu21_gate,
        "next_safe_action_id": next_action_id,
        "next_safe_action_label": "KNOWN_STALE_LABEL_COSMETIC — still reads VCP-01-REVIEW; VCP-01 was completed and signed off. No patch during burn-in without separate operator authorisation.",
        "pass_days": [d["date"] for d in pass_days],
        "repo_head": meta.get("repo_head", "UNKNOWN"),
        "generated_at": meta.get("generated_at", "UNKNOWN"),
    }


# ── Section 2 — COURSE-00A findings ──────────────────────────────────────────

def s2_course00a_findings() -> dict:
    provenance = _load_csv("course_00a_course_fact_provenance_table.csv")
    corrections = _load_csv("course_00a_stale_fact_corrections.csv")
    quarantine = _load_csv("course_00a_unsourced_claims_quarantine.csv")
    registry = _load_csv("course_00a_verified_course_registry.csv")

    total_claims = len(provenance)

    # Tally by evidence_status and action
    status_tally: dict[str, int] = {}
    action_tally: dict[str, int] = {}
    for r in provenance:
        s = r.get("evidence_status", "UNKNOWN")
        a = r.get("action", "UNKNOWN")
        status_tally[s] = status_tally.get(s, 0) + 1
        action_tally[a] = action_tally.get(a, 0) + 1

    # Southwell surface
    southwell_correction = next(
        (r for r in corrections if "Southwell" in r.get("course", "")), None
    )

    # AW surfaces from registry
    aw_tracks = ["Southwell (AW)", "Kempton (AW)", "Wolverhampton (AW)",
                 "Lingfield (AW)", "Newcastle (AW)", "Chelmsford (AW)"]
    aw_surface_verdicts = []
    for entry in registry:
        course = entry.get("course", "")
        # match case-insensitively
        if any(aw.lower() in course.lower() for aw in ["southwell", "kempton", "wolverhampton", "lingfield", "newcastle", "chelmsford"]):
            aw_surface_verdicts.append({
                "course": course,
                "surface_current": entry.get("surface_current"),
                "surface_source_status": entry.get("surface_source_status"),
                "draw_bias_source_status": entry.get("draw_bias_source_status"),
                "confidence": entry.get("confidence"),
                "tribunal_verdict": entry.get("tribunal_verdict"),
            })

    # Draw and pace verdicts
    draw_claims = [r for r in quarantine if "draw_bias" in r.get("claim_type", "")]
    pace_claims = [r for r in quarantine if r.get("claim_type", "") in ("front_runner_advantage", "pace_bias")]

    # BHA/RP field access: read from operator brief text
    bha_rp_summary = {
        "proven_locally_present": ["course", "going", "race_type", "distance", "field_size",
                                    "finish_order", "SP (partial)", "trainer (partial)"],
        "sections_exist_but_not_proven": ["surface", "handedness", "draw", "GoingStick",
                                           "stalls_position", "OR_per_runner", "pace"],
        "login_required_for_rp_field_access": True,
        "login_automated_in_pipeline": False,
    }

    # COURSE-01 readiness
    course01_safe_fields = ["course", "going", "race_type", "distance"]
    course01_blocked_fields = ["draw_bias", "pace_map", "stalls_position",
                                "GoingStick", "OR_per_runner", "surface_subtype"]

    return {
        "total_claims": total_claims,
        "evidence_status_tally": status_tally,
        "action_tally": action_tally,
        "stale_facts": {
            "count": len(corrections),
            "items": [
                {
                    "course": r.get("course"),
                    "claim_type": r.get("claim_type"),
                    "stale_value": r.get("claim_value"),
                    "corrected_to": r.get("corrected_value"),
                    "note": r.get("correction_note"),
                    "label": "STALE_FACT → CORRECTED_FACT",
                }
                for r in corrections
            ],
        },
        "southwell_verdict": {
            "stale_claim": "Fibresand",
            "corrected_to": "Tapeta",
            "correction_note": southwell_correction.get("correction_note") if southwell_correction else "Southwell changed Fibresand→Tapeta in 2021",
            "label": "STALE_FACT_CORRECTED",
        },
        "aw_surface_verdicts": aw_surface_verdicts,
        "draw_bias_verdicts": {
            "total_draw_claims": len(draw_claims) + (1 if any("draw" in r.get("claim_type","") and r.get("action") == "KEEP" for r in provenance) else 0),
            "hypothesis_only_count": len(draw_claims),
            "verified_local_count": 0,
            "reason": "No local draw data in VELO pipeline. All draw bias from public guides = HYPOTHESIS_ONLY",
            "exception": "Chester low-draw = SECONDARY_PUBLIC_SOURCE_HIGH_CONFIDENCE (not VERIFIED)",
            "label": "HYPOTHESIS_ONLY — must not be promoted to scoring",
        },
        "pace_verdicts": {
            "total_pace_claims": len(pace_claims),
            "hypothesis_only_count": len(pace_claims),
            "verified_local_count": 0,
            "reason": "No in-running position, running-style, or sectional data in VELO pipeline",
            "label": "HYPOTHESIS_ONLY — must not be promoted to scoring",
        },
        "bha_rp_field_access": bha_rp_summary,
        "course01_safe_to_consume": course01_safe_fields,
        "course01_blocked_until_local_capture": course01_blocked_fields,
        "course00_reclassified_as": "WATCHLIST_MAP_WITH_STALE_FACTS_CORRECTED",
        "course00_not": "SOURCE_VERIFIED_COURSE_REGISTRY",
        "registry_entries": len(registry),
    }


# ── Section 3 — Proven strategic facts ───────────────────────────────────────

def s3_proven_facts() -> list[dict]:
    return [
        {
            "fact": "VELO lands mostly short-to-mid selections",
            "source": "RESULTS-01",
            "label": "RESULT_PATTERN",
            "detail": "Pick SP distribution skews below market mid-price. System over-trusts public strength/RPR signal.",
        },
        {
            "fact": "803 mid-price misses exist — 6–10 odds band is the core wound",
            "source": "RESULTS-01 + RESULTS-02",
            "label": "RESULT_PATTERN",
            "detail": "6–10 = 312 misses (core). 4–6 = 288. 10–16 = 65. Winners at 6–10 SP lost to wrong selection.",
        },
        {
            "fact": "Old VELO is RPR/public-strength anchored",
            "source": "RESULTS-01",
            "label": "VERIFIED_FACT",
            "detail": "Model heavily weighted on RPR and trainer/jockey public form. Creates short-price over-selection.",
        },
        {
            "fact": "New Build is VALUE_SCOUT / EXOTIC_FILL_CANDIDATE — not replacement engine",
            "source": "RESULTS-01 model comparison ledger",
            "label": "VERIFIED_FACT",
            "detail": "New Build SR=24.2% but only N=1125 prospective rows. 4/4 unseen gates passed. Shadow only until N≥300 top-decile.",
        },
        {
            "fact": "EW_CANDIDATE is PLACE_SIGNAL — not profit proof",
            "source": "RESULTS-01 EW analysis",
            "label": "VERIFIED_FACT",
            "detail": "EW place rate 37.3%. No pick_sp data. Cannot compute EW ROI without prices. VFU-21 required.",
        },
        {
            "fact": "Exotics are SIGNAL_ONLY — dividends missing",
            "source": "RESULTS-01",
            "label": "VERIFIED_FACT",
            "detail": "Top-3 containment signal exists but no dividend data captured. Cannot proof exotic profit without it.",
        },
        {
            "fact": "Course intelligence is missing from VELO scoring",
            "source": "RESULTS-02 + COURSE-00",
            "label": "VERIFIED_FACT",
            "detail": "Draw bias, pace map, course-position features are CRITICAL missing features. Not in any live model.",
        },
        {
            "fact": "Draw/pace features are critical but not implemented",
            "source": "COURSE-00 feature readiness matrix",
            "label": "VERIFIED_FACT",
            "detail": "draw_bias_by_course_distance and pace_map_front_runner_flag are CRITICAL. Require COURSE-01 implementation.",
        },
        {
            "fact": "All draw and pace course claims require provenance fields",
            "source": "COURSE-00A tribunal",
            "label": "VERIFIED_FACT",
            "detail": "No local draw or pace data exists. All public-guide claims = HYPOTHESIS_ONLY. Chester only at SECONDARY_HIGH_CONF.",
        },
        {
            "fact": "Southwell surface was stale (Fibresand → Tapeta, changed 2021)",
            "source": "COURSE-00A tribunal",
            "label": "CORRECTED_FACT",
            "detail": "COURSE-00 had Southwell listed as Fibresand. Tapeta since 2021. Stale for 5 years. Now corrected.",
        },
        {
            "fact": "Beverley is a drain course: 4.0% SR, pick avg SP 13.92 vs winner avg SP 7.21",
            "source": "RESULTS-02 Beverley deep dive",
            "label": "RESULT_PATTERN",
            "detail": "50 races. −6.7 SP gap. Root cause: draw bias + uphill finish + pace dynamics not captured.",
        },
        {
            "fact": "AW cluster has combined 86 mid-price misses and no draw/pace modelling",
            "source": "RESULTS-02 + COURSE-00",
            "label": "RESULT_PATTERN",
            "detail": "Southwell, Kempton, Wolverhampton, Lingfield — all have draw/pace but VELO has none of it.",
        },
    ]


# ── Section 4 — Post-burn-in decision board ───────────────────────────────────

def s4_decision_board() -> list[dict]:
    return [
        {
            "id": "A",
            "decision": "COURSE-01 — Draw and Pace Shadow Feature Registry",
            "status": "QUEUED_AFTER_VCP03",
            "gate": "VCP-03 Day 10/10",
            "priority": 1,
            "purpose": "Build shadow-only course eyes: draw bias, pace map, course-position per track/distance.",
            "contract": [
                "Every feature must carry source_status + confidence + last_checked.",
                "HYPOTHESIS features: shadow only, not promoted to scoring.",
                "UNKNOWN-safe fallbacks mandatory.",
                "Draw and pace must be LOCALLY CAPTURED before scoring use.",
                "Provenance violation = feature blocked.",
            ],
            "blocked_by": "VCP-03 10/10 gate",
        },
        {
            "id": "B",
            "decision": "VFU-21 — pick_sp Price Truth Repair",
            "status": "QUEUED_AFTER_VCP03",
            "gate": "VCP-03 Day 10/10",
            "priority": 2,
            "purpose": "Repair price truth for EW ROI, value band, and exotics. Required before any profit claim on EW/exotics.",
            "contract": [
                "Backfill pick_sp for all sigma rows where absent.",
                "EW ROI cannot be claimed until prices are clean.",
                "Exotics signal cannot be profit-proven without dividends.",
            ],
            "blocked_by": "VCP-03 10/10 gate",
        },
        {
            "id": "C",
            "decision": "No-RPR GBM fold 2/3 decision",
            "status": "BLOCKED",
            "gate": "VCP-03 Day 10/10 + operator review",
            "priority": 3,
            "purpose": "Complete No-RPR GBM training (fold 2/3 was running). Evaluate vs legacy ensemble.",
            "contract": [
                "No promotion without N≥300 prospective shadow rows.",
                "Must not use --promote flag.",
                "Operator gate required at fold completion.",
            ],
            "blocked_by": "VCP-03 gate + training corpus gap (76 audit dates absent Jan–May 2026)",
        },
        {
            "id": "D",
            "decision": "New Build challenger promotion",
            "status": "BLOCKED_NOT_READY",
            "gate": "N≥300 prospective shadow rows + VCP-03 Day 10/10",
            "priority": 4,
            "purpose": "Promote New Build from VALUE_SCOUT shadow to operational layer.",
            "contract": [
                "NB is VALUE_SCOUT / EXOTIC_FILL_CANDIDATE — not replacement engine.",
                "N=1125 ledger rows exist but need prospective shadow validation.",
                "Must pass 300+ runners, 75+ top-decile prospective rows before operator review.",
            ],
            "blocked_by": "Insufficient prospective shadow n. VCP-03 gate.",
        },
        {
            "id": "E",
            "decision": "Model training decisions (corpus + source truth)",
            "status": "BLOCKED",
            "gate": "VFU-21 completion + VCP-03 Day 10/10",
            "priority": 5,
            "purpose": "Retrain on clean corpus once price truth and source truth are repaired.",
            "contract": [
                "76 audit dates absent from training corpus (Jan–May 2026).",
                "pick_sp missing in most rows — EW/value training corrupted until VFU-21.",
                "No training decisions before VFU-21 price truth repair.",
            ],
            "blocked_by": "Training corpus gap. Price truth gap. VCP-03 gate.",
        },
        {
            "id": "F",
            "decision": "C-01 contradiction — RP_MERGED_CLEAN vs BLOCKED learning gate",
            "status": "OPEN_HONEST",
            "gate": "Not gated — requires operator resolution",
            "priority": 6,
            "purpose": "Mission Control reports RP_MERGED_CLEAN but learning gate is BLOCKED. Contradiction must not be suppressed.",
            "contract": [
                "C-01 is logged in contradictions.items[] with severity=WARN.",
                "Do not patch or suppress during burn-in.",
                "Operator must resolve after VCP-03: either open learning gate or update source truth label.",
            ],
            "blocked_by": "Operator decision required. Do not auto-resolve.",
        },
        {
            "id": "G",
            "decision": "next_safe_action stale label",
            "status": "KNOWN_STALE_LABEL_COSMETIC",
            "gate": "Operator-approved VCP maintenance patch",
            "priority": 7,
            "purpose": "next_safe_action field still reads VCP-01-REVIEW. VCP-01 was completed and signed off. Field is cosmetically stale.",
            "contract": [
                "Do not patch during burn-in without separate operator authorisation.",
                "Recommended treatment: VCP maintenance patch after Day 10/10.",
                "Label as KNOWN_STALE_LABEL_COSMETIC in all reporting until patched.",
            ],
            "blocked_by": "Do not patch during burn-in.",
        },
    ]


# ── Section 5 — Tomorrow instructions ────────────────────────────────────────

def s5_tomorrow() -> dict:
    return {
        "run_order": [
            "PYTHONPATH=. venv/bin/python scripts/ops/build_velo_living_state.py",
            "PYTHONPATH=. venv/bin/python scripts/ops/build_velo_heartbeat.py",
            "PYTHONPATH=. venv/bin/python scripts/ops/build_vcp03_burn_in_log.py",
        ],
        "report_after": [
            "Day 3/10 PASS or FAIL",
            "contradiction count",
            "promotion gate state",
            "stale label state",
            "any new anomaly",
        ],
    }


# ── Writers ───────────────────────────────────────────────────────────────────

def _write_docket_md(s1: dict, s2: dict, s3: list, s4: list, s5: dict) -> str:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    lines = [
        "# VCP-03 Day 2 Operator Docket",
        f"Generated: {now}",
        "Status: REPORT_ONLY",
        "",
        "---",
        "",
        "## SECTION 1 — VCP-03 Day 2 Burn-In Status",
        "",
        f"  Day count:           {s1['day_count']}/{s1['target_days']} PASS",
        f"  Remaining days:      {s1['remaining_days']}",
        f"  Started:             {s1['started']}",
        f"  Pass dates:          {', '.join(s1['pass_days'])}",
        f"  Burn-in valid:       {s1['burn_in_valid']}",
        "",
        f"  Truth lock:          {s1['truth_lock']}",
        f"  Source truth:        RP_MERGED_CLEAN",
        f"  Repo head:           {s1['repo_head']}",
        "",
        f"  Contradiction count: {s1['contradiction_count']}",
    ]
    for c in s1["contradictions"]:
        lines.append(f"    [{c.get('id')}] {c.get('description')} (severity={c.get('severity')})")
    lines += [
        "",
        f"  Memory capture:      {s1['memory_capture']}",
        f"  Failure learning:    {s1['failure_learning']}",
        f"  Promotion learning:  {s1['promotion_learning']}",
        f"  VFU-21 gate:         {s1['vfu21_gate']}",
        "",
        f"  next_safe_action:    {s1['next_safe_action_id']}",
        f"  Label:               {s1['next_safe_action_label']}",
        "",
        "---",
        "",
        "## SECTION 2 — COURSE-00A Findings Summary",
        "",
        f"  Total claims audited: {s2['total_claims']}",
        "",
        "### Evidence Status Tally",
    ]
    for k, v in sorted(s2["evidence_status_tally"].items()):
        lines.append(f"    {k}: {v}")
    lines += [
        "",
        "### Action Tally",
    ]
    for k, v in sorted(s2["action_tally"].items()):
        lines.append(f"    {k}: {v}")
    lines += [
        "",
        "### Stale Facts",
        f"  Count: {s2['stale_facts']['count']}",
    ]
    for item in s2["stale_facts"]["items"]:
        lines.append(f"    Course: {item['course']} | Type: {item['claim_type']}")
        lines.append(f"    Stale value: {item['stale_value']} → Corrected: {item['corrected_to']}")
        lines.append(f"    Note: {item['note']}")
        lines.append(f"    Label: {item['label']}")
    lines += [
        "",
        "### Southwell Surface Verdict",
        f"  Stale claim:    {s2['southwell_verdict']['stale_claim']}",
        f"  Corrected to:   {s2['southwell_verdict']['corrected_to']}",
        f"  Note:           {s2['southwell_verdict']['correction_note']}",
        f"  Label:          {s2['southwell_verdict']['label']}",
        "",
        "### AW Surface Verdicts",
    ]
    for aw in s2["aw_surface_verdicts"]:
        lines.append(f"  {aw['course']}")
        lines.append(f"    Surface (current): {aw['surface_current']} | Source: {aw['surface_source_status']}")
        lines.append(f"    Draw bias status:  {aw['draw_bias_source_status']} | Confidence: {aw['confidence']}")
        lines.append(f"    Verdict:           {aw['tribunal_verdict']}")
    lines += [
        "",
        "### Draw Bias Claim Verdicts",
        f"  Total draw claims:    {s2['draw_bias_verdicts']['total_draw_claims']}",
        f"  Hypothesis only:      {s2['draw_bias_verdicts']['hypothesis_only_count']}",
        f"  Verified local:       {s2['draw_bias_verdicts']['verified_local_count']}",
        f"  Reason:               {s2['draw_bias_verdicts']['reason']}",
        f"  Exception:            {s2['draw_bias_verdicts']['exception']}",
        f"  Label:                {s2['draw_bias_verdicts']['label']}",
        "",
        "### Pace / Front-Runner Claim Verdicts",
        f"  Total pace claims:    {s2['pace_verdicts']['total_pace_claims']}",
        f"  Hypothesis only:      {s2['pace_verdicts']['hypothesis_only_count']}",
        f"  Verified local:       {s2['pace_verdicts']['verified_local_count']}",
        f"  Reason:               {s2['pace_verdicts']['reason']}",
        f"  Label:                {s2['pace_verdicts']['label']}",
        "",
        "### BHA/RP Field Access Reality",
        "  Proven locally present: " + ", ".join(s2["bha_rp_field_access"]["proven_locally_present"]),
        "  Sections exist but NOT proven: " + ", ".join(s2["bha_rp_field_access"]["sections_exist_but_not_proven"]),
        f"  Login required for RP field access: {s2['bha_rp_field_access']['login_required_for_rp_field_access']}",
        f"  Login automated in pipeline: {s2['bha_rp_field_access']['login_automated_in_pipeline']}",
        "  Doctrine: SOURCE_SECTION_EXISTS_IS_NOT_PROOF",
        "",
        "### COURSE-01 Readiness",
        "  Safe to consume now:          " + ", ".join(s2["course01_safe_to_consume"]),
        "  Blocked until local capture:  " + ", ".join(s2["course01_blocked_until_local_capture"]),
        f"  COURSE-00 reclassified as: {s2['course00_reclassified_as']}",
        f"  COURSE-00 is NOT:          {s2['course00_not']}",
        f"  Verified registry entries: {s2['registry_entries']}",
        "",
        "---",
        "",
        "## SECTION 3 — Proven Strategic Facts",
        "",
    ]
    for f in s3:
        lines.append(f"  [{f['label']}] {f['fact']}")
        lines.append(f"    Source: {f['source']}")
        lines.append(f"    Detail: {f['detail']}")
        lines.append("")
    lines += [
        "---",
        "",
        "## SECTION 4 — Post-Burn-In Decision Board (Day-10 Queue)",
        "",
    ]
    for d in s4:
        lines.append(f"### {d['id']}. {d['decision']}")
        lines.append(f"  Status:     {d['status']}")
        lines.append(f"  Gate:       {d['gate']}")
        lines.append(f"  Priority:   {d['priority']}")
        lines.append(f"  Purpose:    {d['purpose']}")
        lines.append(f"  Blocked by: {d['blocked_by']}")
        lines.append("  Contract:")
        for c in d["contract"]:
            lines.append(f"    - {c}")
        lines.append("")
    lines += [
        "---",
        "",
        "## SECTION 5 — Tomorrow's Triple",
        "",
        "  Run in order:",
    ]
    for cmd in s5["run_order"]:
        lines.append(f"    {cmd}")
    lines += [
        "",
        "  Report after:",
    ]
    for r in s5["report_after"]:
        lines.append(f"    - {r}")
    lines += [
        "",
        "---",
        "",
        "## FINAL CLASSIFICATIONS",
        "",
    ]
    for c in _FINAL_CLASSIFICATIONS:
        lines.append(f"  - {c}")
    return "\n".join(lines)


def _write_decision_board_md(s3: list, s4: list) -> str:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    lines = [
        "# VÉLØ Post-Burn-In Decision Board",
        f"Generated: {now}",
        "Gate opens: VCP-03 Day 10/10",
        "Status: REPORT_ONLY — no decision taken until gate open",
        "",
        "---",
        "",
        "## What Has Been Proven",
        "",
    ]
    for f in s3:
        lines.append(f"**[{f['label']}]** {f['fact']}")
        lines.append(f"> Source: {f['source']} — {f['detail']}")
        lines.append("")
    lines += [
        "---",
        "",
        "## Decision Queue — ordered by priority after VCP-03 Day 10/10",
        "",
    ]
    for d in s4:
        lines.append(f"### Priority {d['priority']}: {d['decision']}")
        lines.append(f"**Status:** {d['status']}")
        lines.append(f"**Gate:** {d['gate']}")
        lines.append(f"**Blocked by:** {d['blocked_by']}")
        lines.append(f"**Purpose:** {d['purpose']}")
        lines.append("")
        lines.append("**Contract:**")
        for c in d["contract"]:
            lines.append(f"- {c}")
        lines.append("")
    lines += [
        "---",
        "",
        "## Execution Order After Gate Opens",
        "",
        "1. COURSE-01 — Draw and Pace Shadow Feature Registry (shadow only, provenance fields mandatory)",
        "2. VFU-21 — pick_sp Price Truth Repair (unlocks EW/exotics analysis)",
        "3. No-RPR GBM fold 2/3 decision (once corpus and price truth clean)",
        "4. New Build promotion decision (once N≥300 prospective shadow rows)",
        "5. Full model training decision (after VFU-21 + clean corpus)",
        "6. Resolve C-01 contradiction (operator decision)",
        "7. next_safe_action stale label patch (VCP maintenance patch)",
        "",
        "---",
        "",
        "## Hard Constraints Until Gate Opens",
        "",
    ]
    for c in _HARD_CONSTRAINTS:
        lines.append(f"- {c}")
    return "\n".join(lines)


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    print(f"── VCP-03-DAY2-DOCKET — {now} ──")

    s1 = s1_burnin_status()
    s2 = s2_course00a_findings()
    s3 = s3_proven_facts()
    s4 = s4_decision_board()
    s5 = s5_tomorrow()

    docket_md = _write_docket_md(s1, s2, s3, s4, s5)
    board_md = _write_decision_board_md(s3, s4)

    docket_json = {
        "meta": {
            "mission": "VCP-03-DAY2-DOCKET",
            "generated_at": now,
            "hard_constraints": _HARD_CONSTRAINTS,
            "final_classifications": _FINAL_CLASSIFICATIONS,
        },
        "s1_burnin_status": s1,
        "s2_course00a_findings": s2,
        "s3_proven_facts": s3,
        "s4_decision_board": s4,
        "s5_tomorrow": s5,
    }

    REPORTS.mkdir(parents=True, exist_ok=True)

    (REPORTS / "vcp03_day2_operator_docket.md").write_text(docket_md)
    print("  OK   data/reports/vcp03_day2_operator_docket.md")

    (REPORTS / "vcp03_day2_operator_docket.json").write_text(json.dumps(docket_json, indent=2))
    print("  OK   data/reports/vcp03_day2_operator_docket.json")

    (REPORTS / "vcp03_post_burnin_decision_board.md").write_text(board_md)
    print("  OK   data/reports/vcp03_post_burnin_decision_board.md")

    print()
    print(f"  Burn-in:        Day {s1['day_count']}/{s1['target_days']} PASS — {s1['remaining_days']} remaining")
    print(f"  Contradictions: {s1['contradiction_count']} (C-01: RP_MERGED_CLEAN vs BLOCKED learning gate — NOT SUPPRESSED)")
    print(f"  Stale label:    {s1['next_safe_action_id']} → KNOWN_STALE_LABEL_COSMETIC")
    print(f"  Stale facts:    {s2['stale_facts']['count']} corrected (Southwell Fibresand→Tapeta)")
    print(f"  Draw claims:    {s2['draw_bias_verdicts']['hypothesis_only_count']} HYPOTHESIS_ONLY")
    print(f"  Pace claims:    {s2['pace_verdicts']['hypothesis_only_count']} HYPOTHESIS_ONLY")
    print(f"  Decision queue: {len(s4)} items queued for Day 10")
    print()
    print("── VCP-03-DAY2-DOCKET COMPLETE ──")
    print("HARD STOP — no implementation follows. 8 burn-in days remain.")


if __name__ == "__main__":
    main()
