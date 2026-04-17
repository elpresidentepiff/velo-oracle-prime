"""
Generate a Plot Radar Report from intelligence.plot_candidate_flags_2025.

This is an operator-grade intelligence output — not a prediction, not a verdict.
It surfaces horses where handicap movement and condition restoration intersect.

Criteria (VÉLØ Plot Doctrine v1 — Tier 2 / Tier 3):
  - identity_confidence = 'high'
  - manual_review_priority = TRUE
  - 3+ reason codes
  - last_winning_or_to_date IS NOT NULL
  - current_vs_last_winning_or BETWEEN -10 AND 7  (near prior winning mark)

Output: reports/plot_radar/plot_radar_YYYY-MM-DD.md

Usage:
  python scripts/generate_plot_radar_report.py
  python scripts/generate_plot_radar_report.py --date 2025-03-11
  python scripts/generate_plot_radar_report.py --window 14   (last N days)
"""
import os
import sys
import argparse
from datetime import date, timedelta
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

TOKEN = os.getenv("SUPABASE_ACCESS_TOKEN")
REF   = os.getenv("SUPABASE_URL", "").split("//")[-1].split(".")[0]

DOSSIER_HORSES = {
    "Heavenly Fire (GB)", "Red Walls (GB)", "Bantz (IRE)",
    "River Wharfe (GB)", "Muscika (GB)"
}


def sql(q, timeout=60):
    r = requests.post(
        f"https://api.supabase.com/v1/projects/{REF}/database/query",
        headers={"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"},
        json={"query": q}, timeout=timeout,
    )
    return r.json()


