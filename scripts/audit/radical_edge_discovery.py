#!/usr/bin/env python3
"""Radical edge discovery for Velo.

Purpose:
  - Stop asking for one universal scorer.
  - Find regimes where Velo should bet, pass, or route to a sidecar.
  - Keep all outputs evidence-only: no live scoring, no staking, no promotion.
"""

from __future__ import annotations

import json
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import log_loss, roc_auc_score
from sklearn.model_selection import GroupShuffleSplit
from sklearn.pipeline import Pipeline

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"
REPORT_DIR = DATA / "reports"
MODEL_DIR = ROOT / "models" / "radical_sigma_gate_staging"

INNOVATION_PATH = DATA / "velo_innovation_protocol_1k_deduped.csv"
EXECUTION_BRIDGE_PATH = DATA / "velo_execution_bridge_paper_ledger.csv"
CURRENT_ERA_ROWS_PATH = DATA / "reports" / "current_era_sigma_union_rows_2026_05_08_to_2026_06_13.json"
SIGMA_DIR = DATA / "sigma_results"
SIDECAR_ELO_PATH = DATA / "sidecar_elo" / "sidecar_elo_ledger.jsonl"
SIDECAR_TOURNAMENT_PATH = DATA / "new_build" / "reports" / "sidecar_tournament_latest.json"

SIGMA_FEATURES = [
    "model_probability",
    "sp_decimal",
    "implied_probability",
    "edge",
    "field_size",
    "class_num",
    "candidate_stake",
    "router_v1_shadow_pass",
    "router_v2_class4_shadow_pass",
    "router_v6_gold_seam_watchlist",
]


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None or value == "":
            return default
        f = float(value)
        if np.isnan(f) or np.isinf(f):
            return default
        return f
    except Exception:
        return default


def _odds_band(sp: Any) -> str:
    v = _safe_float(sp, 0.0)
    if v <= 0:
        return "NO_ODDS"
    if v < 1.5:
        return "ODDS_ON_LT_1_5"
    if v < 2.5:
        return "EVS_TO_6_4"
    if v < 4.0:
        return "TWO_TO_THREE"
    if v < 6.0:
        return "THREE_TO_FIVE"
    if v < 9.0:
        return "FIVE_TO_EIGHT"
    if v < 15.0:
        return "EIGHT_TO_FOURTEEN"
    return "LONGSHOT_15_PLUS"


def _vp_band(vp: Any) -> str:
    v = _safe_float(vp, 0.0)
    if v >= 0.55:
        return "VP_55_PLUS"
    if v >= 0.45:
        return "VP_45_55"
    if v >= 0.35:
        return "VP_35_45"
    if v >= 0.25:
        return "VP_25_35"
    if v >= 0.15:
        return "VP_15_25"
    return "VP_LT_15"


def _field_band(v: Any) -> str:
    fs = int(_safe_float(v, 0))
    if fs <= 0:
        return "FS_UNKNOWN"
    if fs <= 5:
        return "FS_2_5"
    if fs <= 8:
        return "FS_6_8"
    if fs <= 12:
        return "FS_9_12"
    return "FS_13_PLUS"


def _pl(won: Any, sp: Any) -> float:
    return (_safe_float(sp) - 1.0) if int(_safe_float(won, 0)) == 1 else -1.0


def _summarise_group(df: pd.DataFrame, col: str, min_n: int = 20) -> list[dict[str, Any]]:
    rows = []
    for key, g in df.groupby(col, dropna=False):
        n = len(g)
        if n < min_n:
            continue
        wins = int(g["won"].sum())
        frames = int(g["placed"].sum()) if "placed" in g else 0
        pl = float(g["_pl"].sum())
        rows.append(
            {
                "group": str(key),
                "n": int(n),
                "wins": wins,
                "sr": round(wins / n, 4),
                "frames": frames,
                "frame_rate": round(frames / n, 4) if "placed" in g else None,
                "roi": round(pl / n, 4),
                "pl": round(pl, 2),
                "avg_sp": round(float(pd.to_numeric(g["sp_decimal"], errors="coerce").mean()), 3),
                "avg_vp": round(float(pd.to_numeric(g["model_probability"], errors="coerce").mean()), 4),
            }
        )
    return sorted(rows, key=lambda r: (r["roi"], r["sr"], r["n"]), reverse=True)


