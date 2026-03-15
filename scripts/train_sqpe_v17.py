#!/usr/bin/env python3
"""
VÉLØ Oracle — SQPE v17 Trainer
================================
v16 base (19 features) + 18 doctrine features derived from per-horse lookback.

New feature groups:
  Release/plot  : runs_since_win, runs_since_place, runs_since_mkt_support,
                  current_or_minus_last_win_or, current_or_minus_best_or,
                  mark_compression_score, release_window_score
  Fit           : course_fit_score, going_fit_score, distance_fit_score
  Intent        : quiet_run_score, trainer_timing_score,
                  jockey_switch_intent_score
  Market        : odds_resilience_score, odds_contraction_score,
                  decoy_support_flag
  Execution     : setup_run_flag, cash_run_flag

Usage:
    python scripts/train_sqpe_v17.py
    python scripts/train_sqpe_v17.py --sample 40000   # quick dev run
    python scripts/train_sqpe_v17.py --no-backtest     # 2024-2025 only
"""

import json
import pickle
import argparse
import re
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.calibration import CalibratedClassifierCV
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.metrics import roc_auc_score, log_loss, classification_report

# ─────────────────────────────────────────────────────────
# Column schema for JSON-lines raw text file
# ─────────────────────────────────────────────────────────
COLS = [
    "date", "course", "race_id", "off", "race_name", "type", "class_raw",
    "pattern", "rating_band", "age_band", "sex_rest", "dist", "going",
    "ran", "num", "pos", "draw", "ovr_btn", "btn", "horse", "age", "sex",
    "wgt", "hg", "time", "sp", "jockey", "trainer", "prize",
    "or_rating", "rpr", "ts", "sire", "dam", "damsire", "owner", "comment",
]

EXCLUDE_PATTERNS = re.compile(
    r"\(HK\)|\(AUS\)|\(USA\)|\(FR\)|\(GER\)|\(ITY\)|\(UAE\)|\(JPN\)|"
    r"Sha Tin|Happy Valley|Randwick|Flemington|Moonee|Caulfield|"
    r"Longchamp|Chantilly|Deauville|ParisLongchamp|Meydan|Nad Al Sheba",
    re.IGNORECASE,
)


# ─────────────────────────────────────────────────────────
# Parsers (identical to v16)
# ─────────────────────────────────────────────────────────
def parse_sp(sp_str):
    if not sp_str or str(sp_str).strip() in ("", "–", "-", "nan"):
        return np.nan
    s = str(sp_str).strip().upper().rstrip("F").rstrip("J").strip()
    if s in ("EVENS", "EVS"):
        return 2.0
    m = re.match(r"^(\d+(?:\.\d+)?)/(\d+(?:\.\d+)?)$", s)
    if m:
        return float(m.group(1)) / float(m.group(2)) + 1.0
    try:
        return float(s) + 1.0
    except ValueError:
        return np.nan


def parse_dist(dist_str):
    if not dist_str:
        return np.nan
    s = str(dist_str).strip().lower()
    total = 0.0
    m_miles = re.search(r"(\d+(?:\.\d+)?)m", s)
    m_furlongs = re.search(r"(\d+(?:\.\d+)?)f", s)
    m_yards = re.search(r"(\d+)y", s)
    if m_miles:
        total += float(m_miles.group(1)) * 8
    if m_furlongs:
        total += float(m_furlongs.group(1))
    if m_yards:
        total += float(m_yards.group(1)) / 220
    return total if total > 0 else np.nan


def parse_going(going_str):
    if not going_str:
        return 0.0, 0
    g = str(going_str).strip().upper()
    aw = 1 if any(x in g for x in ["STANDARD", "SLOW", "FAST", "TAPETA", "POLYTRACK", "FIBRESAND"]) else 0
    codes = {
        "FIRM": 2.0, "GOOD TO FIRM": 1.5, "GOOD": 1.0, "GOOD TO SOFT": 0.5,
        "SOFT": 0.0, "HEAVY": -1.0, "YIELDING": 0.3, "YIELDING TO SOFT": 0.1,
        "STANDARD": 1.0, "STANDARD TO SLOW": 0.5, "SLOW": 0.0, "FAST": 1.5,
    }
    for key, val in codes.items():
        if key in g:
            return val, aw
    return 0.5, aw


