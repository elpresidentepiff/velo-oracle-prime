"""
VÉLØ RPDC Horse Tagger — builds a per-horse tag profile from career memory + corpus.

Tags assigned (not mutually exclusive):
  DEBUT_OR_EARLY_STAGE    — ≤4 observed starts
  SECOND_RUN_WATCH        — exactly 2 starts, improvement_high event on run 2
  THIRD_RUN_WATCH         — exactly 3 starts, no win yet, improvement signal present
  IMPROVER_PROFILE        — improvement_high_events ≥ 2 across career
  HANDICAP_COMPRESSION    — trajectory=HANDICAP_PLOT + mds_high_events ≥ 1
  MDS_HISTORY             — any mds_high_event (market deception > 0.5) observed
  VP40_HISTORY            — any vp_ge_40_event observed
  CASHRUN_HISTORY         — mds_high_events ≥ 2 (multiple market deception signals)
  RP_CONVERGENCE_HISTORY  — improvement + mds both high at least once
  EXPOSED_PROFILE         — trajectory=EXPOSED
  REGRESSION_RISK         — trajectory=REGRESSING or (win_rate < 0.08 and starts ≥ 15)
  RETURNING_RUNNER        — days_since_run ≥ 90 (if current RP profile available)
  JUVENILE                — juvenile_2yo_flag=True

Outputs:
  data/features/rpdc_horse_tags_latest.json
  data/features/rpdc_horse_tags_latest.parquet
  data/reports/rpdc_horse_tags_latest.md

Read-only. Does not modify scoring, routing, or live state.
"""

import json
import warnings
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

warnings.filterwarnings("ignore")

ROOT = Path(__file__).resolve().parents[1]
CAREER_MEMORY_PATH = ROOT / "data" / "features" / "horse_career_memory_latest.parquet"
OUT_JSON = ROOT / "data" / "features" / "rpdc_horse_tags_latest.json"
OUT_PARQUET = ROOT / "data" / "features" / "rpdc_horse_tags_latest.parquet"
OUT_MD = ROOT / "data" / "reports" / "rpdc_horse_tags_latest.md"
OUT_MD.parent.mkdir(parents=True, exist_ok=True)


# ── Tagging logic ──────────────────────────────────────────────────────────────

def assign_tags(row: pd.Series) -> list[str]:
    tags = []
    starts = int(row.get("starts_observed", 0) or 0)
    wins = int(row.get("wins_observed", 0) or 0)
    mds_hi = int(row.get("mds_high_events", 0) or 0)
    impr_hi = int(row.get("improvement_high_events", 0) or 0)
    vp40 = int(row.get("vp_ge_40_events", 0) or 0)
    traj = str(row.get("career_trajectory", "") or "")
    juvenile = bool(row.get("juvenile_2yo_flag", False))
    second_run = bool(row.get("second_run_improve_flag", False))
    third_run = bool(row.get("third_run_candidate_flag", False))
    returning = bool(row.get("returning_horse_flag", False))
    win_rate = float(row.get("win_rate", 0) or 0)

    # Early stage / debut
    if starts <= 4:
        tags.append("DEBUT_OR_EARLY_STAGE")

    # Second and third run watch
    if second_run:
        tags.append("SECOND_RUN_WATCH")
    if third_run:
        tags.append("THIRD_RUN_WATCH")

    # Improver profile — multiple improvement signals across career
    if impr_hi >= 2:
        tags.append("IMPROVER_PROFILE")

    # Handicap compression — sits in the handicap plot with market deception history
    if traj == "HANDICAP_PLOT" and mds_hi >= 1:
        tags.append("HANDICAP_COMPRESSION")

    # Market deception history
    if mds_hi >= 1:
        tags.append("MDS_HISTORY")

    # VP40 history — ever fired at VP≥0.40
    if vp40 >= 1:
        tags.append("VP40_HISTORY")

    # Cash run history — multiple MDS high events (repeated pattern)
    if mds_hi >= 2:
        tags.append("CASHRUN_HISTORY")

    # RP convergence — improvement + MDS both triggered at some point
    if impr_hi >= 1 and mds_hi >= 1:
        tags.append("RP_CONVERGENCE_HISTORY")

    # Exposed profile — identified as limited
    if traj == "EXPOSED":
        tags.append("EXPOSED_PROFILE")

    # Regression risk
    if traj == "REGRESSING" or (starts >= 15 and win_rate < 0.08):
        tags.append("REGRESSION_RISK")

    # Returning runner
    if returning:
        tags.append("RETURNING_RUNNER")

    # Juvenile
    if juvenile:
        tags.append("JUVENILE")

    return tags


# ── Main ──────────────────────────────────────────────────────────────────────