def _summarise_combo(df: pd.DataFrame, cols: list[str], min_n: int = 20) -> list[dict[str, Any]]:
    tmp = df.copy()
    key = " + ".join(cols)
    tmp[key] = tmp[cols].astype(str).agg("|".join, axis=1)
    return _summarise_group(tmp, key, min_n=min_n)


def load_innovation() -> pd.DataFrame:
    df = pd.read_csv(INNOVATION_PATH)
    for col in SIGMA_FEATURES + ["won", "placed"]:
        if col not in df.columns:
            df[col] = 0
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df = df[df["won"].isin([0, 1])]
    df = df[pd.to_numeric(df["sp_decimal"], errors="coerce").fillna(0) > 1.0].copy()
    df["_pl"] = [_pl(w, sp) for w, sp in zip(df["won"], df["sp_decimal"], strict=False)]
    df["odds_band"] = df["sp_decimal"].map(_odds_band)
    df["vp_band"] = df["model_probability"].map(_vp_band)
    df["field_band"] = df["field_size"].map(_field_band)
    df["class_band"] = df["class_num"].fillna(0).astype(int).map(lambda x: f"CLASS_{x}" if x else "CLASS_UNKNOWN")
    for col in ["router_v1_shadow_pass", "router_v2_class4_shadow_pass", "router_v6_gold_seam_watchlist"]:
        df[col] = df[col].fillna(False).astype(bool)
    df["router_combo"] = (
        "v1=" + df["router_v1_shadow_pass"].astype(int).astype(str)
        + "|v2=" + df["router_v2_class4_shadow_pass"].astype(int).astype(str)
        + "|v6=" + df["router_v6_gold_seam_watchlist"].astype(int).astype(str)
    )
    return df


def train_sigma_gate(df: pd.DataFrame, target_col: str = "won", label: str = "sigma_win_gate") -> dict[str, Any]:
    model_df = df.copy()
    for col in SIGMA_FEATURES:
        model_df[col] = pd.to_numeric(model_df[col], errors="coerce")
    model_df["target"] = model_df[target_col].astype(int)
    groups = model_df["race_id"].astype(str)
    splitter = GroupShuffleSplit(n_splits=1, test_size=0.25, random_state=77)
    train_idx, test_idx = next(splitter.split(model_df, model_df["target"], groups))
    train = model_df.iloc[train_idx].copy()
    test = model_df.iloc[test_idx].copy()

    baseline = test["model_probability"].clip(1e-6, 1 - 1e-6).to_numpy()
    gate = Pipeline(
        [
            ("impute", SimpleImputer(strategy="median")),
            (
                "model",
                LogisticRegression(max_iter=1000, class_weight="balanced", random_state=77),
            ),
        ]
    )
    gate.fit(train[SIGMA_FEATURES], train["target"])
    proba = gate.predict_proba(test[SIGMA_FEATURES])[:, 1]

    def bands(label: str, score: np.ndarray) -> list[dict[str, Any]]:
        tmp = test.copy()
        tmp["_score"] = score
        tmp = tmp.sort_values("_score", ascending=False).reset_index(drop=True)
        out = []
        for frac in (0.1, 0.2, 0.3, 0.5):
            n = max(1, int(len(tmp) * frac))
            sub = tmp.head(n)
            out.append(
                {
                    "ranker": label,
                    "accept_top_pct": int(frac * 100),
                    "n": int(len(sub)),
                    "sr": round(float(sub["won"].mean()), 4),
                    "frame_rate": round(float(sub["placed"].mean()), 4),
                    "roi": round(float(sub["_pl"].sum() / len(sub)), 4),
                    "pl": round(float(sub["_pl"].sum()), 2),
                    "avg_sp": round(float(sub["sp_decimal"].mean()), 3),
                }
            )
        return out

    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    model_path = MODEL_DIR / f"{label}.pkl"
    joblib.dump(
        {
            "model": gate,
            "features": SIGMA_FEATURES,
            "target": target_col,
            "status": "STAGING_ONLY_NOT_LIVE",
            "trained_at": datetime.now(UTC).isoformat(),
        },
        model_path,
    )

    return {
        "status": "PASS",
        "label": label,
        "target": target_col,
        "rows": int(len(model_df)),
        "train_rows": int(len(train)),
        "test_rows": int(len(test)),
        "test_races": int(test["race_id"].nunique()),
        "baseline_auc": round(float(roc_auc_score(test["target"], baseline)), 4),
        "gate_auc": round(float(roc_auc_score(test["target"], proba)), 4),
        "baseline_logloss": round(float(log_loss(test["target"], np.clip(baseline, 1e-6, 1 - 1e-6))), 4),
        "gate_logloss": round(float(log_loss(test["target"], np.clip(proba, 1e-6, 1 - 1e-6))), 4),
        "acceptance_bands": bands("baseline_vp", baseline) + bands("sigma_gate", proba),
        "staging_model": str(model_path),
    }


