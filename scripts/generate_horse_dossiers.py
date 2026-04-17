"""
Generate operator-grade horse dossiers for VÉLØ pattern horses.

Pulls from all 5 intelligence layers (2024 + 2025) and writes:
  reports/dossiers/horse/<horse_slug>_<year>.md

Usage:
  python scripts/generate_horse_dossiers.py
  python scripts/generate_horse_dossiers.py --horse "Heavenly Fire (GB)"
  python scripts/generate_horse_dossiers.py --year 2025
"""
import os
import argparse
from datetime import date
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

TOKEN = os.getenv("SUPABASE_ACCESS_TOKEN")
REF   = os.getenv("SUPABASE_URL", "").split("//")[-1].split(".")[0]

DOSSIER_HORSES = [
    "Heavenly Fire (GB)",
    "Red Walls (GB)",
    "Bantz (IRE)",
    "River Wharfe (GB)",
    "Muscika (GB)",
]

ARCHETYPES = {
    "Heavenly Fire (GB)": "Repeat-Restore — trainer systematically returns to same circuit/trip",
    "Red Walls (GB)":     "Treadmill horse — narrow OR band all year, multiple wins at compressed marks",
    "Bantz (IRE)":        "Multi-signal active — multiple flag types active simultaneously, full doctrine convergence",
    "River Wharfe (GB)":  "Campaign-shift — trainer finds new winning circuit mid-season, campaigns hard",
    "Muscika (GB)":       "Drop-and-strike — wins only off dropped marks, not off raised marks",
}


def sql(q, timeout=60):
    r = requests.post(
        f"https://api.supabase.com/v1/projects/{REF}/database/query",
        headers={"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"},
        json={"query": q}, timeout=timeout,
    )
    result = r.json()
    if isinstance(result, dict) and "message" in result:
        raise ValueError(result["message"])
    return result


