"""
VÉLØ Scoring Diff — Runtime Override Before/After Comparison
=============================================================
Replays synthesize_decision() + promotion blockers on stored velo_verdicts
data for a target date.  Runs twice — once with overrides OFF, once ON —
and produces a diff table showing exactly which races changed tier and why.

Cross-references sigma_audits.outcome to flag:
  - Blocked winners  (was A/B → now C/D/X, sigma_audits says WIN)
  - Freed misses     (was A/B, sigma says MISS — did blocker fire here?)
  - Clean blocks     (tier dropped, sigma says MISS — correct suppression)

Source data: velo_verdicts.full_analysis[] — the runner-level scoring dict
stored at verdict time.  No re-scoring, no API calls, no writes.

Run:
  python scripts/scoring_diff.py --date 2026-04-11
  python scripts/scoring_diff.py --date 2026-04-11 --show-all   (print every race)
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import date
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
load_dotenv(ROOT / ".env")

from supabase import create_client

SUPA_URL = os.getenv("SUPABASE_URL", "")
SUPA_KEY = (os.getenv("SUPABASE_SERVICE_ROLE_KEY")
            or os.getenv("SUPABASE_SERVICE_KEY", ""))


# ── Tier ordering ─────────────────────────────────────────────────────────────
_TIER_ORDER = {"A": 0, "B": 1, "C": 2, "D": 3, "X": 4}
_BET_TIERS  = {"A", "B"}


# ── Synthesize Decision — standalone replay ───────────────────────────────────

def _synthesize(top: dict, second_prob: float, overrides: dict) -> tuple[str, list[str]]:
    """
    Replay of synthesize_decision() against stored runner dict.
    Uses overrides["tier_thresholds"] when present, else hardcoded baseline.
    Returns (tier, reasons).
    """
    prob     = float(top.get("velo_prime_prob") or 0)
    place    = float(top.get("place_prob") or 0)
    longshot = float(top.get("longshot_prob") or 0)
    sp_dec   = float(top.get("sp_dec") or 0)        # may be absent — defaults 0
    improve  = float(top.get("improvement_score") or 0)
    chaos_m  = bool(top.get("macro_chaos_mode") or False)
    trap     = (top.get("favourite_trap_risk") or "normal").lower()
    gap      = prob - second_prob

    _thresholds = overrides.get("tier_thresholds") or {}
    _a = _thresholds.get("A", {})
    _b = _thresholds.get("B", {})
    _c = _thresholds.get("C", {})
    _x = _thresholds.get("X", {})

    A_min_prob    = float(_a.get("min_prob",   0.32))
    A_min_gap     = float(_a.get("min_gap",    0.08))
    A_min_place   = float(_a.get("min_place",  0.52))
    B_min_prob    = float(_b.get("min_prob",   0.15))
    B_min_gap     = float(_b.get("min_gap",    0.03))
    B_min_place   = float(_b.get("min_place",  0.45))
    B_min_improve = float(_b.get("min_improve",0.18))
    C_min_prob    = float(_c.get("min_prob",   0.13))
    C_min_gap     = float(_c.get("min_gap",    0.02))
    C_rescue_place= float(_c.get("rescue_place",0.55))
    C_rescue_prob = float(_c.get("rescue_prob", 0.11))
    X_max_prob    = float(_x.get("flat_field_prob_max", 0.10))
    X_max_gap     = float(_x.get("max_gap",   0.015))
    X_max_place   = float(_x.get("max_place", 0.40))

    eff_conf = "high" if prob >= 0.45 else "normal" if prob >= B_min_prob else "low"
    longshot_trigger = longshot > 0.35 and sp_dec >= 10.0

    reasons = []
    strong_escape = prob >= 0.18 and place >= 0.35

    if (prob < X_max_prob
            or (gap < X_max_gap and place < X_max_place and not strong_escape)
            or (longshot_trigger and not strong_escape)
            or chaos_m):
        if prob < X_max_prob:    reasons.append(f"flat field {prob:.3f}")
        if gap < X_max_gap and place < X_max_place:
            reasons.append(f"no sep gap={gap:.3f} place={place:.3f}")
        if chaos_m:              reasons.append("macro chaos")
        return "X", reasons

    reasons.append(f"win={prob:.3f} gap={gap:.3f} place={place:.3f}")

    if (prob >= A_min_prob and gap >= A_min_gap and place >= A_min_place
            and eff_conf not in ("low",) and trap != "high"):
        return "A", reasons + ["A gate: all ok"]

    b_place_ok = place >= B_min_place
    b_gap_ok   = gap >= A_min_gap
    b_improve  = improve >= B_min_improve
    if (prob >= B_min_prob and gap >= B_min_gap and eff_conf not in ("low",)
            and (b_place_ok or b_gap_ok or b_improve)):
        return "B", reasons

    if (prob >= C_min_prob and gap >= C_min_gap) or (place >= C_rescue_place and prob >= C_rescue_prob):
        return "C", reasons

    return "D", reasons + ["weak signal"]


def _apply_tie_v3(top: dict, tier: str) -> str:
    """Replay TIE v3 gate from stored tie_gate_tier_upgrade field."""
    if top.get("tie_gate_fires") and top.get("tie_gate_tier_upgrade"):
        upgraded = top["tie_gate_tier_upgrade"]
        # TIE v3 only upgrades C or D
        if tier in ("C", "D") and upgraded in ("B", "C"):
            return upgraded
    return tier


def _apply_blockers(top: dict, tier: str, overrides: dict) -> tuple[str, list[str]]:
    """Replay _apply_promotion_blockers() from stored runner dict."""
    fired = []
    blockers_cfg = overrides.get("tier_promotion_blockers") or {}
    blockers     = blockers_cfg.get("blockers", [])
    if not blockers:
        return tier, fired

    current_rank = _TIER_ORDER.get(tier, 99)

    for b in blockers:
        max_tier = b.get("max_tier", "D")
        max_rank = _TIER_ORDER.get(max_tier, 99)
        if current_rank >= max_rank:
            continue

        conditions = b.get("when", {})
        matched = True
        for k, v in conditions.items():
            actual = top.get(k)
            if actual is None:
                matched = False
                break
            if isinstance(v, bool):
                if bool(actual) != v:
                    matched = False
                    break
            elif isinstance(v, str):
                if str(actual).lower() != v.lower():
                    matched = False
                    break
            else:
                if actual != v:
                    matched = False
                    break

        if matched:
            fired.append(f"{tier}→{max_tier}: {b.get('note','?')}")
            tier = max_tier
            current_rank = max_rank

    return tier, fired


# ── Main diff logic ───────────────────────────────────────────────────────────

def run_diff(target_date: str, show_all: bool = False):
    db = create_client(SUPA_URL, SUPA_KEY)

    # ── Load active overrides ─────────────────────────────────────────────────
    from app.runtime.overrides import load_runtime_overrides
    active_overrides = load_runtime_overrides(db)

    print(f"\nVÉLØ SCORING DIFF — {target_date}")
    print(f"Active overrides: {sorted(active_overrides.keys()) or 'NONE'}")
    print("=" * 80)

    # ── Load verdicts ─────────────────────────────────────────────────────────
    vv_rows = (
        db.table("velo_verdicts")
        .select("race_id, decision_tier, velo_prime_prob, place_prob, "
                "improvement_score, market_deception_score, confidence_level, "
                "full_analysis")
        .gte("generated_at", f"{target_date}T00:00:00")
        .lt("generated_at", f"{target_date}T23:59:59")
        .order("generated_at")
        .execute()
    )
    verdicts = vv_rows.data or []
    print(f"Loaded {len(verdicts)} verdicts\n")

    # ── Load sigma outcomes ───────────────────────────────────────────────────
    sa_rows = (
        db.table("sigma_audits")
        .select("race_id, outcome, miss_reason, track, off_time, top_pick_position")
        .eq("date", target_date)
        .execute()
    )
    sigma = {r["race_id"]: r for r in (sa_rows.data or [])}

    # ── Replay each verdict ───────────────────────────────────────────────────
    results = []
    for v in verdicts:
        race_id = v["race_id"]
        stored_tier = v.get("decision_tier") or "?"

        fa = v.get("full_analysis") or []
        if isinstance(fa, str):
            fa = json.loads(fa)
        if not isinstance(fa, list) or not fa:
            results.append({
                "race_id": race_id,
                "stored_tier": stored_tier,
                "baseline_tier": "?",
                "live_tier": "?",
                "changed": False,
                "blockers_fired": [],
                "sigma": sigma.get(race_id, {}),
                "error": "no full_analysis",
            })
            continue

        top         = fa[0]
        second_prob = float(fa[1].get("velo_prime_prob", 0)) if len(fa) > 1 else 0.0

        # Inject derived blocker flags — these were added to velo_prime_service.py
        # after Apr 11 scoring, so they won't exist in stored full_analysis dicts.
        # Derive them from stored source fields so the replay is faithful to the
        # new production logic (market_deception_score < 0.10, longshot_prob > 0.35).
        if "market_decoy_signal" not in top:
            top["market_decoy_signal"] = float(top.get("market_deception_score") or 0) < 0.10
        if "longshot_risk_flag" not in top:
            top["longshot_risk_flag"] = float(top.get("longshot_prob") or 0) > 0.35
        # longshot_block_allowed: longshot_risk_flag conditioned away from drifting market.
        # For historical replays, horse_state is read from the stored top dict.
        if "longshot_block_allowed" not in top:
            _hs_ms = (top.get("horse_state") or {}).get("market_state")
            top["longshot_block_allowed"] = (
                float(top.get("longshot_prob") or 0) > 0.35
                and _hs_ms != "drifting"
            )

        # ── Pass A: overrides OFF ─────────────────────────────────────────────
        tier_a, _ = _synthesize(top, second_prob, {})
        tier_a    = _apply_tie_v3(top, tier_a)
        tier_a, _ = _apply_blockers(top, tier_a, {})

        # ── Pass B: overrides ON ──────────────────────────────────────────────
        tier_b, _ = _synthesize(top, second_prob, active_overrides)
        tier_b    = _apply_tie_v3(top, tier_b)
        tier_b, blockers_fired = _apply_blockers(top, tier_b, active_overrides)

        sa = sigma.get(race_id, {})
        results.append({
            "race_id":        race_id,
            "course":         sa.get("track", "?"),
            "off_time":       sa.get("off_time", "?"),
            "stored_tier":    stored_tier,
            "baseline_tier":  tier_a,
            "live_tier":      tier_b,
            "changed":        tier_a != tier_b,
            "blockers_fired": blockers_fired,
            "outcome":        sa.get("outcome", "?"),
            "miss_reason":    sa.get("miss_reason"),
            "top_pick_pos":   sa.get("top_pick_position"),
            "prob":             float(top.get("velo_prime_prob") or 0),
            "trap":             top.get("favourite_trap_risk", "normal"),
            "chaos":            top.get("macro_chaos_mode", False),
            "mkt_dec_score":    float(top.get("market_deception_score") or 0),
            "longshot_prob":    float(top.get("longshot_prob") or 0),
            "market_decoy_signal":   bool(top.get("market_decoy_signal")),
            "longshot_risk_flag":    bool(top.get("longshot_risk_flag")),
            "longshot_block_allowed": bool(top.get("longshot_block_allowed")),
        })

    # ── Summary stats ─────────────────────────────────────────────────────────
    changed     = [r for r in results if r["changed"]]
    unchanged   = [r for r in results if not r["changed"]]
    errors      = [r for r in results if r.get("error")]

    # Sanity check: baseline should match stored tier
    mismatches = [r for r in results if r["baseline_tier"] != r["stored_tier"]
                  and r["baseline_tier"] != "?" and r["stored_tier"] != "?"]

    print(f"{'SUMMARY':}")
    print(f"  Total races:      {len(results)}")
    print(f"  Tier changed:     {len(changed)}")
    print(f"  Unchanged:        {len(unchanged)}")
    print(f"  No full_analysis: {len(errors)}")
    print(f"  Replay mismatches (baseline≠stored): {len(mismatches)}")
    if mismatches:
        for m in mismatches[:5]:
            print(f"    {m['race_id']} stored={m['stored_tier']} replay={m['baseline_tier']}")

    # ── Tier distribution comparison ──────────────────────────────────────────
    from collections import Counter
    baseline_dist = Counter(r["baseline_tier"] for r in results if r["baseline_tier"] != "?")
    live_dist     = Counter(r["live_tier"]     for r in results if r["live_tier"] != "?")

    print(f"\n{'TIER DISTRIBUTION':}")
    print(f"  {'Tier':<6} {'Baseline':>10} {'Live':>10} {'Delta':>8}")
    print(f"  {'─'*36}")
    for t in ("A", "B", "C", "D", "X"):
        b = baseline_dist.get(t, 0)
        l = live_dist.get(t, 0)
        d = l - b
        mark = " ←" if d != 0 else ""
        print(f"  {t:<6} {b:>10} {l:>10} {d:>+8}{mark}")

    # ── Changed races detail ──────────────────────────────────────────────────
    if changed:
        print(f"\n{'CHANGED RACES ({len(changed)}):':}")
        print(f"  {'Race ID':<16} {'Course':<12} {'Off':>5} {'Stored':>7} {'Before':>7} {'After':>7} "
              f"{'Outcome':<8} {'Pos':>3} {'Blocker fired'}")
        print(f"  {'─'*100}")
        for r in sorted(changed, key=lambda x: _TIER_ORDER.get(x["baseline_tier"], 9)):
            before = r["baseline_tier"]
            after  = r["live_tier"]
            outcome = r.get("outcome", "?")
            pos     = str(r.get("top_pick_pos") or "?")
            blocker = "; ".join(r["blockers_fired"]) if r["blockers_fired"] else "(threshold change)"
            blocker = blocker[:55]

            # Highlight winner suppressions
            warn = ""
            if before in _BET_TIERS and after not in _BET_TIERS and outcome == "WIN":
                warn = " *** SUPPRESSED WINNER ***"
            elif before in _BET_TIERS and after not in _BET_TIERS and outcome not in ("WIN", "PLACED"):
                warn = " [correct block — miss]"
            elif before in _BET_TIERS and after not in _BET_TIERS and outcome == "PLACED":
                warn = " [placed — borderline]"

            print(f"  {r['race_id']:<16} {r.get('course','?'):<12} {r.get('off_time','?'):>5} "
                  f"{r['stored_tier']:>7} {before:>7} {after:>7} "
                  f"{outcome:<8} {pos:>3} {blocker}{warn}")

    # ── Suppressed winners ────────────────────────────────────────────────────
    suppressed = [
        r for r in changed
        if r["baseline_tier"] in _BET_TIERS
        and r["live_tier"] not in _BET_TIERS
        and r.get("outcome") == "WIN"
    ]
    correct_blocks = [
        r for r in changed
        if r["baseline_tier"] in _BET_TIERS
        and r["live_tier"] not in _BET_TIERS
        and r.get("outcome") not in ("WIN", "PLACED")
    ]
    freed = [
        r for r in changed
        if r["baseline_tier"] not in _BET_TIERS
        and r["live_tier"] in _BET_TIERS
    ]

    # ── Per-blocker fire counts ───────────────────────────────────────────────
    from collections import defaultdict
    blocker_fires: dict = defaultdict(lambda: {"total": 0, "wins": 0, "misses": 0, "placed": 0})
    for r in results:
        for bf in r.get("blockers_fired", []):
            key = bf.split(":")[0].strip()  # e.g. "A→B"
            # Use note segment for grouping
            note_key = bf[:40]
            blocker_fires[note_key]["total"] += 1
            oc = r.get("outcome", "?")
            if oc == "WIN":    blocker_fires[note_key]["wins"] += 1
            elif oc == "PLACED": blocker_fires[note_key]["placed"] += 1
            else:              blocker_fires[note_key]["misses"] += 1

    print(f"\n{'ACTUATION QUALITY:':}")
    print(f"  Correct suppressions (blocked races that missed):  {len(correct_blocks)}")
    print(f"  Winner suppressions  (blocked races that WON):     {len(suppressed)}")
    print(f"  Freed races          (tier raised by live config): {len(freed)}")

    if blocker_fires:
        print(f"\n  Per-blocker fire counts:")
        for note, counts in sorted(blocker_fires.items()):
            safe = "SAFE" if counts["wins"] == 0 else f"CAUTION — {counts['wins']} win(s)"
            print(f"    [{safe}] fires={counts['total']} wins={counts['wins']} placed={counts['placed']} misses={counts['misses']}")
            print(f"      blocker: {note}")
    else:
        print(f"\n  No blockers fired on {target_date} (all races within tier thresholds).")

    if suppressed:
        print(f"\n  *** SUPPRESSED WINNERS — review immediately ***")
        for r in suppressed:
            print(f"    {r['race_id']} | {r.get('course')} {r.get('off_time')} | "
                  f"{r['baseline_tier']}→{r['live_tier']} | blocker: {r['blockers_fired']}")
            print(f"    prob={r['prob']:.3f} trap={r['trap']} chaos={r['chaos']}")
    else:
        print(f"\n  No suppressed winners on {target_date}.")

    # ── Show all races if requested ───────────────────────────────────────────
    if show_all:
        print(f"\n{'ALL RACES:':}")
        print(f"  {'Race ID':<16} {'Course':<12} {'Off':>5} {'Before':>7} {'After':>7} {'Outcome':<8} {'Blocker'}")
        print(f"  {'─'*80}")
        for r in results:
            before = r.get("baseline_tier", "?")
            after  = r.get("live_tier", "?")
            change_mark = " *" if r["changed"] else ""
            blocker = ("; ".join(r["blockers_fired"])[:30]) if r["blockers_fired"] else ""
            print(f"  {r['race_id']:<16} {r.get('course','?'):<12} {r.get('off_time','?'):>5} "
                  f"{before:>7} {after:>7} {r.get('outcome','?'):<8} {blocker}{change_mark}")

    print(f"\n{'='*80}")
    verdict_line = (
        "SAFE" if not suppressed else f"CAUTION — {len(suppressed)} SUPPRESSED WINNER(S)"
    )
    print(f"VERDICT: {verdict_line}")
    print("="*80)

    return {
        "changed": len(changed),
        "suppressed_winners": len(suppressed),
        "correct_blocks": len(correct_blocks),
        "tier_shift": dict(zip(
            [t for t in "ABCDX"],
            [live_dist.get(t,0) - baseline_dist.get(t,0) for t in "ABCDX"]
        )),
    }


def main():
    parser = argparse.ArgumentParser(description="Scoring diff: overrides off vs on")
    parser.add_argument("--date", default=str(date.today()),
                        help="Target date YYYY-MM-DD (default: today)")
    parser.add_argument("--show-all", action="store_true",
                        help="Print all races, not just changed ones")
    args = parser.parse_args()

    if not SUPA_URL or not SUPA_KEY:
        print("ERROR: SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY not set")
        sys.exit(1)

    run_diff(args.date, show_all=args.show_all)


if __name__ == "__main__":
    main()