def load_sigma_daily_rows() -> pd.DataFrame:
    rows = []
    for path in sorted(SIGMA_DIR.glob("sigma_results_2026_*.json")):
        try:
            obj = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        for row in obj.get("rows", []) if isinstance(obj, dict) else []:
            rows.append(
                {
                    "date": obj.get("date"),
                    "race_id": row.get("race_id"),
                    "course": row.get("course"),
                    "predicted": row.get("predicted"),
                    "actual_name": row.get("actual_name"),
                    "winner_sp": _safe_float(row.get("winner_sp"), 0.0),
                    "vp": _safe_float(row.get("velo_prime_prob"), 0.0),
                    "outcome": row.get("outcome"),
                    "miss_class": row.get("miss_class"),
                }
            )
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    df["won"] = (df["outcome"] == "WIN").astype(int)
    df["framed"] = df["outcome"].isin(["WIN", "PLACED"]).astype(int)
    df["vp_band"] = df["vp"].map(_vp_band)
    df["winner_odds_band"] = df["winner_sp"].map(_odds_band)
    return df


def current_era_summary() -> dict[str, Any]:
    if not CURRENT_ERA_ROWS_PATH.exists():
        return {"status": "MISSING"}
    rows = json.loads(CURRENT_ERA_ROWS_PATH.read_text(encoding="utf-8"))
    df = pd.DataFrame(rows)
    if df.empty:
        return {"status": "EMPTY"}
    df["won"] = (df["outcome"] == "WIN").astype(int)
    df["framed"] = df["outcome"].isin(["WIN", "PLACED"]).astype(int)
    df["vp"] = pd.to_numeric(df["vp"], errors="coerce")
    df["actual_winner_sp"] = pd.to_numeric(df["actual_winner_sp"], errors="coerce")
    return {
        "status": "PASS",
        "rows": int(len(df)),
        "date_min": str(df["race_date"].min()),
        "date_max": str(df["race_date"].max()),
        "sr": round(float(df["won"].mean()), 4),
        "frame_rate": round(float(df["framed"].mean()), 4),
        "vp_bands": _simple_rate_table(df, "vp", "won", [0, 0.15, 0.25, 0.35, 0.45, 0.55, 1.0]),
    }


def _simple_rate_table(df: pd.DataFrame, value_col: str, target_col: str, bins: list[float]) -> list[dict[str, Any]]:
    tmp = df.copy()
    tmp["_band"] = pd.cut(tmp[value_col], bins=bins, include_lowest=True).astype(str)
    out = []
    for band, g in tmp.groupby("_band", dropna=False):
        out.append(
            {
                "band": str(band),
                "n": int(len(g)),
                "rate": round(float(g[target_col].mean()), 4) if len(g) else 0.0,
            }
        )
    return out


def sidecar_summary() -> dict[str, Any]:
    tournament = {}
    if SIDECAR_TOURNAMENT_PATH.exists():
        tournament = json.loads(SIDECAR_TOURNAMENT_PATH.read_text(encoding="utf-8"))
    elo = []
    if SIDECAR_ELO_PATH.exists():
        for line in SIDECAR_ELO_PATH.read_text(encoding="utf-8").splitlines():
            if line.strip():
                elo.append(json.loads(line))
    elo_df = pd.DataFrame(elo)
    elo_summary = []
    if not elo_df.empty:
        latest = elo_df.sort_values("generated_at").groupby("sidecar").tail(1)
        events = elo_df.groupby("sidecar")["event"].apply(lambda s: dict(Counter(s))).to_dict()
        for _, row in latest.sort_values("new_elo", ascending=False).iterrows():
            elo_summary.append(
                {
                    "sidecar": row["sidecar"],
                    "new_elo": int(row["new_elo"]),
                    "events": events.get(row["sidecar"], {}),
                }
            )
    ablations = []
    for name, result in (tournament.get("ablation_results") or {}).items():
        test = result.get("test") or {}
        ablations.append(
            {
                "name": name,
                "auc": test.get("AUC"),
                "sr": test.get("SR"),
                "frame": test.get("Frame"),
                "auc_lift": result.get("test_AUC_lift"),
                "sr_lift": result.get("test_SR_lift"),
                "leakage_risk": result.get("leakage_risk"),
                "verdict": result.get("verdict"),
            }
        )
    return {
        "sidecar_elo": elo_summary,
        "sidecar_ablation": sorted(ablations, key=lambda r: (r.get("auc_lift") or -9), reverse=True),
        "inventory": tournament.get("sidecar_inventory", {}),
    }