def build_dossier(horse: str, year: int) -> str:
    lines = []

    def h(text): lines.append(f"\n{text}")
    def row(text): lines.append(text)

    lines.append(f"# VÉLØ Horse Dossier — {horse}")
    lines.append(f"**Year**: {year}  |  **Archetype**: {ARCHETYPES.get(horse, 'Unknown')}")
    lines.append(f"**Generated**: {date.today().isoformat()}  |  **Doctrine**: VÉLØ Plot Doctrine v1")
    lines.append(f"\n---")

    # ── 1. Season overview ──────────────────────────────────────────────────────
    h("## Season Overview")
    overview = sql(f"""
        SELECT COUNT(*) AS runs,
               COUNT(*) FILTER (WHERE is_win) AS wins,
               MIN(date) AS first_run,
               MAX(date) AS last_run,
               COUNT(DISTINCT course) AS distinct_courses,
               MAX(trainer) AS trainer
        FROM intelligence.horse_run_history_{year}
        WHERE horse = '{horse}'
    """)
    if not overview or not overview[0].get('runs'):
        row(f"*No runs found for {horse} in {year}.*")
        return "\n".join(lines)

    o = overview[0]
    win_pct = round(o['wins'] / o['runs'] * 100, 1) if o['runs'] else 0
    row(f"| Runs | Wins | Win% | Period | Courses | Trainer |")
    row(f"|---|---|---|---|---|---|")
    row(f"| {o['runs']} | {o['wins']} | {win_pct}% | {o['first_run']} → {o['last_run']} | {o['distinct_courses']} | {o['trainer']} |")

    # ── 2. Full run log ─────────────────────────────────────────────────────────
    h("## Full Run Log")
    runs = sql(f"""
        SELECT h.date, s.course, s.dist, s.surface, h.pos, h.sp_decimal,
               t.or_rating_num, t.or_change,
               t.mark_compression_flag, t.first_run_after_drop_flag, t.or_treadmill_flag,
               s.full_setup_restore_flag, s.trip_restore_flag, s.course_restore_flag,
               h.days_since_last_run, h.is_win
        FROM intelligence.horse_run_history_{year} h
        LEFT JOIN intelligence.handicap_trajectory_{year} t ON t.run_id = h.run_id
        LEFT JOIN intelligence.setup_restore_events_{year} s ON s.run_id = h.run_id
        WHERE h.horse = '{horse}'
        ORDER BY h.date, h.race_id
    """, timeout=60)

    if runs:
        row(f"| Date | Course | Dist | Surf | Pos | SP | OR | OR chg | Flags | Days off | Win |")
        row(f"|---|---|---|---|---|---|---|---|---|---|---|")
        for r in runs:
            flags = []
            if r.get('mark_compression_flag'): flags.append('compress')
            if r.get('first_run_after_drop_flag'): flags.append('post_drop')
            if r.get('or_treadmill_flag'): flags.append('treadmill')
            if r.get('full_setup_restore_flag'): flags.append('full_restore')
            elif r.get('trip_restore_flag'): flags.append('trip_restore')
            elif r.get('course_restore_flag'): flags.append('course_restore')
            flags_str = ", ".join(flags) if flags else "—"
            or_chg = f"{r['or_change']:+d}" if r.get('or_change') is not None else "—"
            sp_str = f"{float(r['sp_decimal']):.1f}" if r.get('sp_decimal') else "—"
            win_str = "WIN" if r.get('is_win') else ""
            row(f"| {r['date']} | {r.get('course','?')} | {r.get('dist','?')} | "
                f"{r.get('surface','?')} | {r.get('pos','?')} | {sp_str} | "
                f"{r.get('or_rating_num') or '—'} | {or_chg} | {flags_str} | "
                f"{r.get('days_since_last_run') or '—'} | {win_str} |")

    # ── 3. OR trajectory ────────────────────────────────────────────────────────
    h("## OR Trajectory")
    traj = sql(f"""
        SELECT
            MIN(t.or_rating_num) AS min_or,
            MAX(t.or_rating_num) AS max_or,
            MAX(t.career_peak_or_to_date) AS career_peak,
            MAX(t.last_winning_or_to_date) AS last_winning_or,
            ROUND(AVG(t.or_change::numeric), 2) AS avg_or_change,
            COUNT(*) FILTER (WHERE t.mark_compression_flag) AS compression_runs,
            COUNT(*) FILTER (WHERE t.mark_restored_flag) AS restored_runs,
            COUNT(*) FILTER (WHERE t.first_run_after_drop_flag) AS post_drop_runs,
            COUNT(*) FILTER (WHERE t.or_treadmill_flag) AS treadmill_runs,
            BOOL_OR(t.or_treadmill_flag) AS is_treadmill_horse
        FROM intelligence.handicap_trajectory_{year} t
        JOIN intelligence.horse_run_history_{year} h ON h.run_id = t.run_id
        WHERE h.horse = '{horse}'
    """)
    if traj and traj[0].get('min_or') is not None:
        t = traj[0]
        band = (t['max_or'] or 0) - (t['min_or'] or 0)
        row(f"| Metric | Value |")
        row(f"|---|---|")
        row(f"| OR range | {t['min_or']} – {t['max_or']} (band: {band} pts) |")
        row(f"| Career peak OR (to date) | {t['career_peak'] or '—'} |")
        row(f"| Last winning OR | {t['last_winning_or'] or '—'} |")
        row(f"| Avg OR change per run | {t['avg_or_change']} |")
        row(f"| Compression runs | {t['compression_runs']} |")
        row(f"| Restored runs | {t['restored_runs']} |")
        row(f"| Post-drop first runs | {t['post_drop_runs']} |")
        row(f"| Treadmill runs | {t['treadmill_runs']} |")
        row(f"| Treadmill horse? | {'YES' if t['is_treadmill_horse'] else 'no'} |")
    else:
        row("*No numeric OR data available (no handicap rating assigned).*")

    # ── 4. Setup restoration pattern ────────────────────────────────────────────
    h("## Setup Restoration Pattern")
    restore = sql(f"""
        SELECT
            COUNT(*) AS total_runs,
            COUNT(*) FILTER (WHERE s.full_setup_restore_flag) AS full_restore,
            COUNT(*) FILTER (WHERE s.trip_restore_flag) AS trip_restore,
            COUNT(*) FILTER (WHERE s.course_restore_flag) AS course_restore,
            COUNT(*) FILTER (WHERE s.prior_win_at_surface_flag) AS surface_restore,
            MAX(s.best_course_to_date) AS best_course,
            MAX(s.best_dist_to_date) AS best_dist,
            MAX(s.best_surface_to_date) AS best_surface
        FROM intelligence.setup_restore_events_{year} s
        JOIN intelligence.horse_run_history_{year} h ON h.run_id = s.run_id
        WHERE h.horse = '{horse}'
    """)
    if restore:
        r = restore[0]
        row(f"| Restore type | Runs firing |")
        row(f"|---|---|")
        row(f"| full_setup_restore | {r['full_restore']} |")
        row(f"| trip_restore (dist+surf) | {r['trip_restore']} |")
        row(f"| course_restore | {r['course_restore']} |")
        row(f"| surface_restore | {r['surface_restore']} |")
        row(f"")
        row(f"**Best conditions on record**: {r['best_course'] or 'none yet'} / {r['best_dist'] or '—'} / {r['best_surface'] or '—'}")

    # ── 5. Candidate flag timeline ───────────────────────────────────────────────
    h("## Candidate Flag Timeline")
    h("*All runs where plot_pressure_flag = TRUE, showing reason codes.*\n")
    flags_timeline = sql(f"""
        SELECT p.date, s.course, s.dist, s.surface,
               p.or_rating_num, p.or_change, p.current_vs_last_winning_or,
               p.days_since_last_run, p.manual_review_priority,
               p.plot_reason_codes
        FROM intelligence.plot_candidate_flags_{year} p
        JOIN intelligence.setup_restore_events_{year} s ON s.run_id = p.run_id
        WHERE p.horse_name_raw = '{horse}'
          AND p.plot_pressure_flag = TRUE
        ORDER BY p.date
    """, timeout=60)

    if not flags_timeline:
        row("*No plot pressure appearances in this year.*")
    else:
        mr_count = sum(1 for r in flags_timeline if r.get('manual_review_priority'))
        row(f"*{len(flags_timeline)} plot pressure runs | {mr_count} manual_review_priority*\n")
        row(f"| Date | Course | Dist | Surf | OR | chg | vs WinOR | Days | MR | Codes |")
        row(f"|---|---|---|---|---|---|---|---|---|---|")
        for r in flags_timeline:
            or_chg = f"{r['or_change']:+d}" if r.get('or_change') is not None else "—"
            vs_win = f"{r['current_vs_last_winning_or']:+d}" if r.get('current_vs_last_winning_or') is not None else "—"
            codes = ", ".join(r['plot_reason_codes']) if r.get('plot_reason_codes') else "—"
            mr = "MR" if r.get('manual_review_priority') else ""
            row(f"| {r['date']} | {r.get('course','?')} | {r.get('dist','?')} | "
                f"{r.get('surface','?')} | {r.get('or_rating_num') or '—'} | {or_chg} | "
                f"{vs_win} | {r.get('days_since_last_run') or '—'} | {mr} | `{codes}` |")

    # ── 6. Tier 2+ candidate runs ────────────────────────────────────────────────
    h("## Tier 2+ Appearances")
    h("*High identity, MR=TRUE, 3+ reason codes. Highest-quality candidate runs.*\n")
    tier2_runs = sql(f"""
        SELECT p.date, s.course, s.dist, s.surface,
               p.or_rating_num, p.or_change, p.current_vs_last_winning_or,
               p.days_since_last_run, p.plot_reason_codes,
               t.career_peak_or_to_date, t.last_winning_or_to_date
        FROM intelligence.plot_candidate_flags_{year} p
        JOIN intelligence.setup_restore_events_{year} s ON s.run_id = p.run_id
        JOIN intelligence.handicap_trajectory_{year} t ON t.run_id = p.run_id
        WHERE p.horse_name_raw = '{horse}'
          AND p.identity_confidence = 'high'
          AND p.manual_review_priority = TRUE
          AND ARRAY_LENGTH(p.plot_reason_codes, 1) >= 3
        ORDER BY ARRAY_LENGTH(p.plot_reason_codes, 1) DESC, p.date DESC
    """, timeout=60)

    if not tier2_runs:
        row("*No Tier 2+ appearances in this year.*")
    else:
        row(f"*{len(tier2_runs)} Tier 2+ runs found*\n")
        for r in tier2_runs:
            n_codes = len(r['plot_reason_codes']) if r.get('plot_reason_codes') else 0
            tier = "Tier 3" if n_codes >= 4 else "Tier 2"
            or_chg = f"{r['or_change']:+d}" if r.get('or_change') is not None else "n/a"
            vs_win = f"{r['current_vs_last_winning_or']:+d}" if r.get('current_vs_last_winning_or') is not None else "n/a"
            codes_str = "` `".join(r['plot_reason_codes']) if r.get('plot_reason_codes') else "—"
            row(f"### {r['date']} — {r.get('course','?')} {r.get('dist','?')} {r.get('surface','?')} **[{tier} — {n_codes} codes]**")
            row(f"| OR | chg | vs WinOR | Peak OR | Win OR | Days off |")
            row(f"|---|---|---|---|---|---|")
            row(f"| {r.get('or_rating_num') or '—'} | {or_chg} | {vs_win} | "
                f"{r.get('career_peak_or_to_date') or '—'} | {r.get('last_winning_or_to_date') or '—'} | "
                f"{r.get('days_since_last_run') or '—'} |")
            row(f"")
            row(f"**Flags**: `{codes_str}`")
            row(f"")

    # ── 7. Wins in this year ─────────────────────────────────────────────────────
    h(f"## Winning Runs ({year})")
    wins = sql(f"""
        SELECT h.date, s.course, s.dist, s.surface, h.pos,
               h.sp_decimal, t.or_rating_num, t.or_change,
               t.current_vs_last_winning_or
        FROM intelligence.horse_run_history_{year} h
        LEFT JOIN intelligence.setup_restore_events_{year} s ON s.run_id = h.run_id
        LEFT JOIN intelligence.handicap_trajectory_{year} t ON t.run_id = h.run_id
        WHERE h.horse = '{horse}' AND h.is_win = TRUE
        ORDER BY h.date
    """)
    if not wins:
        row(f"*No wins recorded in {year}.*")
    else:
        row(f"| Date | Course | Dist | Surface | SP | OR | OR chg | vs WinOR |")
        row(f"|---|---|---|---|---|---|---|---|")
        for r in wins:
            sp_str = f"{float(r['sp_decimal']):.1f}" if r.get('sp_decimal') else "—"
            or_chg = f"{r['or_change']:+d}" if r.get('or_change') is not None else "—"
            vs_win = f"{r['current_vs_last_winning_or']:+d}" if r.get('current_vs_last_winning_or') is not None else "—"
            row(f"| {r['date']} | {r.get('course','?')} | {r.get('dist','?')} | "
                f"{r.get('surface','?')} | {sp_str} | {r.get('or_rating_num') or '—'} | {or_chg} | {vs_win} |")

    # ── 8. Trainer usage ─────────────────────────────────────────────────────────
    h("## Trainer Deployment Pattern")
    trainer_data = sql(f"""
        SELECT trainer,
               COUNT(*) AS runs,
               COUNT(*) FILTER (WHERE is_win) AS wins,
               ARRAY_AGG(DISTINCT course ORDER BY course) AS courses_used
        FROM intelligence.horse_run_history_{year}
        WHERE horse = '{horse}'
        GROUP BY trainer
        ORDER BY runs DESC
        LIMIT 5
    """)
    if trainer_data:
        row(f"| Trainer | Runs | Wins | Courses used |")
        row(f"|---|---|---|---|")
        for r in trainer_data:
            courses = ", ".join((r['courses_used'] or [])[:6])
            extra = f" (+{len(r['courses_used'])-6})" if r.get('courses_used') and len(r['courses_used']) > 6 else ""
            row(f"| {r['trainer']} | {r['runs']} | {r['wins']} | {courses}{extra} |")

    # ── Doctrine footer ──────────────────────────────────────────────────────────
    h("---")
    h("## Intelligence Notes")
    row(f"*Source: VÉLØ {year} intelligence stack — 5-layer rules-based system.*")
    row(f"*Archetype classification: {ARCHETYPES.get(horse, 'Unknown')}*")
    row(f"*Dossier is a candidate review file, not a prediction. Verdict requires full live pipeline.*")
    row(f"*VÉLØ Plot Doctrine v1 — Law: handicap movement + condition restoration = intent.*")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--horse", default=None, help="Horse name (default: all dossier horses)")
    parser.add_argument("--year", type=int, default=None, help="Year (default: 2025 and 2024)")
    args = parser.parse_args()

    horses = [args.horse] if args.horse else DOSSIER_HORSES
    years  = [args.year] if args.year else [2025, 2024]

    out_dir = Path("reports/dossiers/horse")
    out_dir.mkdir(parents=True, exist_ok=True)

    for horse in horses:
        for year in years:
            slug = (horse.lower()
                    .replace(" ", "_")
                    .replace("(", "").replace(")", "")
                    .replace("__", "_").strip("_"))
            out_path = out_dir / f"{slug}_{year}.md"

            print(f"Building: {horse} / {year}...", flush=True)
            try:
                content = build_dossier(horse, year)
                out_path.write_text(content, encoding="utf-8")
                print(f"  → {out_path}")
            except Exception as e:
                print(f"  ERROR: {e}")

    print("\nDone.")


if __name__ == "__main__":
    main()