def going_bucket(going_str):
    """Map going to broad bucket: 0=fast/AW, 1=good, 2=soft, 3=heavy"""
    if not going_str:
        return 1
    g = str(going_str).strip().upper()
    if any(x in g for x in ["STANDARD", "FAST", "TAPETA", "POLYTRACK", "FIBRESAND"]):
        return 0
    if "HEAVY" in g or "VERY SOFT" in g:
        return 3
    if "SOFT" in g or "YIELD" in g:
        return 2
    return 1  # good / firm


def parse_class(class_str):
    if not class_str:
        return np.nan
    s = str(class_str).strip().upper()
    m = re.search(r"CLASS\s*(\d)", s)
    if m:
        return float(m.group(1))
    if "GROUP 1" in s or "GRADE 1" in s:
        return 1.0
    if "GROUP 2" in s or "GRADE 2" in s:
        return 2.0
    if "GROUP 3" in s or "GRADE 3" in s:
        return 3.0
    if "LISTED" in s:
        return 2.5
    return np.nan


def parse_wgt(wgt_str):
    if not wgt_str:
        return np.nan
    s = str(wgt_str).strip()
    m = re.match(r"(\d+)-(\d+)", s)
    if m:
        return float(m.group(1)) * 14 + float(m.group(2))
    try:
        return float(s)
    except ValueError:
        return np.nan


def parse_numeric(val):
    if val is None:
        return np.nan
    s = str(val).strip()
    if s in ("", "–", "-", "nan"):
        return np.nan
    try:
        return float(s)
    except ValueError:
        return np.nan


# ─────────────────────────────────────────────────────────
# v16 features (19) — identical to v16 trainer
# ─────────────────────────────────────────────────────────
V16_FEATURES = [
    "sp_dec", "log_sp", "implied_prob",
    "dist_f", "going_code", "is_aw",
    "class_num", "wgt_lbs",
    "or_num", "rpr_num", "ts_num",
    "or_vs_field", "rpr_vs_field",
    "field_size", "draw_num", "draw_pct",
    "age_num", "sp_rank", "is_fav",
]

V17_DOCTRINE_FEATURES = [
    # Release / plot
    "runs_since_win",
    "runs_since_place",
    "runs_since_mkt_support",
    "curr_or_minus_last_win_or",
    "curr_or_minus_best_or",
    "mark_compression_score",
    "release_window_score",
    # Fit
    "course_fit_score",
    "going_fit_score",
    "distance_fit_score",
    # Intent
    "quiet_run_score",
    "trainer_timing_score",
    "jockey_switch_intent",
    # Market behaviour
    "odds_resilience_score",
    "odds_contraction_score",
    "decoy_support_flag",
    # Execution
    "setup_run_flag",
    "cash_run_flag",
]

ALL_FEATURES = V16_FEATURES + V17_DOCTRINE_FEATURES  # 37 total