def generate_report(report_date: date, window_days: int = 7) -> str:
    date_from = (report_date - timedelta(days=window_days - 1)).isoformat()
    date_to   = report_date.isoformat()

    lines = []

    def h(text): lines.append(f"\n{text}")
    def row(text): lines.append(text)

    lines.append(f"# VÉLØ Plot Radar Report")
    lines.append(f"**Period**: {date_from} → {date_to} ({window_days} days)")
    lines.append(f"**Generated**: {date.today().isoformat()}")
    lines.append(f"**Doctrine**: VÉLØ Plot Doctrine v1 — Tier 2/3 only")
    lines.append(f"**Scope**: identity=high, MR=true, 3+ codes, near last winning OR")
    lines.append(f"\n---")

    # ── Summary stats ──────────────────────────────────────────────────────────
    h("## Summary")
    stats = sql(f"""
        SELECT
            COUNT(*) AS candidates,
            COUNT(DISTINCT entity_id) AS distinct_horses,
            COUNT(*) FILTER (WHERE ARRAY_LENGTH(plot_reason_codes,1) >= 4) AS tier3_count,
            COUNT(*) FILTER (WHERE post_drop_restore) AS post_drop,
            COUNT(*) FILTER (WHERE full_restore_live) AS full_restore,
            COUNT(*) FILTER (WHERE reactivation_candidate AND full_restore_live) AS react_full,
            COUNT(*) FILTER (WHERE compression_plus_restore) AS compress_restore,
            ROUND(AVG(current_vs_last_winning_or), 1) AS avg_vs_win_or,
            ROUND(AVG(or_change::numeric), 2) AS avg_or_change
        FROM intelligence.plot_candidate_flags_2025
        WHERE identity_confidence = 'high'
          AND manual_review_priority = TRUE
          AND ARRAY_LENGTH(plot_reason_codes, 1) >= 3
          AND current_vs_last_winning_or BETWEEN -10 AND 7
          AND date BETWEEN '{date_from}' AND '{date_to}'
    """)
    if stats:
        s = stats[0]
        row(f"| Metric | Value |")
        row(f"|---|---|")
        row(f"| Candidates (Tier 2+) | {s['candidates']} |")
        row(f"| Distinct horses | {s['distinct_horses']} |")
        row(f"| Tier 3 (4+ codes) | {s['tier3_count']} |")
        row(f"| post_drop_restore | {s['post_drop']} |")
        row(f"| full_restore_live | {s['full_restore']} |")
        row(f"| full_restore + reactivation | {s['react_full']} |")
        row(f"| compression + restore | {s['compress_restore']} |")
        row(f"| avg vs last winning OR | {s['avg_vs_win_or']} pts |")
        row(f"| avg OR change on run | {s['avg_or_change']} pts |")

    # ── Tier 3: 4+ codes (highest quality) ────────────────────────────────────
    h("## Tier 3 — Strongest Candidates (4+ codes)")
    h("*Handicap movement AND condition restoration AND near last winning OR. Highest structural convergence.*\n")

    tier3 = sql(f"""
        SELECT p.horse_name_raw, p.trainer, p.date,
               p.or_rating_num, p.or_change, p.current_vs_last_winning_or,
               p.days_since_last_run, p.layoff_flag,
               p.plot_reason_codes,
               s.course, s.surface, s.dist, s.best_course_to_date, s.best_dist_to_date,
               t.career_peak_or_to_date, t.last_winning_or_to_date
        FROM intelligence.plot_candidate_flags_2025 p
        JOIN intelligence.setup_restore_events_2025 s ON s.run_id = p.run_id
        JOIN intelligence.handicap_trajectory_2025 t ON t.run_id = p.run_id
        WHERE p.identity_confidence = 'high'
          AND p.manual_review_priority = TRUE
          AND ARRAY_LENGTH(p.plot_reason_codes, 1) >= 4
          AND p.current_vs_last_winning_or BETWEEN -10 AND 7
          AND p.date BETWEEN '{date_from}' AND '{date_to}'
        ORDER BY ARRAY_LENGTH(p.plot_reason_codes, 1) DESC, p.date DESC, p.horse_name_raw
    """)

    if not tier3:
        row("*No Tier 3 candidates in this window.*")
    else:
        for r in tier3:
            dossier_flag = " ⚑ DOSSIER" if r['horse_name_raw'] in DOSSIER_HORSES else ""
            layoff_str = f", {r['days_since_last_run']}d off" if r['days_since_last_run'] else ""
            or_chg_str = f"{r['or_change']:+d}" if r['or_change'] is not None else "n/a"
            vs_win_str = f"{r['current_vs_last_winning_or']:+d}" if r['current_vs_last_winning_or'] is not None else "n/a"
            row(f"### {r['horse_name_raw']}{dossier_flag}")
            row(f"**{r['date']}** | {r['course']} | {r['dist']} {r['surface']} | Trainer: {r['trainer']}")
            row(f"")
            row(f"| OR | OR chg | vs Win OR | Peak OR | Win OR | days off |")
            row(f"|---|---|---|---|---|---|")
            row(f"| {r['or_rating_num']} | {or_chg_str} | {vs_win_str} | {r['career_peak_or_to_date']} | {r['last_winning_or_to_date']} | {r['days_since_last_run'] or '—'} |")
            row(f"")
            row(f"**Flags**: `{'` `'.join(r['plot_reason_codes'])}`")
            if r['best_course_to_date'] and r['best_dist_to_date']:
                row(f"**Won at**: {r['best_course_to_date']} / {r['best_dist_to_date']}")
            row(f"")

    # ── Tier 2: 3-code candidates ──────────────────────────────────────────────
    h("## Tier 2 — Working Candidates (3 codes)")
    h("*Signal confirmed — two themes intersecting. Review queue.*\n")

    tier2 = sql(f"""
        SELECT p.horse_name_raw, p.trainer, p.date,
               p.or_rating_num, p.or_change, p.current_vs_last_winning_or,
               p.days_since_last_run, p.plot_reason_codes,
               s.course, s.surface, s.dist
        FROM intelligence.plot_candidate_flags_2025 p
        JOIN intelligence.setup_restore_events_2025 s ON s.run_id = p.run_id
        WHERE p.identity_confidence = 'high'
          AND p.manual_review_priority = TRUE
          AND ARRAY_LENGTH(p.plot_reason_codes, 1) = 3
          AND p.current_vs_last_winning_or BETWEEN -10 AND 7
          AND p.date BETWEEN '{date_from}' AND '{date_to}'
        ORDER BY p.date DESC, p.horse_name_raw
    """)

    if not tier2:
        row("*No Tier 2 candidates in this window.*")
    else:
        row(f"*{len(tier2)} candidates — showing all*\n")
        row(f"| Date | Horse | Trainer | Course | Dist | OR | chg | vs WinOR | days | Codes |")
        row(f"|---|---|---|---|---|---|---|---|---|---|")
        for r in tier2:
            dossier_flag = " ⚑" if r['horse_name_raw'] in DOSSIER_HORSES else ""
            or_chg_str = f"{r['or_change']:+d}" if r['or_change'] is not None else "—"
            vs_win_str = f"{r['current_vs_last_winning_or']:+d}" if r['current_vs_last_winning_or'] is not None else "—"
            codes_short = ", ".join(r['plot_reason_codes'])
            row(f"| {r['date']} | {r['horse_name_raw']}{dossier_flag} | {r['trainer']} | "
                f"{r['course']} | {r['dist']} {r['surface']} | {r['or_rating_num']} | "
                f"{or_chg_str} | {vs_win_str} | {r['days_since_last_run'] or '—'} | `{codes_short}` |")

    # ── Dossier horses in window ───────────────────────────────────────────────
    h("## Dossier Horse Activity")
    h("*Pattern horses — any MR appearance, regardless of code count.*\n")

    for horse in sorted(DOSSIER_HORSES):
        drows = sql(f"""
            SELECT p.date, p.or_rating_num, p.or_change, p.current_vs_last_winning_or,
                   p.days_since_last_run, p.manual_review_priority,
                   p.plot_reason_codes,
                   s.course, s.dist, s.surface
            FROM intelligence.plot_candidate_flags_2025 p
            JOIN intelligence.setup_restore_events_2025 s ON s.run_id = p.run_id
            WHERE p.horse_name_raw = '{horse}'
              AND p.date BETWEEN '{date_from}' AND '{date_to}'
            ORDER BY p.date DESC
        """)
        if drows:
            row(f"**{horse}**")
            for r in drows:
                mr = "MR" if r['manual_review_priority'] else "  "
                or_chg_str = f"{r['or_change']:+d}" if r['or_change'] is not None else "n/a"
                vs_win_str = f"{r['current_vs_last_winning_or']:+d}" if r['current_vs_last_winning_or'] is not None else "n/a"
                codes = ", ".join(r['plot_reason_codes']) if r['plot_reason_codes'] else "—"
                row(f"  `{r['date']}` {mr}  {r['course']} {r['dist']} {r['surface']}  "
                    f"OR={r['or_rating_num']} chg={or_chg_str} vs_win={vs_win_str}  off={r['days_since_last_run'] or '1st'}d  [{codes}]")
            row("")

    # ── Top trainers in window ─────────────────────────────────────────────────
    h("## Active Trainer Patterns")
    h("*Trainers with 2+ MR candidates in window (Tier 2+).*\n")

    trainers = sql(f"""
        SELECT trainer,
               COUNT(*) AS mr_count,
               COUNT(*) FILTER (WHERE ARRAY_LENGTH(plot_reason_codes,1) >= 4) AS tier3,
               COUNT(*) FILTER (WHERE post_drop_restore) AS post_drop,
               COUNT(*) FILTER (WHERE full_restore_live) AS full_restore,
               ARRAY_AGG(DISTINCT horse_name_raw ORDER BY horse_name_raw) AS horses
        FROM intelligence.plot_candidate_flags_2025
        WHERE identity_confidence = 'high'
          AND manual_review_priority = TRUE
          AND ARRAY_LENGTH(plot_reason_codes, 1) >= 3
          AND current_vs_last_winning_or BETWEEN -10 AND 7
          AND date BETWEEN '{date_from}' AND '{date_to}'
        GROUP BY trainer
        HAVING COUNT(*) >= 2
        ORDER BY tier3 DESC, mr_count DESC
        LIMIT 15
    """)

    if not trainers:
        row("*No trainers with 2+ candidates in this window.*")
    else:
        row(f"| Trainer | MR | Tier3 | post_drop | full_restore | Horses |")
        row(f"|---|---|---|---|---|---|")
        for r in trainers:
            horses_str = ", ".join(r['horses'][:3])
            if len(r['horses']) > 3:
                horses_str += f" (+{len(r['horses'])-3})"
            row(f"| {r['trainer']} | {r['mr_count']} | {r['tier3']} | "
                f"{r['post_drop']} | {r['full_restore']} | {horses_str} |")

    # ── Doctrine footer ────────────────────────────────────────────────────────
    h("---")
    h("## Doctrine Reference")
    row("*VÉLØ Plot Doctrine v1 — Law: handicap movement + condition restoration = intent.*")
    row("*Single-theme flags are atmosphere. Multi-theme intersections are signal.*")
    row("*This report is a candidate queue, not a prediction. Verdicts require full live pipeline.*")
    row(f"*Source: intelligence.plot_candidate_flags_2025 | 5-table stack | 84,049 rows | 2025*")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--date",   default=None, help="Report end date YYYY-MM-DD (default: today)")
    parser.add_argument("--window", type=int, default=7, help="Days to cover (default: 7)")
    args = parser.parse_args()

    report_date = date.fromisoformat(args.date) if args.date else date.today()
    window = args.window

    print(f"Generating Plot Radar Report: {report_date.isoformat()} (window={window}d)...")

    report_md = generate_report(report_date, window)

    out_dir = Path("reports/plot_radar")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"plot_radar_{report_date.isoformat()}.md"

    out_path.write_text(report_md, encoding="utf-8")
    print(f"Written: {out_path}")

    # Quick count summary to stdout
    lines = report_md.split("\n")
    for line in lines:
        if "|" in line and ("Candidates" in line or "Tier 3" in line or "Distinct" in line):
            print(f"  {line.strip()}")


if __name__ == "__main__":
    main()
