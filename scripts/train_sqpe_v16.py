#!/usr/bin/env python3
"""
VÉLØ Oracle — SQPE v16 Trainer
Trains on real UK/IRE race data: backtest_50k (2015) + raw_races_2024_2025

Usage:
    python scripts/train_sqpe_v16.py
    python scripts/train_sqpe_v16.py --sample 30000
    python scripts/train_sqpe_v16.py --no-backtest   # 2024-2025 only
"""

import json
import pickle
import argparse
import re
from datetime import datetime
from pathlib import Path

import pandas as pd
import numpy as np
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.model_selection import TimeSeriesSplit
from sklearn.metrics import roc_auc_score, log_loss, classification_report
from sklearn.calibration import CalibratedClassifierCV, calibration_curve

# Column order for JSON-lines arrays (raw_races_2024_2025.txt)
COLS = [
    "date", "course", "race_id", "off", "race_name", "type", "class_raw",
    "pattern", "rating_band", "age_band", "sex_rest", "dist", "going",
    "ran", "num", "pos", "draw", "ovr_btn", "btn", "horse", "age", "sex",
    "wgt", "hg", "time", "sp", "jockey", "trainer", "prize",
    "or_rating", "rpr", "ts", "sire", "dam", "damsire", "owner", "comment"
]

# Courses to exclude (non-UK/IRE)
EXCLUDE_PATTERNS = re.compile(
    r"\(HK\)|\(AUS\)|\(USA\)|\(FR\)|\(GER\)|\(ITY\)|\(UAE\)|\(JPN\)|"
    r"\(SAF\)|\(SWE\)|\(NOR\)|\(BEL\)|\(CZE\)|\(HUN\)|\(POL\)|\(TUR\)|"
    r"Sha Tin|Happy Valley|Randwick|Flemington|Moonee|Caulfield|"
    r"Longchamp|Chantilly|Deauville|ParisLongchamp|"
    r"Meydan|Nad Al Sheba",
    re.IGNORECASE
)


def parse_sp(sp_str):
    """Convert SP string to decimal odds. '9/2' → 5.5, 'Evens' → 2.0, '11/10F' → 2.1"""
    if not sp_str or str(sp_str).strip() in ("", "–", "-", "nan"):
        return np.nan
    s = str(sp_str).strip().upper().rstrip("F").rstrip("J").strip()
    if s in ("EVENS", "EVS"):
        return 2.0
    m = re.match(r"^(\d+(?:\.\d+)?)/(\d+(?:\.\d+)?)$", s)
    if m:
        return float(m.group(1)) / float(m.group(2)) + 1.0
    try:
        return float(s) + 1.0  # decimal already
    except ValueError:
        return np.nan


def parse_dist(dist_str):
    """Convert distance string to furlongs. '6f' → 6.0, '1m2f' → 10.0, '1m' → 8.0"""
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
    """Encode going surface. Returns (going_code, is_all_weather)."""
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
    return 0.5, aw  # default: good-ish


def parse_class(class_str):
    """Extract numeric class. 'Class 2' → 2, 'Group 1' → 1 (elite), 'Listed' → 2"""
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
    """Convert weight '9-2' → total lbs (stone-pounds format)."""
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
    """Parse numeric field, handling '–', '-', empty."""
    if val is None:
        return np.nan
    s = str(val).strip()
    if s in ("", "–", "-", "nan"):
        return np.nan
    try:
        return float(s)
    except ValueError:
        return np.nan