def run():
    print("\nRPDC HORSE TAGGER")
    print("=" * 60)

    if not CAREER_MEMORY_PATH.exists():
        print(f"ERROR: Career memory not found at {CAREER_MEMORY_PATH}")
        print("Run scripts/build_horse_career_memory.py first.")
        return

    df = pd.read_parquet(CAREER_MEMORY_PATH)
    print(f"Career memory rows: {len(df)}")

    tag_records = []
    tag_freq: dict[str, int] = {}

    for _, row in df.iterrows():
        tags = assign_tags(row)
        for t in tags:
            tag_freq[t] = tag_freq.get(t, 0) + 1
        tag_records.append({
            "horse_id": row.get("horse_id_primary"),
            "group_key": row.get("group_key"),
            "horse_name": row.get("horse_name"),
            "career_trajectory": row.get("career_trajectory"),
            "starts_observed": row.get("starts_observed"),
            "wins_observed": row.get("wins_observed"),
            "mds_high_events": row.get("mds_high_events"),
            "improvement_high_events": row.get("improvement_high_events"),
            "vp_ge_40_events": row.get("vp_ge_40_events"),
            "tags": json.dumps(sorted(tags)),
            "tag_count": len(tags),
            "tagged_at": datetime.now(timezone.utc).isoformat(),
        })

    out_df = pd.DataFrame(tag_records)
    out_df.to_parquet(OUT_PARQUET, index=False)
    print(f"Parquet: {OUT_PARQUET}")

    print("\nTag frequency:")
    for tag, count in sorted(tag_freq.items(), key=lambda x: -x[1]):
        pct = count / len(df) * 100
        print(f"  {tag:<35} {count:>5} ({pct:.1f}%)")

    # JSON summary
    summary = {
        "built_at": datetime.now(timezone.utc).isoformat(),
        "total_horses": len(df),
        "tag_frequency": {k: {"count": v, "pct": round(v / len(df) * 100, 1)}
                          for k, v in sorted(tag_freq.items(), key=lambda x: -x[1])},
        "governance": {
            "read_only": True,
            "no_scoring_change": True,
            "no_live_state_mutation": True,
            "feeds_into_scoring": "PENDING_OPERATOR_APPROVAL",
        },
    }
    OUT_JSON.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(f"JSON:    {OUT_JSON}")

    _write_md(summary, out_df)
    print(f"MD:      {OUT_MD}")
    print("=" * 60)


def _write_md(summary: dict, df: pd.DataFrame) -> None:
    freq = summary["tag_frequency"]
    lines = [
        "# VÉLØ RPDC HORSE TAGS — LATEST",
        "",
        f"**Built:** {summary['built_at']}  ",
        f"**Total horses:** {summary['total_horses']}",
        "",
        "---",
        "",
        "## Tag Frequency",
        "",
        "| Tag | Count | % Horses |",
        "|---|---|---|",
    ]
    for tag, info in freq.items():
        lines.append(f"| {tag} | {info['count']} | {info['pct']}% |")

    lines += ["", "---", "", "## Tag Definitions", "",
              "| Tag | Trigger |",
              "|---|---|",
              "| DEBUT_OR_EARLY_STAGE | ≤4 observed starts |",
              "| SECOND_RUN_WATCH | 2 starts, improvement high event on run 2 |",
              "| THIRD_RUN_WATCH | 3 starts, no win, improvement signal |",
              "| IMPROVER_PROFILE | improvement_high_events ≥ 2 across career |",
              "| HANDICAP_COMPRESSION | HANDICAP_PLOT trajectory + MDS high ≥ 1 |",
              "| MDS_HISTORY | Any market_deception_score > 0.50 event observed |",
              "| VP40_HISTORY | Any velo_prime_prob ≥ 0.40 event observed |",
              "| CASHRUN_HISTORY | mds_high_events ≥ 2 (repeated pattern) |",
              "| RP_CONVERGENCE_HISTORY | Both improvement + MDS high events observed |",
              "| EXPOSED_PROFILE | trajectory=EXPOSED |",
              "| REGRESSION_RISK | REGRESSING trajectory or win_rate<0.08 at ≥15 starts |",
              "| RETURNING_RUNNER | days_since_run ≥ 90 (RP profile required) |",
              "| JUVENILE | juvenile_2yo_flag=True |"]

    lines += [
        "",
        "---",
        "",
        "## Top Horses by Tag Count",
        "",
        "| Horse | Tags | Trajectory |",
        "|---|---|---|",
    ]
    for _, r in df.nlargest(15, "tag_count").iterrows():
        tags = json.loads(r["tags"]) if r["tags"] else []
        lines.append(f"| {r['horse_name']} | {', '.join(tags)} | {r['career_trajectory']} |")

    lines += [
        "",
        "---",
        "",
        "## Governance",
        "",
        "```",
        "Read-only build. Tags are diagnostic only.",
        "Does not modify scoring, routing, or live state.",
        "Feeds into next-day VP scoring after operator approval.",
        "```",
    ]
    OUT_MD.write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    run()
