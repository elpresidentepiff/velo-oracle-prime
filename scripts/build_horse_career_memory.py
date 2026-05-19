"""
Build horse career memory layer from all available VÉLØ signal history.

Sources:
  data/velo_unified_evidence_corpus_v1.csv  — 1310+ rows of signal + outcome
  data/features/rp_runner_profile_latest.parquet — current day RP profile
  data/features/runner_master_profile_latest.parquet — merged master profile

Outputs:
  data/features/horse_career_memory_latest.parquet
  data/reports/horse_career_memory_latest.md

Read-only. Does not mutate live state. Does not touch scoring.
"""

import json
import sys
import warnings
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")

ROOT = Path(__file__).resolve().parents[1]
CORPUS_PATH = ROOT / "data" / "velo_unified_evidence_corpus_v1.csv"
RP_PROFILE_PATH = ROOT / "data" / "features" / "rp_runner_profile_latest.parquet"
MASTER_PROFILE_PATH = ROOT / "data" / "features" / "runner_master_profile_latest.parquet"
OUT_PARQUET = ROOT / "data" / "features" / "horse_career_memory_latest.parquet"
OUT_MD = ROOT / "data" / "reports" / "horse_career_memory_latest.md"
OUT_MD.parent.mkdir(parents=True, exist_ok=True)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _safe_float(x) -> float | None:
    try:
        v = float(x)
        return None if np.isnan(v) else v
    except (TypeError, ValueError):
        return None


def _career_trajectory(starts: int, wins: int, frames: int,
                        or_delta: float | None, vp_trend: str) -> str:
    if starts == 0:
        return "UNKNOWN"
    if starts <= 4:
        return "EARLY_STAGE"
    win_rate = wins / starts
    frame_rate = frames / starts
    if or_delta is not None and or_delta >= 3:
        return "IMPROVING"
    if win_rate >= 0.25 and frame_rate >= 0.45:
        return "PLATEAU"
    if or_delta is not None and or_delta <= -5:
        return "REGRESSING"
    if starts >= 20 and win_rate < 0.10:
        return "EXPOSED"
    return "HANDICAP_PLOT"


# ── Load corpus ───────────────────────────────────────────────────────────────

def load_corpus() -> pd.DataFrame:
    df = pd.read_csv(CORPUS_PATH)
    safe = df[df["result_matched"] == True].copy()
    safe["date_parsed"] = pd.to_datetime(safe["date"], errors="coerce")
    safe = safe.dropna(subset=["date_parsed"]).sort_values("date_parsed")
    return safe


def load_rp_profile() -> pd.DataFrame | None:
    if RP_PROFILE_PATH.exists():
        return pd.read_parquet(RP_PROFILE_PATH)
    return None


def load_master_profile() -> pd.DataFrame | None:
    if MASTER_PROFILE_PATH.exists():
        return pd.read_parquet(MASTER_PROFILE_PATH)
    return None


# ── Build career rows ─────────────────────────────────────────────────────────