def engineer_features(df):
    """Apply feature engineering to a raw dataframe."""
    df = df.copy()

    # Target
    df["target"] = (df["pos"].astype(str).str.strip() == "1").astype(int)

    # SP → decimal odds + log odds
    df["sp_dec"] = df["sp"].apply(parse_sp)
    df["log_sp"] = np.log(df["sp_dec"].clip(1.01, 200))

    # Implied probability from SP
    df["implied_prob"] = 1.0 / df["sp_dec"].clip(1.01, 200)

    # Distance
    df["dist_f"] = df["dist"].apply(parse_dist)

    # Going
    going_parsed = df["going"].apply(parse_going)
    df["going_code"] = going_parsed.apply(lambda x: x[0])
    df["is_aw"] = going_parsed.apply(lambda x: x[1])

    # Class
    df["class_num"] = df["class_raw"].apply(parse_class)

    # Weight
    df["wgt_lbs"] = df["wgt"].apply(parse_wgt)

    # Ratings
    df["or_num"] = df["or_rating"].apply(parse_numeric)
    df["rpr_num"] = df["rpr"].apply(parse_numeric)
    df["ts_num"] = df["ts"].apply(parse_numeric)

    # Field size
    df["field_size"] = pd.to_numeric(df["ran"], errors="coerce")

    # Draw (stall number)
    df["draw_num"] = pd.to_numeric(df["draw"], errors="coerce")
    # Draw as fraction of field (0=low draw, 1=high draw)
    df["draw_pct"] = df["draw_num"] / df["field_size"].clip(1)

    # Age
    df["age_num"] = pd.to_numeric(df["age"], errors="coerce")

    # Rating relative to field (OR minus mean OR in same race)
    df["or_num_safe"] = df["or_num"].fillna(df["or_num"].median())
    df["or_vs_field"] = df.groupby("race_id")["or_num_safe"].transform(
        lambda x: x - x.mean()
    )

    # RPR vs field
    df["rpr_safe"] = df["rpr_num"].fillna(df["rpr_num"].median())
    df["rpr_vs_field"] = df.groupby("race_id")["rpr_safe"].transform(
        lambda x: x - x.mean()
    )

    # SP rank within race (1=favourite, higher=bigger price)
    df["sp_rank"] = df.groupby("race_id")["sp_dec"].rank(method="min", ascending=True)
    df["is_fav"] = (df["sp_rank"] == 1).astype(int)

    return df


FEATURE_COLS = [
    "sp_dec", "log_sp", "implied_prob",
    "dist_f", "going_code", "is_aw",
    "class_num", "wgt_lbs",
    "or_num", "rpr_num", "ts_num",
    "or_vs_field", "rpr_vs_field",
    "field_size", "draw_num", "draw_pct",
    "age_num", "sp_rank", "is_fav",
]


def load_backtest_csv(path):
    """Load backtest_50k.csv — named columns."""
    print(f"  Loading {path} ...")
    df = pd.read_csv(path, low_memory=False)
    # Rename to standard names
    rename = {"class": "class_raw", "or": "or_rating"}
    df = df.rename(columns=rename)
    if "race_id" not in df.columns:
        df["race_id"] = df.get("course", "unk") + "_" + df.get("off", "0") + "_" + df.get("date", "0")
    print(f"  {len(df):,} rows loaded from backtest CSV")
    return df


def load_raw_txt(path, max_rows=None):
    """Load raw_races_2024_2025.txt — JSON-lines arrays, filter to UK/IRE."""
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
                row = dict(zip(COLS, arr[:len(COLS)]))
                # UK/IRE filter: exclude known non-UK/IRE courses
                if EXCLUDE_PATTERNS.search(str(row.get("course", ""))):
                    continue
                rows.append(row)
            except (json.JSONDecodeError, Exception):
                continue

    df = pd.DataFrame(rows)
    print(f"  {len(df):,} UK/IRE rows loaded from 2024-2025 TXT")
    return df


