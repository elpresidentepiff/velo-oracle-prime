#!/usr/bin/env python3
"""Horse-history candidate SHADOW. Scores today's runners with the leak-free candidate.

Shadow only: writes data/horse_history_shadow/<date>.json. Never changes Prime's output.
Non-critical: any failure writes a FAILED status file and exits 0 so the morning run continues.
"""
from __future__ import annotations

import argparse
import json
import pickle
import re
import sys
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from app.services.horse_history_features import (  # noqa: E402
    compute_history_features, normalise_name, parse_dist_f, parse_going_code,
)
from app.services.horse_history_live import fetch_history  # noqa: E402

MODEL_DIR = ROOT / "models" / "horse_history_candidate"
OUT_DIR = ROOT / "data" / "horse_history_shadow"


def _num(s):
    try:
        return float(s)
    except (TypeError, ValueError):
        return np.nan


def _wgt(s):
    m = re.fullmatch(r"\s*(\d+)-(\d+)\s*", str(s or ""))
    return int(m.group(1)) * 14 + int(m.group(2)) if m else np.nan


def _cls(s):
    m = re.search(r"(\d)", str(s or ""))
    return float(m.group(1)) if m else np.nan


def _write(date: str, status: str, runners: list[dict], detail: str = "") -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "date": date, "status": status, "detail": detail, "model": "horse_history_candidate_v1",
        "promotion_status": "NOT_PROMOTED", "production_influence": False,
        "generated_at": datetime.now(UTC).isoformat(), "runners": runners,
    }
    (OUT_DIR / f"{date}.json").write_text(json.dumps(payload, indent=2, default=str))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", required=True)
    args = ap.parse_args()
    date = args.date
    try:
        from src.velo.racecard_loader import load_rp_merged_as_racecards
        races = load_rp_merged_as_racecards(date, ROOT / "data")
        meta = json.loads((MODEL_DIR / "metadata.json").read_text())
        model = pickle.loads((MODEL_DIR / "model.pkl").read_bytes())
        type_codes = {t: i for i, t in enumerate(meta["type_codes"])}

        rows, race_keys = [], []
        for race in races:
            rid = str(race.get("race_id"))
            runners = race.get("runners", []) or []
            field = float(len(runners))
            ors = [_num(r.get("ofr")) for r in runners]
            mean_or = np.nanmean(ors) if any(np.isfinite(ors)) else np.nan
            for r in runners:
                race_keys.append(rid)
                or_n = _num(r.get("ofr"))
                rows.append({
                    "horse": r.get("horse"), "date": date, "race_id": rid,
                    "course": race.get("course"), "dist_f": _num(race.get("distance_f")),
                    "going_code": parse_going_code(race.get("going")),
                    "class_num": _cls(race.get("race_class")),
                    "wgt_lbs": _wgt(r.get("lbs")), "or_num": or_n,
                    "or_vs_field": or_n - mean_or, "or_missing": float(not np.isfinite(or_n)),
                    "field_size": field, "draw_num": _num(r.get("draw")),
                    "draw_pct": _num(r.get("draw")) / field if field else np.nan,
                    "age_num": _num(r.get("age")),
                    "type_code": float(type_codes.get(race.get("type"), -1)),
                    "pos": None, "sp": None, "_today": True,
                })
        if not rows:
            _write(date, "NO_RUNNERS", [], "no merged racecards for date")
            return 0

        names = [r["horse"] for r in rows if r["horse"]]
        hist = fetch_history(names)
        hist_rows = []
        if len(hist):
            for i, h in hist.reset_index(drop=True).iterrows():
                dist = parse_dist_f(h.get("dist")) if h.get("dist") else _num(h.get("dist_f"))
                pos = pd.to_numeric(h.get("pos"), errors="coerce")
                hist_rows.append({
                    "horse": normalise_name(h.get("horse")), "date": h.get("date"),
                    "race_id": f"hist|{h.get('date')}|{h.get('course')}|{i}",
                    "course": h.get("course"), "dist_f": dist,
                    "going_code": parse_going_code(h.get("going")),
                    "class_num": _cls(h.get("class_raw")), "pos_n": pos, "or_num": _num(h.get("or_rating")),
                    "wgt_lbs": np.nan, "or_vs_field": np.nan, "or_missing": 0.0,
                    "field_size": np.nan, "draw_num": np.nan, "draw_pct": np.nan,
                    "age_num": np.nan, "type_code": -1.0, "_today": False,
                })
        today = []
        for r in rows:
            r = dict(r)
            r["horse_key"] = normalise_name(r["horse"])
            r["pos_n"] = np.nan
            today.append(r)
        frame = pd.DataFrame(hist_rows + [
            {**t, "horse": t["horse_key"]} for t in today])
        frame = compute_history_features(frame)
        frame = frame[frame["_today"] == True]  # noqa: E712
        X = frame[meta["features"]].fillna(-1)
        frame = frame.assign(prob=model.predict_proba(X)[:, 1])

        out = []
        for _, f in frame.iterrows():
            out.append({
                "horse": f["horse"], "race_id": f["race_id"],
                "prob": round(float(f["prob"]), 5),
                "runs_prior": int(f["runs_prior"]),
                "history_known": bool(f["runs_prior"] > 0),
            })
        out_df = pd.DataFrame(out)
        out_df["rank_in_race"] = out_df.groupby("race_id")["prob"].rank(ascending=False, method="first").astype(int)
        _write(date, "OK", out_df.to_dict(orient="records"),
               f"history rows fetched: {len(hist)}; runners scored: {len(out_df)}")
        print(f"horse_history_shadow {date}: {len(out_df)} runners, {len(hist)} history rows")
        return 0
    except Exception as exc:  # shadow must never stop the morning run
        _write(date, "FAILED", [], f"{type(exc).__name__}: {exc}")
        print(f"horse_history_shadow {date}: FAILED {type(exc).__name__}: {exc}")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