def build_career_memory(corpus: pd.DataFrame, rp: pd.DataFrame | None) -> pd.DataFrame:
    # Normalise horse identity for grouping
    # Use horse_id as primary key; fall back to horse_norm or horse
    corpus = corpus.copy()
    corpus["group_key"] = (
        corpus["horse_id"].fillna("")
        .where(corpus["horse_id"].notna() & (corpus["horse_id"] != ""), corpus["horse"].str.lower().str.strip())
    )

    records = []

    for group_key, grp in corpus.groupby("group_key"):
        grp = grp.sort_values("date_parsed")

        # Basic identity
        horse_ids = grp["horse_id"].dropna().unique().tolist()
        horse_names = grp["horse"].dropna().unique().tolist()

        # Career metrics
        starts = len(grp)
        wins = int(grp["won"].apply(lambda x: 1 if str(x).lower() in ("true", "1", "1.0") else 0).sum())
        frames = int(grp["placed"].apply(lambda x: 1 if str(x).lower() in ("true", "1", "1.0") else 0).sum())

        first_seen = str(grp["date_parsed"].min().date())
        last_seen = str(grp["date_parsed"].max().date())

        # Probability signals
        vp_vals = pd.to_numeric(grp["velo_prime_prob"], errors="coerce").dropna()
        sqpe_vals = pd.to_numeric(grp["sqpe_v17_prob"], errors="coerce").dropna()
        mds_vals = pd.to_numeric(grp["market_deception_score"], errors="coerce").dropna()
        impr_vals = pd.to_numeric(grp["improvement_score"], errors="coerce").dropna()
        place_vals = pd.to_numeric(grp["place_prob"], errors="coerce").dropna()

        avg_vp = _safe_float(vp_vals.mean())
        avg_mds = _safe_float(mds_vals.mean())
        avg_improvement = _safe_float(impr_vals.mean())

        # High-signal events
        mds_high_events = int((mds_vals > 0.50).sum())
        improvement_high_events = int((impr_vals > 0.40).sum())
        vp_ge_30_events = int((vp_vals >= 0.30).sum())
        vp_ge_40_events = int((vp_vals >= 0.40).sum())

        # Tier distribution
        tier_dist = grp["decision_tier"].value_counts().to_dict()

        # Router lane history
        lane_hist = grp["router_shadow_lane"].dropna().value_counts().to_dict()

        # VP trend (early vs late)
        vp_trend = "UNKNOWN"
        if len(vp_vals) >= 4:
            mid = len(vp_vals) // 2
            early_avg = vp_vals.iloc[:mid].mean()
            late_avg = vp_vals.iloc[mid:].mean()
            if late_avg > early_avg + 0.03:
                vp_trend = "RISING"
            elif late_avg < early_avg - 0.03:
                vp_trend = "FALLING"
            else:
                vp_trend = "STABLE"

        # RP profile enrichment (today's entry if horse in current profile)
        or_vals = []
        ts_vals = []
        rpr_vals = []
        age = None
        form_figures = None
        days_since_run = None
        course_winner = None
        dist_winner = None
        cd_winner = None
        juvenile_flag = False

        if rp is not None:
            # Match by horse_id or horse name normalisation
            for hid in horse_ids:
                rp_match = rp[rp["horse_id"] == hid] if "horse_id" in rp.columns else pd.DataFrame()
                if len(rp_match) == 0 and horse_names:
                    hn = horse_names[0].upper().strip()
                    rp_match = rp[rp.get("horse_norm", pd.Series()) == hn] if "horse_norm" in rp.columns else pd.DataFrame()
                if len(rp_match) > 0:
                    row = rp_match.iloc[0]
                    or_v = _safe_float(row.get("current_or"))
                    ts_v = _safe_float(row.get("current_ts"))
                    rpr_v = _safe_float(row.get("current_rpr"))
                    if or_v:
                        or_vals.append(or_v)
                    if ts_v:
                        ts_vals.append(ts_v)
                    if rpr_v:
                        rpr_vals.append(rpr_v)
                    age = _safe_float(row.get("age"))
                    form_figures = str(row.get("form_figures", "")) or None
                    days_since_run = _safe_float(row.get("days_since_run"))
                    course_winner = bool(row.get("course_winner", False))
                    dist_winner = bool(row.get("dist_winner", False))
                    cd_winner = bool(row.get("cd_winner", False))
                    if age and age <= 2:
                        juvenile_flag = True
                    break

        # OR progression across raceform (if multiple OR values are in corpus)
        or_delta = None
        if len(or_vals) >= 1 and or_vals[0] is not None:
            pass  # single RP snapshot — delta requires history

        # Trajectory
        trajectory = _career_trajectory(starts, wins, frames, or_delta, vp_trend)

        # Special flags
        second_run_improve = (
            starts == 2
            and wins == 0
            and frames >= 1
            and improvement_high_events >= 1
        )

        records.append({
            "group_key": group_key,
            "horse_id_primary": horse_ids[0] if horse_ids else None,
            "horse_ids_all": json.dumps(horse_ids),
            "horse_name": horse_names[0] if horse_names else group_key,
            "horse_names_all": json.dumps(horse_names),
            "first_seen": first_seen,
            "last_seen": last_seen,
            "starts_observed": starts,
            "wins_observed": wins,
            "frames_observed": frames,
            "win_rate": round(wins / starts, 4) if starts > 0 else None,
            "frame_rate": round(frames / starts, 4) if starts > 0 else None,
            # Age and run data from RP
            "age": age,
            "form_figures": form_figures,
            "days_since_run": days_since_run,
            "course_winner": course_winner,
            "dist_winner": dist_winner,
            "cd_winner": cd_winner,
            # Ratings (latest RP values)
            "current_or": or_vals[0] if or_vals else None,
            "current_ts": ts_vals[0] if ts_vals else None,
            "current_rpr": rpr_vals[0] if rpr_vals else None,
            "or_delta": or_delta,
            # Signal averages
            "avg_velo_prime_prob": avg_vp,
            "avg_market_deception_score": avg_mds,
            "avg_improvement_score": avg_improvement,
            # High-signal event counts
            "mds_high_events": mds_high_events,
            "improvement_high_events": improvement_high_events,
            "vp_ge_30_events": vp_ge_30_events,
            "vp_ge_40_events": vp_ge_40_events,
            # Tier and lane history
            "tier_distribution": json.dumps(tier_dist),
            "router_lane_history": json.dumps(lane_hist),
            # Trend
            "vp_trend": vp_trend,
            "career_trajectory": trajectory,
            # Special flags
            "juvenile_2yo_flag": juvenile_flag,
            "second_run_improve_flag": second_run_improve,
            # Metadata
            "built_at": datetime.now(timezone.utc).isoformat(),
        })

    return pd.DataFrame(records)


