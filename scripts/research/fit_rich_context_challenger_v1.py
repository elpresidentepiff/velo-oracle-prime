#!/usr/bin/env python3
"""Fit the Rich Context challenger v1 on the frozen chronological split, and freeze an artifact.

This is Phase 5/6 of docs/engineering/WAKE_VELO_RICH_CONTEXT_CHALLENGER_PLAN_V1.md, scoped to the only
two feature families with real pre-November history: ``prime_baseline_snapshot`` (velo_prime_prob,
sp_dec) and ``canonical_history`` (as-of, leak-proof, from CanonicalHistoryProvider over
``racing_horse_runs``). FormFav and Spotlight facts have no pre-2026-11-06 history, so a family history
of them does not exist yet to fit or validate on; they stay future ablations once enough forward daily
packets accumulate, exactly as Phase 6 describes ("rolling chronological train/validation windows").

Universe and dates (frozen, declared before this script ever read a result):
  training   2026-05-26 .. 2026-06-12  (every UK/IRE runner with a numeric RP horse_id)
  validation 2026-06-13 .. 2026-06-19
  untouched holdout 2026-11-04 .. 2026-11-06 (read exactly once, by this script, for the honest readout
      printed below; never refit on)
  forward shadow 2026-11-07 onward: scored daily by the live pipeline, accumulating toward the Phase 7
      promotion threshold (500 forward races). This script does not touch forward dates.

Estimator (frozen in config/rich_context_challenger_protocol_v1.json, declared here, not chosen after
looking at holdout results): L2-regularised logistic regression, lbfgs, max_iter=2000, seed=2607,
class_weight balanced, C selected on validation log loss from the declared grid. Calibration: isotonic
(validation rows >= 1000) fit on the validation split only, never refit on holdout.

No production write. No Prime import. Reads racing_horse_runs and runner_prediction_snapshots only.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.services.rich_context_history_provider import (  # noqa: E402
    CanonicalHistoryProvider,
    HistoryPage,
)
from src.velo.rich_context_challenger_features import FEATURE_NAMES, extract_feature_vector  # noqa: E402

_REPO_COLUMNS = (
    "id,horse_id,race_id,run_date,course,course_id,region,race_type,distance_f,going,race_class,"
    "position,position_int,is_win,is_place,official_rating,sp_dec,btn,weight_lbs,jockey_id,jockey,"
    "trainer_id,trainer"
)


class _InMemoryHistoryRepository:
    """Serves CanonicalHistoryProvider from one bulk-loaded table instead of one HTTP call per horse.

    Same contract as SupabaseHistoricalRunRepository (exact count, ``run_date < before_date``, ordered
    ``run_date DESC, id DESC``) so every leakage/identity rule in the provider applies unchanged; this
    class only changes where the rows come from.
    """

    def __init__(self, rows_by_horse: dict[str, list[dict]]):
        self._by_horse = rows_by_horse

    def fetch_page(self, *, horse_id, before_date, offset, limit):

        rows = self._by_horse.get(str(horse_id), [])
        filtered = [r for r in rows if r["_d"] < before_date]
        total = len(filtered)
        page = filtered[offset : offset + limit]
        return HistoryPage(rows=tuple(dict(r) for r in page), offset=offset, limit=limit, total_count=total)


def _load_all_numeric_runs(client) -> dict[str, list[dict]]:
    """One bulk load of every numeric-horse-id row, sorted (run_date DESC, id DESC) per horse."""
    from datetime import date as _date

    rows: dict[str, list[dict]] = {}
    for row in _page(client, "racing_horse_runs", select=_REPO_COLUMNS, filters=[]):
        hid = str(row.get("horse_id") or "").strip()
        if not hid.isdigit():
            continue
        try:
            row["_d"] = _date.fromisoformat(str(row["run_date"])[:10])
        except (TypeError, ValueError, KeyError):
            continue
        rows.setdefault(hid, []).append(row)
    for horse_rows in rows.values():
        horse_rows.sort(key=lambda r: (r["_d"], int(r["id"])), reverse=True)
    return rows


TRAIN = ("2026-05-26", "2026-06-12")
VALIDATION = ("2026-06-13", "2026-06-19")
HOLDOUT = ("2026-11-04", "2026-11-06")
CANDIDATE_C = [0.05, 0.1, 0.25, 0.5, 1.0]
SEED = 2607
ARTIFACT_DIR = ROOT / "models" / "rich_context_challenger_v1"


def _client():
    from dotenv import load_dotenv

    load_dotenv(ROOT / ".env")
    from supabase import create_client

    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ.get("SUPABASE_SERVICE_KEY")
    if not url or not key:
        raise SystemExit("SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY not configured")
    return create_client(url, key)


def _page(client, table: str, *, select: str, filters: list[tuple[str, str, str]], page_size: int = 1000):
    offset = 0
    while True:
        q = client.table(table).select(select)
        for col, op, val in filters:
            q = getattr(q, op)(col, val)
        resp = q.range(offset, offset + page_size - 1).execute()
        rows = resp.data or []
        yield from rows
        if len(rows) < page_size:
            return
        offset += page_size


def _fetch_runs(client, start: str, end: str) -> list[dict[str, Any]]:
    """Every full-field run in [start, end]: context, market and the settlement label, in one table."""
    rows = list(
        _page(
            client,
            "racing_horse_runs",
            select="race_id,horse_id,run_date,course,distance_f,going,race_class,jockey_id,trainer_id,"
            "sp_dec,position_int,is_win",
            filters=[("run_date", "gte", start), ("run_date", "lte", end)],
        )
    )
    return [r for r in rows if str(r.get("horse_id") or "").strip().isdigit()]


def _fetch_prime_probs(client, start: str, end: str) -> dict[tuple[str, str], float]:
    """Prime's own velo_prime_prob per (race_id, horse_id), latest row per pair within the window."""
    rows = list(
        _page(
            client,
            "runner_prediction_snapshots",
            select="race_id,horse_id,race_date,velo_prime_prob,created_at",
            filters=[("race_date", "gte", start), ("race_date", "lte", end)],
        )
    )
    best: dict[tuple[str, str], tuple[str, float]] = {}
    for r in rows:
        key = (str(r.get("race_id")), str(r.get("horse_id")))
        vp = r.get("velo_prime_prob")
        ts = str(r.get("created_at") or "")
        if vp is None:
            continue
        if key not in best or ts > best[key][0]:
            best[key] = (ts, float(vp))
    return {k: v[1] for k, v in best.items()}