def train(backtest_path, raw_path, output_dir, sample_size=None, no_backtest=False):
    print("=" * 60)
    print("VÉLØ — SQPE v16 Training")
    print("=" * 60)

    frames = []

    if not no_backtest and Path(backtest_path).exists():
        df_bt = load_backtest_csv(backtest_path)
        df_bt["data_source"] = "backtest_2015"
        frames.append(df_bt)
    elif not no_backtest:
        print(f"  WARNING: {backtest_path} not found — skipping")

    if Path(raw_path).exists():
        df_raw = load_raw_txt(raw_path)
        df_raw["data_source"] = "real_2024_2025"
        frames.append(df_raw)
    else:
        print(f"  ERROR: {raw_path} not found")
        return

    df = pd.concat(frames, ignore_index=True)
    print(f"\nTotal combined rows: {len(df):,}")

    if sample_size:
        df = df.sample(n=min(sample_size, len(df)), random_state=42)
        print(f"Sampled to: {len(df):,} rows")

    # Remove rows where pos is non-numeric (DSQ, NR, etc.)
    df = df[pd.to_numeric(df["pos"].astype(str).str.strip(), errors="coerce").notna()]
    print(f"After removing non-runners/DSQ: {len(df):,} rows")

    print("\nEngineering features ...")
    df = engineer_features(df)

    X = df[FEATURE_COLS].fillna(0)
    y = df["target"]

    print(f"Win rate: {y.mean():.4f} ({y.sum():,} winners from {len(y):,} runners)")
    print(f"Features: {len(FEATURE_COLS)}")

    # Time-based train/test split (last 20% by row order = most recent data as test)
    split_idx = int(len(df) * 0.8)
    X_train, X_test = X.iloc[:split_idx], X.iloc[split_idx:]
    y_train, y_test = y.iloc[:split_idx], y.iloc[split_idx:]

    print(f"\nTrain: {len(X_train):,} | Test: {len(X_test):,}")

    print("\nTraining GradientBoostingClassifier ...")
    model = GradientBoostingClassifier(
        n_estimators=300,
        learning_rate=0.05,
        max_depth=5,
        min_samples_split=80,
        min_samples_leaf=40,
        subsample=0.8,
        max_features="sqrt",
        random_state=42,
        verbose=1,
    )
    model.fit(X_train, y_train)

    # Isotonic calibration on held-out test set
    # sklearn removed cv='prefit' — use a fresh CCV with 3-fold on test data
    print("\nCalibrating probabilities (isotonic, 3-fold on test set) ...")
    calibrator = CalibratedClassifierCV(
        GradientBoostingClassifier(
            n_estimators=300, learning_rate=0.05, max_depth=5,
            min_samples_split=80, min_samples_leaf=40,
            subsample=0.8, max_features="sqrt", random_state=42,
        ),
        method="isotonic", cv=3,
    )
    calibrator.fit(X_train, y_train)

    # Evaluate
    y_prob = calibrator.predict_proba(X_test)[:, 1]
    auc = roc_auc_score(y_test, y_prob)
    ll = log_loss(y_test, y_prob)

    print(f"\nAUC:       {auc:.4f}")
    print(f"Log Loss:  {ll:.4f}")
    print("\nClassification Report (threshold 0.5):")
    print(classification_report(y_test, (y_prob >= 0.5).astype(int)))

    # Feature importance
    importance = pd.DataFrame({
        "feature": FEATURE_COLS,
        "importance": model.feature_importances_
    }).sort_values("importance", ascending=False)
    print("\nTop 10 Features:")
    print(importance.head(10).to_string(index=False))

    # Save
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    model_path = out / "sqpe_v16.pkl"
    with open(model_path, "wb") as f:
        pickle.dump(calibrator, f)
    print(f"\nModel saved: {model_path}")

    metadata = {
        "version": "v16.0",
        "model_type": "GradientBoostingClassifier + IsotonicCalibration",
        "n_estimators": 300,
        "learning_rate": 0.05,
        "max_depth": 5,
        "auc": float(auc),
        "log_loss": float(ll),
        "n_features": len(FEATURE_COLS),
        "feature_names": FEATURE_COLS,
        "n_train": int(len(X_train)),
        "n_test": int(len(X_test)),
        "win_rate": float(y.mean()),
        "trained_at": datetime.utcnow().isoformat(),
        "data_sources": ["backtest_50k.csv (2015)", "raw_races_2024_2025.txt (UK/IRE)"],
        "top_10_features": importance.head(10).to_dict("records"),
    }
    with open(out / "metadata.json", "w") as f:
        json.dump(metadata, f, indent=2)
    importance.to_csv(out / "feature_importance.csv", index=False)

    print(f"Metadata:  {out / 'metadata.json'}")
    print(f"Features:  {out / 'feature_importance.csv'}")
    print("\n" + "=" * 60)
    print(f"SQPE v16 COMPLETE  AUC={auc:.4f}")
    print("=" * 60)
    return {"auc": auc, "log_loss": ll, "model_path": str(model_path)}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Train SQPE v16")
    parser.add_argument("--backtest", default="data/backtest_50k_clean.csv")
    parser.add_argument("--raw", default="data/raw_races_2024_2025.txt")
    parser.add_argument("--output", default="models/sqpe_v16")
    parser.add_argument("--sample", type=int, default=None, help="Row limit for quick test")
    parser.add_argument("--no-backtest", action="store_true", help="Skip backtest CSV")
    args = parser.parse_args()

    train(
        backtest_path=args.backtest,
        raw_path=args.raw,
        output_dir=args.output,
        sample_size=args.sample,
        no_backtest=args.no_backtest,
    )
