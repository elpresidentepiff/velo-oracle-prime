"""
VÉLØ — Sigma Forensic Report Generator
========================================
Reads sigma_audits + velo_post_race_reviews + learned_patterns for a given date
and writes reports/daily/sigma_forensic_YYYY-MM-DD.md.

Run: python scripts/generate_sigma_report.py [--date YYYY-MM-DD]
Default: today (UTC)
"""

import argparse
import os
import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")


def _f(v, fmt=None) -> str:
    if v is None:
        return "—"
    if fmt == "%":
        return f"{float(v)*100:.1f}%"
    if fmt == ".2f":
        return f"{float(v):.2f}"
    return str(v)


def generate(target_date: str) -> Path:
    from supabase import create_client
    import requests as _req

    sb = create_client(
        os.getenv("SUPABASE_URL"),
        os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_ANON_KEY", ""),
    )
    token = os.getenv("SUPABASE_ACCESS_TOKEN")
    ref   = os.getenv("SUPABASE_URL", "").split("//")[-1].split(".")[0]

    def sql(q):
        r = _req.post(
            f"https://api.supabase.com/v1/projects/{ref}/database/query",
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            json={"query": q}, timeout=15,
        )
        return r.json()

    # ── 1. sigma_audits for target_date ──────────────────────────────────────
    audits = sql(f"""
        SELECT race_id, track, date, outcome, miss_reason, decision_tier,
               confidence_level, verdict_score, top_pick_position,
               actual_winner_id, actual_winner_sp, notes
        FROM sigma_audits
        WHERE date = '{target_date}' AND outcome IS NOT NULL
        ORDER BY created_at ASC
    """)

    # ── 2. velo_post_race_reviews for target_date ─────────────────────────────
    reviews_raw = sql(f"""
        SELECT r.race_id, r.top_pick_won, r.top_pick_placed, r.top_pick_position,
               r.actual_winner_sp, r.review_outcome, r.notes AS review_notes
        FROM velo_post_race_reviews r
        JOIN sigma_audits s ON s.race_id = r.race_id AND s.date = '{target_date}'
        WHERE s.outcome IS NOT NULL
        GROUP BY r.race_id, r.top_pick_won, r.top_pick_placed, r.top_pick_position,
                 r.actual_winner_sp, r.review_outcome, r.notes
    """)

    # ── 3. All-time tier accuracy from learned_patterns ───────────────────────
    tier_patterns = sql("""
        SELECT pattern_name, occurrences, successful_predictions, success_rate
        FROM learned_patterns
        WHERE pattern_name LIKE 'tier_%_accuracy' AND is_active = true
        ORDER BY pattern_name
    """)

    # ── 4. All-time miss reason distribution from learned_patterns ────────────
    miss_patterns = sql("""
        SELECT pattern_name, occurrences, description
        FROM learned_patterns
        WHERE pattern_name LIKE 'miss_reason_%' AND is_active = true
        ORDER BY occurrences DESC
    """)

    # ── Compute today stats ───────────────────────────────────────────────────
    wins    = [a for a in audits if a["outcome"] == "WIN"]
    placed  = [a for a in audits if a["outcome"] == "PLACED"]
    misses  = [a for a in audits if a["outcome"] == "MISS"]
    total   = len(audits)

    tier_today: dict = defaultdict(lambda: {"total": 0, "wins": 0, "placed": 0})
    for a in audits:
        t = a.get("decision_tier") or "?"
        tier_today[t]["total"] += 1
        if a["outcome"] == "WIN":
            tier_today[t]["wins"] += 1
        elif a["outcome"] == "PLACED":
            tier_today[t]["placed"] += 1

    miss_today: dict = defaultdict(int)
    for a in misses:
        miss_today[a.get("miss_reason") or "unclassified"] += 1

    # Track chaos log — from sigma_audits.notes (chaos=N pace=X)
    track_chaos_rows = []
    for a in audits:
        notes = a.get("notes") or ""
        track = a.get("track") or "?"
        chaos_val = None
        pace_val  = None
        for part in notes.split("|")[0].split():
            if part.startswith("chaos="):
                chaos_val = part.split("=", 1)[1]
            if part.startswith("pace="):
                pace_val = part.split("=", 1)[1]
        track_chaos_rows.append({
            "track":   track,
            "chaos":   chaos_val,
            "pace":    pace_val,
            "tier":    a.get("decision_tier") or "?",
            "outcome": a.get("outcome"),
            "sp":      a.get("actual_winner_sp"),
        })

    # All-time tier truth from learned_patterns
    tier_all: dict = {}
    for p in tier_patterns:
        name = p["pattern_name"]  # e.g. "tier_B_accuracy"
        parts = name.split("_")
        if len(parts) >= 3:
            t = parts[1].upper()
            tier_all[t] = {
                "occ":  p["occurrences"] or 0,
                "wins": p["successful_predictions"] or 0,
                "rate": p["success_rate"],
            }

    # ── Build markdown ────────────────────────────────────────────────────────
    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    pct = lambda n, d: f"{round(n/d*100, 1)}%" if d else "—"

    lines = []
    A = lines.append

    A(f"# VÉLØ SIGMA FORENSIC — {target_date}")
    A(f"**Generated:** {now_str} | **Engine:** velo_prime_v1 | **Source:** auto sigma loop")
    A("")
    A("---")
    A("")
    A("## DAY SUMMARY")
    A("| Metric | Value |")
    A("|---|---|")
    A(f"| Races reviewed | {total} |")
    A(f"| WIN | {len(wins)} ({pct(len(wins), total)}) |")
    A(f"| PLACED | {len(placed)} ({pct(len(placed), total)}) |")
    A(f"| MISS | {len(misses)} ({pct(len(misses), total)}) |")
    tier_str = " ".join(f"{t}:{v['total']}" for t, v in sorted(tier_today.items()))
    A(f"| Tier breakdown today | {tier_str or '—'} |")
    winner_sps = [float(a["actual_winner_sp"]) for a in audits if a.get("actual_winner_sp") is not None]
    avg_sp = round(sum(winner_sps)/len(winner_sps), 2) if winner_sps else None
    A(f"| Avg winner SP | {_f(avg_sp)} |")
    longshots = sum(1 for a in audits if float(a.get("actual_winner_sp") or 0) > 10)
    A(f"| Longshot winners (SP>10) | {longshots} |")
    A("")
    A("---")
    A("")
    A("## TIER TRUTH (all-time cumulative)")
    A("| Tier | Races | Wins | Win% | Notes |")
    A("|---|---|---|---|---|")
    tier_notes = {
        "B": "0% — no confidence gate, all low-conf picks",
        "C": "—",
        "X": "chaos tier outperforming B",
        "A": "—",
        "D": "no bet tier",
    }
    for t in sorted(tier_all.keys()):
        v = tier_all[t]
        win_pct = pct(v["wins"], v["occ"])
        note = tier_notes.get(t, "—")
        A(f"| {t} | {v['occ']} | {v['wins']} | {win_pct} | {note} |")
    if not tier_all:
        A("| — | no data | — | — | — |")
    A("")
    if tier_all.get("B", {}).get("rate", 1) == 0 and tier_all.get("X", {}).get("rate", 0) > 0:
        A("> **⚠ B-tier inversion active.** B=0% win rate. X outperforms B. Confidence gate missing from synthesize_decision().")
        A("")
    A("---")
    A("")
    A("## TODAY'S RACES — FORENSIC")
    A("")

    # Build review lookup
    review_map = {}
    for rv in reviews_raw:
        race_id = rv["race_id"]
        ro = rv.get("review_outcome") or {}
        if isinstance(ro, str):
            try: ro = json.loads(ro)
            except Exception: ro = {}
        review_map[race_id] = {"rv": rv, "ro": ro}

    def _sig_summary(ro: dict) -> str:
        sa = ro.get("signal_attribution") or {}
        tp = sa.get("top_pick_scores") or {}
        ws = sa.get("winner_scores") or {}
        if not tp:
            return "—"
        # Find signals where top_pick had high score but winner had low
        gaps = {}
        for sig, tp_score in tp.items():
            w_score = ws.get(sig, 0)
            if tp_score > 0.3 and w_score < tp_score * 0.5:
                gaps[sig] = f"tp={tp_score:.2f} winner={w_score:.2f}"
        if gaps:
            return " | ".join(f"{k}({v})" for k, v in gaps.items())
        return "no gap found"

    if wins:
        A("### WINS")
        A("| Race | Course | Tier | Horse ID | SP | Conf | velo_prob | RPD |")
        A("|---|---|---|---|---|---|---|---|")
        for a in wins:
            rid  = a["race_id"]
            ro   = review_map.get(rid, {}).get("ro", {})
            A(f"| {rid} | {a.get('track') or '?'} | {a.get('decision_tier') or '?'} "
              f"| {a.get('actual_winner_id') or '?'} | {_f(a.get('actual_winner_sp'))} "
              f"| {a.get('confidence_level') or '?'} | {_f(a.get('verdict_score'), '.2f')} "
              f"| {ro.get('top_pick_rpd_tag') or '—'} |")
        A("")

    if placed:
        A("### PLACED (top pick placed, not won)")
        A("| Race | Course | Tier | Pos | Winner SP | Miss reason |")
        A("|---|---|---|---|---|---|")
        for a in placed:
            A(f"| {a['race_id']} | {a.get('track') or '?'} | {a.get('decision_tier') or '?'} "
              f"| {_f(a.get('top_pick_position'))} | {_f(a.get('actual_winner_sp'))} "
              f"| {a.get('miss_reason') or '—'} |")
        A("")

    if misses:
        A("### MISSES")
        A("| Race | Course | Chaos | Tier | Pos | Winner SP | Miss reason | Signal gap |")
        A("|---|---|---|---|---|---|---|---|")
        for a in misses:
            rid    = a["race_id"]
            ro     = review_map.get(rid, {}).get("ro", {})
            chaos  = ro.get("track_chaos_rating") or "?"
            sig    = _sig_summary(ro)
            A(f"| {rid} | {a.get('track') or '?'} | {chaos} "
              f"| {a.get('decision_tier') or '?'} | {_f(a.get('top_pick_position'))} "
              f"| {_f(a.get('actual_winner_sp'))} | {a.get('miss_reason') or '—'} | {sig} |")
        A("")

    A("---")
    A("")
    A("## MISS REASON HIERARCHY")
    A("| Reason | Today | All-time | Category |")
    A("|---|---|---|---|")
    reason_category = {
        "signal_underweighted_place_prob":        "forensic",
        "signal_underweighted_improvement_score": "forensic",
        "signal_underweighted_market_deception_score": "forensic",
        "high_confidence_miss":     "high-value — model confident and wrong",
        "outsider_hedge_omitted":   "structural — SP>10 winner",
        "market_decoy_followed":    "RESIDUAL catch-all — no signal gap found",
        "non_runner_or_untracked":  "data gap",
    }
    # All-time from learned_patterns
    alltime_miss = {
        p["pattern_name"].replace("miss_reason_", ""): p["occurrences"]
        for p in miss_patterns
    }
    all_reasons = sorted(set(list(miss_today.keys()) + list(alltime_miss.keys())))
    for r in all_reasons:
        cat = reason_category.get(r, "—")
        A(f"| {r} | {miss_today.get(r, 0)} | {alltime_miss.get(r, '?')} | {cat} |")
    A("")
    A("---")
    A("")
    A("## TRACK CHAOS LOG (today)")
    A("| Course | Chaos | Pace | Tier | Outcome | Winner SP |")
    A("|---|---|---|---|---|---|")
    seen_tracks = set()
    for tc in track_chaos_rows:
        key = (tc["track"], tc["tier"], tc["outcome"])
        if key in seen_tracks:
            continue
        seen_tracks.add(key)
        chaos_disp = tc['chaos'] if tc['chaos'] is not None else '?'
        pace_disp  = tc['pace']  if tc['pace']  is not None else '?'
        A(f"| {tc['track']} | {chaos_disp} | {pace_disp} "
          f"| {tc['tier']} | {tc['outcome']} | {_f(tc['sp'])} |")
    A("")
    A("---")
    A("")
    A("## DOCTRINE STATUS")
    A("| Item | State |")
    A("|---|---|")
    b_rate = tier_all.get("B", {}).get("rate")
    x_rate = tier_all.get("X", {}).get("rate")
    A(f"| B-tier confidence gate | {'MISSING — all B picks are confidence=low' if b_rate == 0 else 'present'} |")
    A(f"| B-tier win rate (all-time) | {pct(tier_all.get('B',{}).get('wins',0), tier_all.get('B',{}).get('occ',1))} |")
    A(f"| X-tier win rate (all-time) | {pct(tier_all.get('X',{}).get('wins',0), tier_all.get('X',{}).get('occ',1))} |")
    A(f"| market_decoy_followed dominance | {alltime_miss.get('market_decoy_followed', '?')} all-time misses (residual bucket) |")
    A(f"| _attribute_miss_signals fix | PENDING APPROVAL — diagnosis done, not yet implemented |")
    A(f"| Betfair market data | PENDING — market_engine.py unblocked when BSP feed arrives |")
    A("")
    A("---")
    A("")
    A("## FULL RACE CLOSURE DETAIL")
    A("")
    A("One line per reconciled race. Tiers A and B shown; others included if present.")
    A("")

    def _parse_notes(notes: str) -> dict:
        """Extract structured fields from sigma_audits.notes.

        Supports two formats:
          - JSON: {"summary": "pred=... | ...", "full_field_rpd": [...]}  (new)
          - Legacy pipe-delimited: pred=... | prob=... | winner_name=...  (old)
        """
        out = {"pred": None, "winner_name": None, "place2": None, "place3": None, "full_field_rpd": []}
        if not notes:
            return out
        # Try JSON first
        try:
            payload = json.loads(notes)
            if isinstance(payload, dict):
                summary = payload.get("summary", "")
                out["full_field_rpd"] = payload.get("full_field_rpd") or []
                for part in summary.split("|"):
                    part = part.strip()
                    for key in ("pred", "winner_name", "place2", "place3"):
                        if part.startswith(f"{key}="):
                            out[key] = part.split("=", 1)[1].strip()
                return out
        except (json.JSONDecodeError, TypeError):
            pass
        # Legacy pipe-delimited fallback
        for part in notes.split("|"):
            part = part.strip()
            for key in ("pred", "winner_name", "place2", "place3"):
                if part.startswith(f"{key}="):
                    out[key] = part.split("=", 1)[1].strip()
        return out

    def _placed_str(place2, place3) -> str:
        parts = [p for p in [place2, place3] if p and p != "unknown"]
        return "/".join(parts) if parts else "unknown"

    closure_tiers = {"A", "B", "C", "X"}
    closure_rows = [a for a in audits if (a.get("decision_tier") or "?").upper() in closure_tiers]
    # Sort: A first, then B, then rest; within tier by race_id
    tier_order = {"A": 0, "B": 1, "C": 2, "X": 3}
    closure_rows.sort(key=lambda a: (tier_order.get((a.get("decision_tier") or "?").upper(), 9), a.get("race_id", "")))

    if closure_rows:
        for a in closure_rows:
            rid      = a.get("race_id", "?")
            tier     = (a.get("decision_tier") or "?").upper()
            outcome  = a.get("outcome") or "?"
            pos      = a.get("top_pick_position")
            sp       = a.get("actual_winner_sp")
            miss_cat = a.get("miss_reason") or "none"
            notes    = a.get("notes") or ""
            parsed   = _parse_notes(notes)
            pick_name    = parsed["pred"] or "?"
            winner_name  = parsed["winner_name"] or a.get("actual_winner_id") or "?"
            placed_str   = _placed_str(parsed["place2"], parsed["place3"])
            sp_str       = f"{float(sp):.1f}" if sp is not None else "?"
            A(
                f"[{rid}] TIER={tier} | pick={pick_name} | pick_pos={pos or '?'}"
                f" | winner={winner_name} ({sp_str}) | placed={placed_str}"
                f" | result={outcome} | miss_category={miss_cat}"
            )
            # Full-field RPD per runner (only when data is present)
            rpd_rows = parsed.get("full_field_rpd") or []
            if rpd_rows:
                A("")
                A(f"  | Pos | Horse | RPD Tag | Conf | Evidence |")
                A(f"  |---|---|---|---|---|")
                for entry in rpd_rows:
                    conf_str = f"{entry['rpd_confidence']:.2f}" if entry.get("rpd_confidence") is not None else "—"
                    ev_str   = str(entry.get("rpd_evidence") or "—")[:40]
                    A(f"  | {entry.get('pos','?')} | {entry.get('horse','?')} "
                      f"| {entry.get('rpd_tag','?')} | {conf_str} | {ev_str} |")
                A("")
    else:
        A("_No A/B/C/X tier races reconciled for this date._")

    A("")
    A("---")
    A("")
    A("## WHAT CHANGED SINCE YESTERDAY")
    A("_Populated by operator or future delta script._")
    A("")
    A("---")
    A(f"_Generated by scripts/generate_sigma_report.py — {now_str}_")

    # ── Write file ────────────────────────────────────────────────────────────
    out_dir = Path(__file__).parent.parent / "reports" / "daily"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"sigma_forensic_{target_date}.md"
    out_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"Written: {out_path}")
    return out_path


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", default=datetime.now(timezone.utc).strftime("%Y-%m-%d"))
    args = parser.parse_args()
    generate(args.date)