def build_rows(
    client, start: str, end: str, *, history: CanonicalHistoryProvider
) -> tuple[list[list[float]], list[int], dict[str, Any]]:
    runs = _fetch_runs(client, start, end)
    prime = _fetch_prime_probs(client, start, end)
    X: list[list[float]] = []
    y: list[int] = []
    skipped = {"no_prime_prob": 0, "no_sp": 0, "races": set()}
    for row in runs:
        race_id, horse_id = str(row["race_id"]), str(row["horse_id"])
        vp = prime.get((race_id, horse_id))
        sp = row.get("sp_dec")
        if vp is None:
            skipped["no_prime_prob"] += 1
            continue
        if sp is None or float(sp) <= 1.0:
            skipped["no_sp"] += 1
            continue
        run_date = datetime.fromisoformat(str(row["run_date"])).replace(tzinfo=UTC)
        hist = history.build(
            horse_id=horse_id,
            as_of_cutoff=run_date,  # racing_horse_runs is date-granular; before_date=run_date excludes it
            current_course=row.get("course"),
            current_distance_f=row.get("distance_f"),
            current_going=row.get("going"),
            current_race_class=row.get("race_class"),
            current_jockey_id=row.get("jockey_id"),
            current_trainer_id=row.get("trainer_id"),
        )
        vector = extract_feature_vector(
            prime_baseline={"velo_prime_prob": vp, "sp_dec": sp},
            history_eligible=bool(hist.get("eligible")),
            history_features=hist.get("features"),
        )
        if vector is None:
            continue
        X.append(vector)
        y.append(1 if row.get("is_win") else 0)
        skipped["races"].add(race_id)
    skipped["races"] = len(skipped["races"])
    return X, y, skipped