# ─────────────────────────────────────────────────────────
# v16 feature engineering (base layer)
# ─────────────────────────────────────────────────────────
def engineer_v16_features(df):
    df = df.copy()
    df["target"] = (df["pos"].astype(str).str.strip() == "1").astype(int)
    df["sp_dec"] = df["sp"].apply(parse_sp)
    df["log_sp"] = np.log(df["sp_dec"].clip(1.01, 200))
    df["implied_prob"] = 1.0 / df["sp_dec"].clip(1.01, 200)
    df["dist_f"] = df["dist"].apply(parse_dist)
    going_parsed = df["going"].apply(parse_going)
    df["going_code"] = going_parsed.apply(lambda x: x[0])
    df["is_aw"] = going_parsed.apply(lambda x: x[1])
    df["class_num"] = df["class_raw"].apply(parse_class)
    df["wgt_lbs"] = df["wgt"].apply(parse_wgt)
    df["or_num"] = df["or_rating"].apply(parse_numeric)
    df["rpr_num"] = df["rpr"].apply(parse_numeric)
    df["ts_num"] = df["ts"].apply(parse_numeric)
    df["field_size"] = pd.to_numeric(df["ran"], errors="coerce")
    df["draw_num"] = pd.to_numeric(df["draw"], errors="coerce")
    df["draw_pct"] = df["draw_num"] / df["field_size"].clip(1)
    df["age_num"] = pd.to_numeric(df["age"], errors="coerce")
    df["or_num_safe"] = df["or_num"].fillna(df["or_num"].median())
    df["or_vs_field"] = df.groupby("race_id")["or_num_safe"].transform(lambda x: x - x.mean())
    df["rpr_safe"] = df["rpr_num"].fillna(df["rpr_num"].median())
    df["rpr_vs_field"] = df.groupby("race_id")["rpr_safe"].transform(lambda x: x - x.mean())
    df["sp_rank"] = df.groupby("race_id")["sp_dec"].rank(method="min", ascending=True)
    df["is_fav"] = (df["sp_rank"] == 1).astype(int)
    return df


# ─────────────────────────────────────────────────────────
# v17 doctrine feature computation (lookback per horse)
# ─────────────────────────────────────────────────────────
def _runs_since_event(events: np.ndarray) -> np.ndarray:
    """
    For each position i, return count of runs since the last event=1 in [0..i-1].
    Returns NaN if no prior event.
    """
    n = len(events)
    result = np.full(n, np.nan)
    last_event = -1
    for i in range(n):
        if last_event >= 0:
            result[i] = float(i - last_event - 1)
        if events[i] == 1:
            last_event = i
    return result


def _cumulative_fit_score(values: np.ndarray, match_mask: np.ndarray,
                          wins: np.ndarray, places: np.ndarray) -> np.ndarray:
    """
    Cumulative (wins+places)/starts where match_mask=True, for each row using only prior rows.
    Laplace smoothing: start with (1 win + 1 place) / 4 starts = 0.5 default.
    """
    n = len(values)
    result = np.full(n, np.nan)
    cum_starts = 0
    cum_wins_places = 0
    for i in range(n):
        if cum_starts > 0:
            result[i] = cum_wins_places / cum_starts
        # Update with this row (but only count if same condition)
        if match_mask[i]:
            cum_starts += 1
            cum_wins_places += wins[i] + places[i]
    return result