def build_report() -> dict[str, Any]:
    innovation = load_innovation()
    sigma_gate = train_sigma_gate(innovation, "won", "sigma_win_gate")
    frame_gate = train_sigma_gate(innovation, "placed", "sigma_frame_gate")
    sigma_daily = load_sigma_daily_rows()

    regime_tables = {
        "odds_band": _summarise_group(innovation, "odds_band"),
        "vp_band": _summarise_group(innovation, "vp_band"),
        "field_band": _summarise_group(innovation, "field_band"),
        "class_band": _summarise_group(innovation, "class_band"),
        "router_combo": _summarise_group(innovation, "router_combo", min_n=10),
        "course": _summarise_group(innovation, "course", min_n=12),
        "odds_x_field": _summarise_combo(innovation, ["odds_band", "field_band"], min_n=20),
        "odds_x_vp": _summarise_combo(innovation, ["odds_band", "vp_band"], min_n=20),
        "class_x_field": _summarise_combo(innovation, ["class_band", "field_band"], min_n=20),
    }
    toxic_tables = {
        key: sorted(value, key=lambda r: (r["roi"], r["sr"], r["n"]))[:12]
        for key, value in regime_tables.items()
    }

    daily_summary = {"status": "EMPTY"}
    if not sigma_daily.empty:
        daily_summary = {
            "status": "PASS",
            "rows": int(len(sigma_daily)),
            "date_min": str(sigma_daily["date"].min()),
            "date_max": str(sigma_daily["date"].max()),
            "sr": round(float(sigma_daily["won"].mean()), 4),
            "frame_rate": round(float(sigma_daily["framed"].mean()), 4),
            "vp_band": [
                {
                    "band": k,
                    "n": int(len(g)),
                    "sr": round(float(g["won"].mean()), 4),
                    "frame_rate": round(float(g["framed"].mean()), 4),
                }
                for k, g in sigma_daily.groupby("vp_band")
            ],
            "winner_odds_band": [
                {
                    "band": k,
                    "n": int(len(g)),
                    "sr": round(float(g["won"].mean()), 4),
                    "frame_rate": round(float(g["framed"].mean()), 4),
                }
                for k, g in sigma_daily.groupby("winner_odds_band")
            ],
        }

    doctrine = [
        "Live Velo should become a gated decision system, not a universal top-pick bettor.",
        "Morning model: clean RP race-shape + Velo doctrine + passport memory only.",
        "Late model: market lane is separate and time-boxed; never contaminates morning truth.",
        "Sigma gate decides bet/pass after the scorer speaks; it does not replace the scorer.",
        "JTC-D is high-value but quarantined until rebuilt as lagged/date-bounded.",
        "Longshots split: 8-14 can be an edge-discovery zone; 15+ is not execution-ready.",
        "High Sigma frame confidence is a cash-run/acca clue, not proof of win-bet value.",
    ]

    payload = {
        "generated_at": datetime.now(UTC).isoformat(),
        "status": "EVIDENCE_ONLY_NO_LIVE_CHANGE",
        "sources": {
            "innovation_protocol": str(INNOVATION_PATH),
            "execution_bridge": str(EXECUTION_BRIDGE_PATH),
            "current_era_rows": str(CURRENT_ERA_ROWS_PATH),
            "sigma_dir": str(SIGMA_DIR),
            "sidecar_elo": str(SIDECAR_ELO_PATH),
            "sidecar_tournament": str(SIDECAR_TOURNAMENT_PATH),
        },
        "innovation_universe": {
            "rows": int(len(innovation)),
            "sr": round(float(innovation["won"].mean()), 4),
            "frame_rate": round(float(innovation["placed"].mean()), 4),
            "roi": round(float(innovation["_pl"].sum() / len(innovation)), 4),
            "pl": round(float(innovation["_pl"].sum()), 2),
        },
        "sigma_gate": sigma_gate,
        "frame_gate": frame_gate,
        "best_regimes": {k: v[:12] for k, v in regime_tables.items()},
        "toxic_regimes": toxic_tables,
        "daily_sigma_summary": daily_summary,
        "current_era_summary": current_era_summary(),
        "sidecars": sidecar_summary(),
        "radical_doctrine": doctrine,
        "decision": {
            "go_live_now": False,
            "next_build": "RADICAL_VELO_GATED_ARCHITECTURE_SHADOW",
            "why": "Evidence supports separation of scorer, Sigma gate, passport memory, and late market sidecar. It does not support one blended live model yet.",
        },
    }
    return payload