def _dataset_manifest_hash(rows: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(rows, sort_keys=True, default=str).encode()).hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dry-run", action="store_true", help="build the corpus and print sizes, fit nothing")
    args = ap.parse_args()

    client = _client()
    print("[FIT] bulk-loading racing_horse_runs once (replaces one HTTP call per horse)...", flush=True)
    history = CanonicalHistoryProvider(_InMemoryHistoryRepository(_load_all_numeric_runs(client)))
    print(f"[FIT] training   {TRAIN}", flush=True)
    X_train, y_train, train_skip = build_rows(client, *TRAIN, history=history)
    print(f"  rows={len(X_train)} races={train_skip['races']} skipped={train_skip}", flush=True)
    print(f"[FIT] validation {VALIDATION}", flush=True)
    X_val, y_val, val_skip = build_rows(client, *VALIDATION, history=history)
    print(f"  rows={len(X_val)} races={val_skip['races']} skipped={val_skip}", flush=True)
    print(f"[FIT] holdout    {HOLDOUT} (read once, never refit on)", flush=True)
    X_hold, y_hold, hold_skip = build_rows(client, *HOLDOUT, history=history)
    print(f"  rows={len(X_hold)} races={hold_skip['races']} skipped={hold_skip}", flush=True)

    manifest = {
        "train_window": TRAIN,
        "validation_window": VALIDATION,
        "holdout_window": HOLDOUT,
        "train_rows": len(X_train),
        "validation_rows": len(X_val),
        "holdout_rows": len(X_hold),
        "feature_names": list(FEATURE_NAMES),
    }
    manifest_hash = _dataset_manifest_hash(manifest)
    print(f"[FIT] dataset manifest hash: {manifest_hash}")
    if args.dry_run:
        print("[FIT] --dry-run: stopping before fit.")
        return 0
    if len(X_train) < 200 or len(X_val) < 200:
        raise SystemExit(f"Refusing to fit on too few rows (train={len(X_train)}, validation={len(X_val)})")

    import numpy as np
    from sklearn.calibration import CalibratedClassifierCV
    from sklearn.linear_model import LogisticRegression
    from sklearn.metrics import brier_score_loss, log_loss

    Xtr, ytr = np.array(X_train), np.array(y_train)
    Xva, yva = np.array(X_val), np.array(y_val)
    Xho, yho = np.array(X_hold), np.array(y_hold)

    best_c, best_ll, best_model = None, math.inf, None
    for c in CANDIDATE_C:
        model = LogisticRegression(
            penalty="l2", solver="lbfgs", max_iter=2000, random_state=SEED, class_weight="balanced", C=c
        ).fit(Xtr, ytr)
        ll = log_loss(yva, model.predict_proba(Xva)[:, 1], labels=[0, 1])
        print(f"  C={c:<5} validation log_loss={ll:.5f}")
        if ll < best_ll:
            best_c, best_ll, best_model = c, ll, model
    print(f"[FIT] selected C={best_c} (frozen candidate grid, validation log loss)")

    calibration_method = "isotonic" if len(X_val) >= 1000 else "sigmoid"
    # sklearn >=1.6 dropped cv="prefit"; FrozenEstimator freezes best_model so CalibratedClassifierCV
    # only fits the calibration curve, on the validation split, exactly as the protocol requires.
    from sklearn.frozen import FrozenEstimator

    calibrated = CalibratedClassifierCV(FrozenEstimator(best_model), method=calibration_method)
    calibrated.fit(Xva, yva)
    print(f"[FIT] calibration: {calibration_method} (fit on validation only)")

    def _report(name: str, X, y) -> dict[str, float]:
        if len(X) == 0:
            return {"n": 0}
        p_market = X[:, FEATURE_NAMES.index("implied_prob")]  # already 1/sp_dec, see extract_feature_vector
        p_prime = X[:, FEATURE_NAMES.index("velo_prime_prob")]
        p_model = calibrated.predict_proba(X)[:, 1]
        eps = 1e-9
        out = {
            "n": int(len(X)),
            "log_loss_market_only": float(log_loss(y, np.clip(p_market, eps, 1 - eps), labels=[0, 1])),
            "log_loss_prime_only": float(log_loss(y, np.clip(p_prime, eps, 1 - eps), labels=[0, 1])),
            "log_loss_challenger": float(log_loss(y, np.clip(p_model, eps, 1 - eps), labels=[0, 1])),
            "brier_prime_only": float(brier_score_loss(y, p_prime)),
            "brier_challenger": float(brier_score_loss(y, p_model)),
        }
        out["lift_vs_prime"] = out["log_loss_prime_only"] - out["log_loss_challenger"]  # positive = improvement
        return out

    metrics = {
        "train": _report("train", Xtr, ytr),
        "validation": _report("validation", Xva, yva),
        "untouched_holdout": _report("untouched_holdout", Xho, yho),
    }
    print("[FIT] metrics (lift_vs_prime > 0 means lower log loss than Prime alone):")
    print(json.dumps(metrics, indent=2))

    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    import joblib

    joblib.dump(calibrated, ARTIFACT_DIR / "model.joblib")
    code_sha = os.environ.get("RAILWAY_GIT_COMMIT_SHA", "")[:12] or "local"
    metadata = {
        "model_version": "rich_context_challenger_v1_fit_20261108",
        "protocol": "RICH_CONTEXT_PROTOCOL_V1",
        "estimator": "logistic_regression_l2_lbfgs",
        "selected_C": best_c,
        "calibration_method": calibration_method,
        "random_seed": SEED,
        "feature_names": list(FEATURE_NAMES),
        "feature_families_used": ["prime_baseline_snapshot", "canonical_history", "market_facts"],
        "feature_families_excluded": [
            "rp_spotlight_facts",
            "formfav_raw_facts",
            "formfav_pace_context",
            "formfav_class_context",
            "formfav_track_bias_context",
            "connections_passports",
        ],
        "feature_families_excluded_reason": "no pre-2026-11-06 history to train or validate on",
        "dataset_manifest": manifest,
        "dataset_manifest_hash": manifest_hash,
        "metrics": metrics,
        "code_sha": code_sha,
        "fitted_at": datetime.now(UTC).isoformat(),
        "promotion_eligible": False,
        "production_influence": False,
    }
    (ARTIFACT_DIR / "metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    print(f"[FIT] artifact written: {ARTIFACT_DIR / 'model.joblib'}")
    print(f"[FIT] metadata written: {ARTIFACT_DIR / 'metadata.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