def engineer_v17_doctrine(df: pd.DataFrame) -> pd.DataFrame:
    """
    Compute 18 v17 doctrine features using per-horse lookback.
    Requires the dataframe to already have: or_num, sp_dec, dist_f, going, course,
    target (is_win), jockey, trainer, ovr_btn, is_fav.
    Must be sorted by (horse, date) before calling.
    """
    df = df.copy()

    # Derived helpers
    df["is_place"] = (pd.to_numeric(df["pos"].astype(str).str.strip(), errors="coerce").fillna(99) <= 3).astype(int)
    df["going_bkt"] = df["going"].apply(going_bucket)
    df["sp_dec_safe"] = df["sp_dec"].fillna(10.0)
    df["is_mkt_support"] = (df["sp_dec_safe"] < 3.5).astype(int)  # backed at <5/2
    df["ovr_btn_num"] = pd.to_numeric(df["ovr_btn"], errors="coerce").fillna(0.0)

    # Group by horse, sorted chronologically
    groups = df.groupby("horse", sort=False)

    runs_since_win_vals = np.full(len(df), np.nan)
    runs_since_place_vals = np.full(len(df), np.nan)
    runs_since_mkt_support_vals = np.full(len(df), np.nan)
    curr_or_minus_last_win_or_vals = np.full(len(df), np.nan)
    curr_or_minus_best_or_vals = np.full(len(df), np.nan)
    mark_compression_vals = np.full(len(df), np.nan)
    release_window_vals = np.full(len(df), 0.0)
    course_fit_vals = np.full(len(df), np.nan)
    going_fit_vals = np.full(len(df), np.nan)
    dist_fit_vals = np.full(len(df), np.nan)
    quiet_run_vals = np.full(len(df), 0.0)
    trainer_timing_vals = np.full(len(df), np.nan)
    jockey_switch_vals = np.full(len(df), 0.0)
    odds_resilience_vals = np.full(len(df), np.nan)
    odds_contraction_vals = np.full(len(df), 0.0)
    decoy_support_vals = np.full(len(df), 0.0)
    setup_run_vals = np.full(len(df), 0.0)
    cash_run_vals = np.full(len(df), 0.0)

    idx_arr = df.index.to_numpy()
    pos_arr = np.searchsorted(idx_arr, idx_arr)  # 0-based positions in df

    # Build index: original_index → row_number
    orig_to_row = {orig: row for row, orig in enumerate(idx_arr)}

    for horse_name, group in groups:
        gidx = group.index.to_numpy()  # original indices of this horse's rows
        row_positions = np.array([orig_to_row[i] for i in gidx])  # positions in df arrays

        n = len(gidx)
        if n == 0:
            continue

        g_target = group["target"].values
        g_is_place = group["is_place"].values
        g_is_mkt_support = group["is_mkt_support"].values
        g_or = group["or_num"].values
        g_sp = group["sp_dec_safe"].values
        g_course = group["course"].values
        g_going_bkt = group["going_bkt"].values
        g_dist = group["dist_f"].values
        g_jockey = group["jockey"].values
        g_trainer = group["trainer"].values
        g_ovr_btn = group["ovr_btn_num"].values
        g_is_fav = group["is_fav"].values

        # ── runs_since_win / place / mkt_support ──
        rsw = _runs_since_event(g_target)
        rsp = _runs_since_event(g_is_place)
        rsm = _runs_since_event(g_is_mkt_support)

        # ── OR mark features ──
        curr_minus_lwor = np.full(n, np.nan)
        curr_minus_bor = np.full(n, np.nan)
        mark_comp = np.full(n, np.nan)
        last_win_or = np.nan
        best_or = np.nan
        for i in range(n):
            cor = g_or[i] if not np.isnan(g_or[i] if not (g_or[i] != g_or[i]) else np.nan) else np.nan
            # check nan
            cor = float(g_or[i]) if not (g_or[i] != g_or[i]) else np.nan
            if not np.isnan(cor):
                if not np.isnan(last_win_or):
                    curr_minus_lwor[i] = cor - last_win_or
                if not np.isnan(best_or) and best_or > 0:
                    curr_minus_bor[i] = cor - best_or
                    mark_comp[i] = (best_or - cor) / best_or
                best_or = cor if np.isnan(best_or) else max(cor, best_or)
            if g_target[i] == 1 and not np.isnan(cor):
                last_win_or = cor

        # ── course / going / distance fit ──
        cf_scores = np.full(n, np.nan)
        gf_scores = np.full(n, np.nan)
        df_scores = np.full(n, np.nan)
        c_win_place = 0; c_starts = 0
        g_win_place = 0; g_starts = 0
        d_win_place = 0; d_starts = 0

        for i in range(n):
            this_course = g_course[i]
            this_going_bkt = g_going_bkt[i]
            this_dist = g_dist[i]
            wp = g_target[i] + g_is_place[i]  # 0, 1, or 2

            # Course fit: from prior runs at same course
            same_course_prior_wp = 0; same_course_prior_s = 0
            same_going_prior_wp = 0; same_going_prior_s = 0
            same_dist_prior_wp = 0; same_dist_prior_s = 0

            for j in range(i):  # prior runs only
                jwp = g_target[j] + g_is_place[j]
                if g_course[j] == this_course:
                    same_course_prior_wp += jwp
                    same_course_prior_s += 1
                if g_going_bkt[j] == this_going_bkt:
                    same_going_prior_wp += jwp
                    same_going_prior_s += 1
                if not np.isnan(g_dist[j]) and not np.isnan(this_dist):
                    dist_lo = this_dist * 0.8
                    dist_hi = this_dist * 1.2
                    if dist_lo <= g_dist[j] <= dist_hi:
                        same_dist_prior_wp += jwp
                        same_dist_prior_s += 1

            if same_course_prior_s > 0:
                cf_scores[i] = same_course_prior_wp / same_course_prior_s
            if same_going_prior_s > 0:
                gf_scores[i] = same_going_prior_wp / same_going_prior_s
            if same_dist_prior_s > 0:
                df_scores[i] = same_dist_prior_wp / same_dist_prior_s

        # ── release_window_score ──
        # Horse that hasn't won in 3-10 runs but mark has compressed (dropped OR)
        rel_window = np.full(n, 0.0)
        for i in range(n):
            rsw_i = rsw[i]
            mc_i = mark_comp[i]
            if not np.isnan(rsw_i) and not np.isnan(mc_i):
                if 3.0 <= rsw_i <= 10.0 and mc_i > 0.05:
                    # In the window (3-10 runs no win) + mark compressed 5%+ = release candidate
                    rel_window[i] = min(1.0, mc_i * 5.0)

        # ── quiet_run_score ──
        # Last run was a hard beating (ovr_btn > 12) = prep-run signal
        quiet = np.full(n, 0.0)
        for i in range(1, n):
            if g_ovr_btn[i - 1] > 12.0:
                quiet[i] = min(1.0, (g_ovr_btn[i - 1] - 12.0) / 20.0)

        # ── trainer_timing_score ── (cumulative win rate for this trainer before this run)
        # We approximate with global cumulative because time-windowed rolling is expensive here
        trainer_timing = np.full(n, np.nan)
        tr_wins = 0; tr_starts = 0
        for i in range(n):
            if tr_starts > 0:
                trainer_timing[i] = tr_wins / tr_starts
            tr_starts += 1
            tr_wins += g_target[i]

        # ── jockey_switch_intent ──
        # 1.0 if jockey changed from last run, 0.0 if same
        jockey_switch = np.full(n, 0.0)
        for i in range(1, n):
            if g_jockey[i] != g_jockey[i - 1] and g_jockey[i - 1] != "":
                jockey_switch[i] = 1.0

        # ── odds_resilience_score ──
        # Std dev of SP over last 3 runs (lower = more consistent = more predictable)
        odds_resi = np.full(n, np.nan)
        for i in range(2, n):
            window = g_sp[max(0, i - 3):i]
            if len(window) >= 2:
                odds_resi[i] = np.std(window)

        # ── odds_contraction_score ──
        # SP shortened from last run (positive = shortened, negative = drifted)
        odds_cont = np.full(n, 0.0)
        for i in range(1, n):
            if g_sp[i - 1] > 0:
                odds_cont[i] = (g_sp[i - 1] - g_sp[i]) / g_sp[i - 1]

        # ── decoy_support_flag ──
        # Fav with cold trainer (trainer cumulative win rate < 8%) = market decoy risk
        decoy = np.full(n, 0.0)
        for i in range(n):
            if g_is_fav[i] == 1:
                tt = trainer_timing[i]
                if not np.isnan(tt) and tt < 0.08:
                    decoy[i] = 1.0

        # ── setup_run_flag ──
        # Last run was a heavy beating (>15 btn) = setup run pattern
        setup = np.full(n, 0.0)
        for i in range(1, n):
            if g_ovr_btn[i - 1] > 15.0:
                setup[i] = 1.0

        # ── cash_run_flag ──
        # Trainer in form + not won recently (3-6 runs) + mark dropped = targeting this race
        cash = np.full(n, 0.0)
        for i in range(n):
            tt = trainer_timing[i]
            rsw_i = rsw[i]
            mc_i = mark_comp[i]
            if (not np.isnan(tt) and tt > 0.15
                    and not np.isnan(rsw_i) and 3.0 <= rsw_i <= 6.0
                    and not np.isnan(mc_i) and mc_i > 0.0):
                cash[i] = 1.0

        # ── Write results back ──
        for ii, rp in enumerate(row_positions):
            runs_since_win_vals[rp] = rsw[ii]
            runs_since_place_vals[rp] = rsp[ii]
            runs_since_mkt_support_vals[rp] = rsm[ii]
            curr_or_minus_last_win_or_vals[rp] = curr_minus_lwor[ii]
            curr_or_minus_best_or_vals[rp] = curr_minus_bor[ii]
            mark_compression_vals[rp] = mark_comp[ii]
            release_window_vals[rp] = rel_window[ii]
            course_fit_vals[rp] = cf_scores[ii]
            going_fit_vals[rp] = gf_scores[ii]
            dist_fit_vals[rp] = df_scores[ii]
            quiet_run_vals[rp] = quiet[ii]
            trainer_timing_vals[rp] = trainer_timing[ii]
            jockey_switch_vals[rp] = jockey_switch[ii]
            odds_resilience_vals[rp] = odds_resi[ii]
            odds_contraction_vals[rp] = odds_cont[ii]
            decoy_support_vals[rp] = decoy[ii]
            setup_run_vals[rp] = setup[ii]
            cash_run_vals[rp] = cash[ii]

    df["runs_since_win"] = runs_since_win_vals
    df["runs_since_place"] = runs_since_place_vals
    df["runs_since_mkt_support"] = runs_since_mkt_support_vals
    df["curr_or_minus_last_win_or"] = curr_or_minus_last_win_or_vals
    df["curr_or_minus_best_or"] = curr_or_minus_best_or_vals
    df["mark_compression_score"] = mark_compression_vals
    df["release_window_score"] = release_window_vals
    df["course_fit_score"] = course_fit_vals
    df["going_fit_score"] = going_fit_vals
    df["distance_fit_score"] = dist_fit_vals
    df["quiet_run_score"] = quiet_run_vals
    df["trainer_timing_score"] = trainer_timing_vals
    df["jockey_switch_intent"] = jockey_switch_vals
    df["odds_resilience_score"] = odds_resilience_vals
    df["odds_contraction_score"] = odds_contraction_vals
    df["decoy_support_flag"] = decoy_support_vals
    df["setup_run_flag"] = setup_run_vals
    df["cash_run_flag"] = cash_run_vals

    return df