# ── Reports ───────────────────────────────────────────────────────────────────

def write_md(df: pd.DataFrame, n_corpus: int) -> None:
    total = len(df)
    improving = (df["career_trajectory"] == "IMPROVING").sum()
    early_stage = (df["career_trajectory"] == "EARLY_STAGE").sum()
    plateau = (df["career_trajectory"] == "PLATEAU").sum()
    regressing = (df["career_trajectory"] == "REGRESSING").sum()
    exposed = (df["career_trajectory"] == "EXPOSED").sum()
    juveniles = df["juvenile_2yo_flag"].sum()
    second_run = df["second_run_improve_flag"].sum()
    multi_mds = (df["mds_high_events"] >= 2).sum()

    lines = [
        "# VÉLØ HORSE CAREER MEMORY — LATEST",
        "",
        f"**Built:** {datetime.now(timezone.utc).isoformat()}  ",
        f"**Corpus rows:** {n_corpus}  ",
        f"**Unique horses:** {total}",
        "",
        "---",
        "",
        "## Career Trajectory Distribution",
        "",
        "| Trajectory | Count |",
        "|---|---|",
        f"| EARLY_STAGE | {early_stage} |",
        f"| IMPROVING | {improving} |",
        f"| PLATEAU | {plateau} |",
        f"| HANDICAP_PLOT | {(df['career_trajectory'] == 'HANDICAP_PLOT').sum()} |",
        f"| REGRESSING | {regressing} |",
        f"| EXPOSED | {exposed} |",
        f"| UNKNOWN | {(df['career_trajectory'] == 'UNKNOWN').sum()} |",
        "",
        "---",
        "",
        "## Special Flags",
        "",
        f"| Flag | Count |",
        f"|---|---|",
        f"| Juvenile/2yo | {juveniles} |",
        f"| Second-run improve candidate | {second_run} |",
        f"| MDS high ≥2 events | {multi_mds} |",
        f"| VP ≥ 0.40 at least once | {(df['vp_ge_40_events'] >= 1).sum()} |",
        "",
        "---",
        "",
        "## Top Horses by MDS High Events",
        "",
        "| Horse | Starts | W | F | MDS Events | VP≥0.40 | Trajectory |",
        "|---|---|---|---|---|---|---|",
    ]

    top_mds = df.nlargest(15, "mds_high_events")
    for _, r in top_mds.iterrows():
        lines.append(
            f"| {r['horse_name']} | {r['starts_observed']} | {r['wins_observed']} | "
            f"{r['frames_observed']} | {r['mds_high_events']} | "
            f"{r['vp_ge_40_events']} | {r['career_trajectory']} |"
        )

    lines += [
        "",
        "---",
        "",
        "## Governance",
        "",
        "```",
        "Read-only build. Does not mutate scoring, models, or live state.",
        "May feed back into VP scoring after operator approval.",
        "```",
    ]

    OUT_MD.write_text("\n".join(lines), encoding="utf-8")
    print(f"MD:      {OUT_MD}")


# ── Main ──────────────────────────────────────────────────────────────────────

def run():
    print("\nHORSE CAREER MEMORY BUILD")
    print("=" * 60)

    corpus = load_corpus()
    rp = load_rp_profile()
    print(f"Corpus rows (training-safe): {len(corpus)}")
    print(f"RP profile rows: {len(rp) if rp is not None else 0}")

    print("Building career memory...")
    df = build_career_memory(corpus, rp)
    print(f"Unique horses: {len(df)}")

    # Save parquet
    df.to_parquet(OUT_PARQUET, index=False)
    print(f"Parquet: {OUT_PARQUET}")

    write_md(df, len(corpus))

    # Summary
    print("\nCareer trajectory breakdown:")
    for traj, count in df["career_trajectory"].value_counts().items():
        print(f"  {traj:<25} {count}")

    print(f"\nJuveniles/2yo flag:         {df['juvenile_2yo_flag'].sum()}")
    print(f"Second-run improve:          {df['second_run_improve_flag'].sum()}")
    print(f"MDS high ≥2 events:          {(df['mds_high_events'] >= 2).sum()}")
    print("=" * 60)


if __name__ == "__main__":
    run()