def write_report(payload: dict[str, Any]) -> None:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    json_path = REPORT_DIR / "radical_edge_discovery_latest.json"
    md_path = REPORT_DIR / "radical_edge_discovery_latest.md"
    json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    lines = [
        "# Radical Edge Discovery",
        f"Generated: {payload['generated_at']}",
        "",
        "## Decision",
        f"- Go live now: {payload['decision']['go_live_now']}",
        f"- Next build: {payload['decision']['next_build']}",
        f"- Why: {payload['decision']['why']}",
        "",
        "## Innovation Universe",
    ]
    u = payload["innovation_universe"]
    lines.extend(
        [
            f"- Rows: {u['rows']}",
            f"- Strike rate: {u['sr']}",
            f"- Frame rate: {u['frame_rate']}",
            f"- ROI/pt: {u['roi']}",
            f"- P&L: {u['pl']}",
            "",
            "## Sigma Gate",
        ]
    )
    sg = payload["sigma_gate"]
    lines.extend(
        [
            f"- Rows: {sg['rows']}",
            f"- Baseline AUC: {sg['baseline_auc']}",
            f"- Gate AUC: {sg['gate_auc']}",
            f"- Staging model: {sg['staging_model']}",
            "",
            "| Ranker | Top % | n | SR | Frame | ROI/pt | P&L | Avg SP |",
            "|---|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for row in sg["acceptance_bands"]:
        lines.append(
            f"| {row['ranker']} | {row['accept_top_pct']} | {row['n']} | {row['sr']} | {row['frame_rate']} | {row['roi']} | {row['pl']} | {row['avg_sp']} |"
        )

    fg = payload["frame_gate"]
    lines.extend(
        [
            "",
            "## Frame Gate",
            f"- Rows: {fg['rows']}",
            f"- Baseline AUC: {fg['baseline_auc']}",
            f"- Gate AUC: {fg['gate_auc']}",
            f"- Staging model: {fg['staging_model']}",
            "",
            "| Ranker | Top % | n | SR | Frame | ROI/pt | P&L | Avg SP |",
            "|---|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for row in fg["acceptance_bands"]:
        lines.append(
            f"| {row['ranker']} | {row['accept_top_pct']} | {row['n']} | {row['sr']} | {row['frame_rate']} | {row['roi']} | {row['pl']} | {row['avg_sp']} |"
        )

    lines.extend(["", "## Best Regimes"])
    for name, rows in payload["best_regimes"].items():
        lines.append(f"### {name}")
        for r in rows[:6]:
            lines.append(
                f"- {r['group']}: n={r['n']} SR={r['sr']} frame={r['frame_rate']} ROI={r['roi']} avg_sp={r['avg_sp']}"
            )

    lines.extend(["", "## Toxic Regimes"])
    for name, rows in payload["toxic_regimes"].items():
        lines.append(f"### {name}")
        for r in rows[:4]:
            lines.append(
                f"- {r['group']}: n={r['n']} SR={r['sr']} frame={r['frame_rate']} ROI={r['roi']} avg_sp={r['avg_sp']}"
            )

    lines.extend(["", "## Sidecars"])
    for r in payload["sidecars"].get("sidecar_ablation", [])[:6]:
        lines.append(
            f"- {r['name']}: AUC={r['auc']} SR={r['sr']} lift={r['auc_lift']} leakage={r['leakage_risk']} verdict={r['verdict']}"
        )

    lines.extend(["", "## Radical Doctrine"])
    for item in payload["radical_doctrine"]:
        lines.append(f"- {item}")
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    payload = build_report()
    write_report(payload)
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