# ─────────────────────────────────────────────────────────
# Data loading (identical to v16)
# ─────────────────────────────────────────────────────────
def load_backtest_csv(path):
    print(f"  Loading {path} ...")
    df = pd.read_csv(path, low_memory=False)
    df = df.rename(columns={"class": "class_raw", "or": "or_rating"})
    if "race_id" not in df.columns:
        df["race_id"] = df.get("course", "unk") + "_" + df.get("off", "0") + "_" + df.get("date", "0")
    print(f"  {len(df):,} rows loaded")
    return df


def load_raw_txt(path, max_rows=None):
    print(f"  Loading {path} (UK/IRE filter) ...")
    rows = []
    with open(path, "r", encoding="utf-8") as fh:
        for i, line in enumerate(fh):
            if max_rows and i >= max_rows:
                break
            line = line.strip()
            if not line:
                continue
            try:
                arr = json.loads(line)
                if len(arr) < len(COLS):
                    arr += [""] * (len(COLS) - len(arr))
                row = dict(zip(COLS, arr[: len(COLS)]))
                if EXCLUDE_PATTERNS.search(str(row.get("course", ""))):
                    continue
                rows.append(row)
            except Exception:
                continue
    df = pd.DataFrame(rows)
    print(f"  {len(df):,} UK/IRE rows loaded")
    return df


# ─────────────────────────────────────────────────────────
# Main training pipeline
# ─────────────────────────────────────────────────────────
def train(backtest_path, raw_path, output_dir, sample_size=None, no_backtest=False):
    print("=" * 65)
    print("VÉLØ — SQPE v17 Training  (v16 base + 18 doctrine features)")
    print("=" * 65)

    frames = []
    if not no_backtest and Path(backtest_path).exists():
        df_bt = load_backtest_csv(backtest_path)
        df_bt["data_source"] = "backtest_2015"
        frames.append(df_bt)
    if Path(raw_path).exists():
        df_raw = load_raw_txt(raw_path, max_rows=sample_size * 4 if sample_size else None)
        df_raw["data_source"] = "real_2024_2025"
        frames.append(df_raw)
    else:
        print(f"  ERROR: {raw_path} not found")
        return

    df = pd.concat(frames, ignore_index=True)
    print(f"\nTotal combined rows: {len(df):,}")

    # Remove non-starters, DSQ, PU etc.
    df = df[pd.to_numeric(df["pos"].astype(str).str.strip(), errors="coerce").notna()]
    print(f"After removing non-runners/DSQ: {len(df):,} rows")

    if sample_size:
        df = df.sample(n=min(sample_size, len(df)), random_state=42)
        print(f"Sampled to: {len(df):,} rows")

    # ── v16 feature engineering ──
    print("\nEngineering v16 base features ...")
    df = engineer_v16_features(df)

    # ── Sort for chronological lookback before v17 computation ──
    print("Sorting chronologically for v17 lookback ...")
    df["date_parsed"] = pd.to_datetime(df["date"], errors="coerce")
    df = df.sort_values(["horse", "date_parsed"]).reset_index(drop=True)

    # ── v17 doctrine features ──
    print("Computing v17 doctrine features (per-horse lookback) ...")
    print("  This processes", df["horse"].nunique(), "unique horses ...")
    df = engineer_v17_doctrine(df)

    # ── Restore race-level ordering for train/test split ──
    df = df.sort_values("date_parsed").reset_index(drop=True)

    X_v16 = df[V16_FEATURES].fillna(0)
    X_v17 = df[ALL_FEATURES].fillna(0)
    y = df["target"]

    print(f"\nWin rate: {y.mean():.4f}  ({y.sum():,} winners / {len(y):,} runners)")
    print(f"v16 features: {len(V16_FEATURES)}")
    print(f"v17 features: {len(ALL_FEATURES)}")

    # Time-based split (last 20% = test)
    split_idx = int(len(df) * 0.8)
    Xv16_train, Xv16_test = X_v16.iloc[:split_idx], X_v16.iloc[split_idx:]
    Xv17_train, Xv17_test = X_v17.iloc[:split_idx], X_v17.iloc[split_idx:]
    y_train, y_test = y.iloc[:split_idx], y.iloc[split_idx:]

    print(f"Train: {len(y_train):,} | Test: {len(y_test):,}")

    # ── Train v17 ──
    print("\nTraining SQPE v17 (GBM + isotonic calibration) ...")
    model_v17 = CalibratedClassifierCV(
        GradientBoostingClassifier(
            n_estimators=300, learning_rate=0.05, max_depth=5,
            min_samples_split=80, min_samples_leaf=40,
            subsample=0.8, max_features="sqrt", random_state=42,
        ),
        method="isotonic", cv=3,
    )
    model_v17.fit(Xv17_train, y_train)

    # ── Train v16 baseline (for comparison on same split) ──
    print("Training v16 baseline on same split for fair AUC comparison ...")
    model_v16_baseline = CalibratedClassifierCV(
        GradientBoostingClassifier(
            n_estimators=300, learning_rate=0.05, max_depth=5,
            min_samples_split=80, min_samples_leaf=40,
            subsample=0.8, max_features="sqrt", random_state=42,
        ),
        method="isotonic", cv=3,
    )
    model_v16_baseline.fit(Xv16_train, y_train)

    # ── Evaluate ──
    y_prob_v17 = model_v17.predict_proba(Xv17_test)[:, 1]
    y_prob_v16 = model_v16_baseline.predict_proba(Xv16_test)[:, 1]

    auc_v17 = roc_auc_score(y_test, y_prob_v17)
    auc_v16 = roc_auc_score(y_test, y_prob_v16)
    ll_v17 = log_loss(y_test, y_prob_v17)
    ll_v16 = log_loss(y_test, y_prob_v16)

    print(f"\n{'':=<65}")
    print(f"  v16 AUC: {auc_v16:.4f}  LogLoss: {ll_v16:.4f}")
    print(f"  v17 AUC: {auc_v17:.4f}  LogLoss: {ll_v17:.4f}")
    print(f"  Delta AUC: {auc_v17 - auc_v16:+.4f}")
    print(f"{'':=<65}")

    # ── Feature importance ──
    # Extract from the first estimator in the calibrated CV ensemble
    base_gbm = model_v17.calibrated_classifiers_[0].estimator
    importance = pd.DataFrame({
        "feature": ALL_FEATURES,
        "importance": base_gbm.feature_importances_,
    }).sort_values("importance", ascending=False)

    print("\nTop 15 v17 Features:")
    print(importance.head(15).to_string(index=False))

    doctrine_imps = importance[importance["feature"].isin(V17_DOCTRINE_FEATURES)]
    print(f"\nNew doctrine features — total importance share: "
          f"{doctrine_imps['importance'].sum():.4f} "
          f"({doctrine_imps['importance'].sum() * 100:.1f}%)")
    print(doctrine_imps.to_string(index=False))

    # ── Save v17 model ──
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    model_path = out / "sqpe_v17.pkl"
    with open(model_path, "wb") as f:
        pickle.dump(model_v17, f)

    metadata = {
        "version": "v17.0",
        "model_type": "GradientBoostingClassifier + IsotonicCalibration",
        "n_estimators": 300,
        "learning_rate": 0.05,
        "max_depth": 5,
        "auc": float(auc_v17),
        "auc_v16_baseline": float(auc_v16),
        "auc_delta": float(auc_v17 - auc_v16),
        "log_loss": float(ll_v17),
        "n_features": len(ALL_FEATURES),
        "v16_features": V16_FEATURES,
        "v17_doctrine_features": V17_DOCTRINE_FEATURES,
        "feature_names": ALL_FEATURES,
        "n_train": int(len(Xv17_train)),
        "n_test": int(len(Xv17_test)),
        "win_rate": float(y.mean()),
        "trained_at": datetime.utcnow().isoformat(),
        "data_sources": ["backtest_50k.csv (2015)", "raw_races_2024_2025.txt (UK/IRE)"],
        "top_15_features": importance.head(15).to_dict("records"),
        "doctrine_feature_importance_total": float(doctrine_imps["importance"].sum()),
    }
    with open(out / "metadata.json", "w") as f:
        json.dump(metadata, f, indent=2)
    importance.to_csv(out / "feature_importance.csv", index=False)

    print(f"\nModel:    {model_path}")
    print(f"Metadata: {out / 'metadata.json'}")
    print(f"\n{'':=<65}")
    print(f"SQPE v17 COMPLETE  AUC={auc_v17:.4f}  (v16 was {auc_v16:.4f})")
    print(f"{'':=<65}")
    return {"auc_v17": auc_v17, "auc_v16": auc_v16, "model_path": str(model_path)}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Train SQPE v17")
    parser.add_argument("--backtest", default="data/backtest_50k_clean.csv")
    parser.add_argument("--raw", default="data/raw_races_2024_2025.txt")
    parser.add_argument("--output", default="models/sqpe_v17")
    parser.add_argument("--sample", type=int, default=None)
    parser.add_argument("--no-backtest", action="store_true")
    args = parser.parse_args()
    train(
        backtest_path=args.backtest,
        raw_path=args.raw,
        output_dir=args.output,
        sample_size=args.sample,
        no_backtest=args.no_backtest,
    )
