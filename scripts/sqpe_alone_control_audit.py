"""
sqpe_alone_control_audit.py
============================
Compare SQPE-only vs current ensemble vs each sidecar combination.

Uses VeloPrimeEnsemble.predict_race() with ablation mode constants.
Pulls race data from velo_verdicts (Supabase) + runner_results for outcomes.

Configurations tested:
  1. SQPE_ONLY
  2. FULL_ENSEMBLE (FULL_MINUS_DEAD — current live weights)
  3. SQPE + improvement_score  (SQPE_PLUS_PLACE_PLUS_IMPROVEMENT but as SQPE+improve)
  4. SQPE + market_deception_score (MDS)
  5. SQPE + place_prob
  6. SQPE + longshot_score
  7. SQPE + improvement_score + MDS

AUDIT ONLY — no model changes, no scoring changes.
"""

from __future__ import annotations

import json
import os
import re
import statistics
import sys
import urllib.parse
import urllib.request
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Optional

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
load_dotenv(ROOT / ".env")

from src.intelligence.velo_prime_ensemble import (
    VeloPrimeEnsemble,
    ABLATION_SQPE_ONLY,
    ABLATION_FULL_MINUS_DEAD,
    _DISABLED_COMPONENTS,
    _WEIGHTS,
)
from src.intelligence.macro_regime.bha_macro_context import get_macro_context_for_race

OUTPUT_JSON = ROOT / "data" / "sqpe_alone_control_audit_latest.json"
OUTPUT_MD = ROOT / "data" / "sqpe_alone_control_audit_latest.md"

# ── Supabase REST ───────────────────────────────────────────────────────────────

def _sb_env() -> tuple[str, str]:
    url = os.getenv("SUPABASE_URL", "").rstrip("/")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_SERVICE_KEY", "")
    if not url or not key:
        raise RuntimeError("SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY not set")
    return url, key


def _sb_get(table: str, select: str, params: dict | None = None, limit: int = 10000) -> list[dict]:
    url, key = _sb_env()
    headers = {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Accept": "application/json",
    }
    all_rows: list[dict] = []
    offset = 0
    page = min(limit, 1000)
    while True:
        query: dict[str, str] = {"select": select, "limit": str(page), "offset": str(offset)}
        if params:
            query.update(params)
        qs = "&".join(f"{k}={urllib.parse.quote(str(v))}" for k, v in query.items())
        req = urllib.request.Request(f"{url}/rest/v1/{table}?{qs}", headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read().decode())
        except Exception as exc:
            print(f"  WARNING: Supabase error ({table}): {exc}", file=sys.stderr)
            return all_rows
        if not isinstance(data, list):
            print(f"  WARNING: Unexpected response from {table}: {data}", file=sys.stderr)
            return all_rows
        all_rows.extend(data)
        if len(data) < page:
            break
        offset += page
        if offset >= limit:
            break
    return all_rows


# ── Helpers ────────────────────────────────────────────────────────────────────

def _safe_float(v: Any) -> Optional[float]:
    try:
        if v is None or str(v).strip() in ("", "–", "-"):
            return None
        return float(v)
    except (ValueError, TypeError):
        return None


def _position_int(v: Any) -> Optional[int]:
    try:
        return int(str(v).strip())
    except (ValueError, TypeError):
        return None


def _norm_name(s: str) -> str:
    return re.sub(r"[^\w\s]", "", str(s or "")).strip().lower()


def _code_from_race_type(race_type: str | None) -> str:
    text = (race_type or "").lower()
    return "jump" if any(t in text for t in ["hurdle", "chase", "nh flat"]) else "flat"


# ── Build ablation configs ───────────────────────────────────────────────────────
# Each config: {name, mode, extra_exclude}
# extra_exclude: set of component keys to zero out in runner data
CONFIGS = [
    {
        "name": "SQPE_ONLY",
        "mode": ABLATION_SQPE_ONLY,
        "description": "SQPE v17 alone, all sidecars excluded",
        "extra_exclude": set(),
    },
    {
        "name": "FULL_ENSEMBLE",
        "mode": ABLATION_FULL_MINUS_DEAD,
        "description": "Current live ensemble (SQPE + MDS + place_prob + longshot)",
        "extra_exclude": set(),
    },
    {
        "name": "SQPE_PLUS_IMPROVEMENT",
        "mode": None,  # custom — we'll use SQPE_ONLY + re-enable improvement
        "description": "SQPE + improvement_score",
        "extra_exclude": {"market_deception_score", "place_prob", "comment_intel_score", "release_window_score", "longshot_score"},
        "force_include": {"improvement_score"},
    },
    {
        "name": "SQPE_PLUS_MDS",
        "mode": None,
        "description": "SQPE + market_deception_score",
        "extra_exclude": {"improvement_score", "place_prob", "comment_intel_score", "release_window_score", "longshot_score"},
        "force_include": {"market_deception_score"},
    },
    {
        "name": "SQPE_PLUS_PLACE",
        "mode": None,
        "description": "SQPE + place_prob",
        "extra_exclude": {"improvement_score", "market_deception_score", "comment_intel_score", "release_window_score", "longshot_score"},
        "force_include": {"place_prob"},
    },
    {
        "name": "SQPE_PLUS_LONGSHOT",
        "mode": None,
        "description": "SQPE + longshot_score",
        "extra_exclude": {"improvement_score", "market_deception_score", "place_prob", "comment_intel_score", "release_window_score"},
        "force_include": {"longshot_score"},
    },
    {
        "name": "SQPE_PLUS_IMPROVE_MDS",
        "mode": None,
        "description": "SQPE + improvement_score + MDS",
        "extra_exclude": {"place_prob", "comment_intel_score", "release_window_score", "longshot_score"},
        "force_include": {"improvement_score", "market_deception_score"},
    },
]


def _make_custom_ensemble(config: dict) -> "CustomEnsemble":
    """Build a pseudo-ensemble that applies custom exclusions."""
    return CustomEnsemble(
        extra_exclude=config.get("extra_exclude", set()),
        force_include=config.get("force_include", set()),
        mode=config.get("mode"),
    )


class CustomEnsemble:
    """Wraps VeloPrimeEnsemble with custom forced-exclude/include logic."""

    def __init__(self, extra_exclude: set, force_include: set, mode: str | None):
        self.ensemble = VeloPrimeEnsemble()
        self.extra_exclude = extra_exclude
        self.force_include = force_include
        self.mode = mode

    def predict_race(self, runners: list[dict], macro_context: Any = None) -> list:
        if self.mode == ABLATION_SQPE_ONLY:
            return self.ensemble.predict_race(runners, macro_context=macro_context, mode=ABLATION_SQPE_ONLY)
        if self.mode == ABLATION_FULL_MINUS_DEAD:
            return self.ensemble.predict_race(runners, macro_context=macro_context, mode=ABLATION_FULL_MINUS_DEAD)

        # Custom: zero out excluded components in runner data, then run full_minus_dead
        # Since _DISABLED_COMPONENTS already blocks improvement/release/comment,
        # we temporarily patch runner data to simulate include/exclude
        patched = []
        for r in runners:
            pr = dict(r)
            for comp in self.extra_exclude:
                pr[comp] = None
            # For force_include: keep value (it's already in runner dict from verdicts)
            # but improvement_score is in _DISABLED_COMPONENTS, so we need SQPE_ONLY+patch
            patched.append(pr)

        # Use full_minus_dead which respects _DISABLED_COMPONENTS.
        # For force_include items that are in _DISABLED_COMPONENTS, we can't override
        # them without patching the module. Instead, we use a workaround: compute a
        # custom weighted score manually if the component is in _DISABLED_COMPONENTS.
        if self.force_include & _DISABLED_COMPONENTS:
            return self._manual_predict(patched, macro_context)

        return self.ensemble.predict_race(patched, macro_context=macro_context, mode=ABLATION_FULL_MINUS_DEAD)

    def _manual_predict(self, runners: list[dict], macro_context: Any) -> list:
        """
        Manual weighted probability for configs that need disabled components re-enabled.
        Computes SQPE_ONLY base, then adds force_include components at their declared weights.
        """
        # Get SQPE_ONLY predictions first
        sqpe_preds = self.ensemble.predict_race(runners, macro_context=macro_context, mode=ABLATION_SQPE_ONLY)
        sqpe_index = {p.horse_id or p.horse: p for p in sqpe_preds}

        # For each runner, build custom prob
        results = []
        for r in runners:
            horse_key = r.get("horse_id") or r.get("horse")
            sqpe_pred = sqpe_index.get(str(horse_key))
            base_sqpe = sqpe_pred.sqpe_v17_prob if sqpe_pred else r.get("sqpe_v17_prob", 0.0)

            # Include force_include components
            components = {"sqpe_v17": base_sqpe}
            w_sqpe = _WEIGHTS["sqpe_v17"]

            for comp in self.force_include:
                if comp in self.extra_exclude:
                    continue
                val = _safe_float(r.get(comp))
                if val is not None:
                    # longshot_score only at sp >= 10
                    if comp == "longshot_score" and (_safe_float(r.get("sp_dec")) or 0) < 10:
                        continue
                    components[comp] = val

            total_w = sum(_WEIGHTS.get(k, 0) for k in components)
            if total_w > 0:
                prob = sum(_WEIGHTS.get(k, 0) * v for k, v in components.items()) / total_w
            else:
                prob = base_sqpe

            # Clip
            prob = max(0.001, min(0.999, prob))

            # Create a simple result object
            class _P:
                pass
            p = _P()
            p.horse = r.get("horse", "")
            p.horse_id = r.get("horse_id", "")
            p.race_id = r.get("race_id", "")
            p.sqpe_v17_prob = base_sqpe
            p.velo_prime_prob = prob
            results.append(p)

        # Normalize
        total = sum(p.velo_prime_prob for p in results)
        if total > 0:
            for p in results:
                p.velo_prime_prob = round(p.velo_prime_prob / total, 4)
        results.sort(key=lambda p: p.velo_prime_prob, reverse=True)
        return results


# ── Data loading ───────────────────────────────────────────────────────────────

def _fetch_verdicts() -> list[dict]:
    print("  Fetching velo_verdicts ...")
    rows = _sb_get(
        "velo_verdicts",
        "race_id,generated_at,full_analysis,velo_prime_prob,decision_tier",
    )
    latest: dict[str, dict] = {}
    for row in rows:
        rid = str(row.get("race_id") or "")
        gen = str(row.get("generated_at") or "")
        if not rid:
            continue
        cur = latest.get(rid)
        if cur is None or gen > str(cur.get("generated_at") or ""):
            latest[rid] = row
    return list(latest.values())


def _fetch_races(race_ids: list[str]) -> dict[str, dict]:
    if not race_ids:
        return {}
    batch = race_ids[:500]  # limit
    id_list = ",".join(batch)
    rows = _sb_get("races", "race_id,date,race_type", {"race_id": f"in.({id_list})"})
    return {str(r["race_id"]): r for r in rows if r.get("race_id")}


def _fetch_runner_results(race_ids: list[str]) -> dict[tuple[str, str], dict]:
    if not race_ids:
        return {}
    batch = race_ids[:500]
    id_list = ",".join(batch)
    rows = _sb_get(
        "runner_results",
        "race_id,horse_id,position,sp_dec,is_winner",
        {"race_id": f"in.({id_list})"},
    )
    lookup: dict[tuple[str, str], dict] = {}
    for r in rows:
        rid = str(r.get("race_id") or "")
        hid = str(r.get("horse_id") or "")
        if rid and hid:
            lookup[(rid, hid)] = r
    return lookup


# ── Race input builder ─────────────────────────────────────────────────────────

def _build_race_inputs(verdicts: list[dict]) -> list[dict]:
    race_ids = [str(v["race_id"]) for v in verdicts if v.get("race_id")]
    print(f"  Building race inputs for {len(race_ids)} verdicts ...")
    races = _fetch_races(race_ids)
    runner_results = _fetch_runner_results(race_ids)
    print(f"  Got {len(races)} race meta, {len(runner_results)} runner results")

    race_inputs: list[dict] = []
    for verdict in verdicts:
        race_id = str(verdict["race_id"])
        race_row = races.get(race_id)
        analysis = verdict.get("full_analysis")
        if not isinstance(analysis, list) or not analysis:
            continue
        if not race_row:
            continue

        runners: list[dict] = []
        matched = 0
        min_sp = None
        for item in analysis:
            if not isinstance(item, dict):
                continue
            hid = str(item.get("horse_id") or "")
            result = runner_results.get((race_id, hid))
            sp = _safe_float((result or {}).get("sp_dec"))
            if sp is not None and sp > 0:
                min_sp = sp if min_sp is None else min(min_sp, sp)
            if result:
                matched += 1
            runners.append({
                "horse": item.get("horse") or item.get("horse_name") or "",
                "horse_id": hid,
                "race_id": race_id,
                "sqpe_v17_prob": float(item.get("sqpe_v17_prob") or 0.0),
                "improvement_score": _safe_float(item.get("improvement_score")),
                "release_window_score": _safe_float(item.get("release_day_prob")),
                "market_deception_score": _safe_float(item.get("market_deception_score")),
                "place_prob": _safe_float(item.get("place_prob")),
                "comment_intel_score": _safe_float(item.get("comment_intel_score")),
                "longshot_score": _safe_float(item.get("longshot_prob")),
                "sp_dec": sp,
                "position": _position_int((result or {}).get("position")),
                "is_winner": bool((result or {}).get("is_winner")),
            })
        if min_sp is not None:
            for r in runners:
                r["is_fav"] = r.get("sp_dec") == min_sp
        else:
            for r in runners:
                r["is_fav"] = False

        if matched == 0:
            continue

        macro = get_macro_context_for_race(
            str(race_row.get("date") or ""),
            _code_from_race_type(race_row.get("race_type")),
        )
        race_inputs.append({
            "race_id": race_id,
            "date": race_row.get("date"),
            "runners": runners,
            "macro_context": macro,
        })

    return race_inputs


# ── Evaluate one config ────────────────────────────────────────────────────────

def _evaluate_config(
    config: dict,
    race_inputs: list[dict],
    sqpe_top_per_race: dict[str, str],
) -> dict[str, Any]:
    """Run the config over all races, return metrics."""
    ens = _make_custom_ensemble(config)
    n = 0
    wins = 0
    places = 0
    profits: list[float] = []
    sps: list[float] = []
    top_changes_vs_sqpe = 0
    vp30_count = 0

    for race in race_inputs:
        preds = ens.predict_race(race["runners"], macro_context=race["macro_context"])
        if not preds:
            continue
        top = preds[0]
        top_hid = getattr(top, "horse_id", None) or getattr(top, "horse", "")
        top_vp = getattr(top, "velo_prime_prob", 0.0)

        # Find result for top pick
        top_runner = next(
            (r for r in race["runners"]
             if (str(r.get("horse_id") or "") == str(top_hid) or
                 str(r.get("horse") or "") == str(getattr(top, "horse", "")))),
            None,
        )
        if top_runner is None or top_runner.get("position") is None:
            continue

        n += 1
        is_winner = bool(top_runner.get("is_winner"))
        pos = top_runner.get("position")
        sp = _safe_float(top_runner.get("sp_dec"))
        placed = pos is not None and pos in (1, 2, 3)

        wins += 1 if is_winner else 0
        places += 1 if placed else 0
        if sp is not None:
            sps.append(sp)
            profit = (sp - 1.0) if is_winner else -1.0
            profits.append(profit)
        if top_vp >= 0.30:
            vp30_count += 1

        # Compare top pick vs SQPE_ONLY top
        sqpe_top_hid = sqpe_top_per_race.get(race["race_id"], "")
        if str(top_hid) != sqpe_top_hid:
            top_changes_vs_sqpe += 1

    sr = (wins / n) if n else None
    frame = (places / n) if n else None
    roi = (sum(profits) / n) if profits else None
    avg_sp = (sum(sps) / len(sps)) if sps else None
    med_sp = statistics.median(sps) if sps else None

    return {
        "config": config["name"],
        "description": config["description"],
        "n": n,
        "wins": wins,
        "places": places,
        "strike_rate": round(sr, 4) if sr is not None else None,
        "frame_rate": round(frame, 4) if frame is not None else None,
        "flat_roi": round(roi, 4) if roi is not None else None,
        "avg_sp": round(avg_sp, 3) if avg_sp is not None else None,
        "median_sp": round(med_sp, 3) if med_sp is not None else None,
        "vp30_count": vp30_count,
        "top_selection_changes_vs_sqpe": top_changes_vs_sqpe,
    }


def _classify_sidecar(cfg_result: dict, sqpe_result: dict) -> str:
    if cfg_result["n"] < 20:
        return "INSUFFICIENT_SAMPLE"
    sqpe_roi = sqpe_result.get("flat_roi")
    sqpe_sr = sqpe_result.get("strike_rate")
    sqpe_sp = sqpe_result.get("avg_sp")
    this_roi = cfg_result.get("flat_roi")
    this_sr = cfg_result.get("strike_rate")
    this_frame = cfg_result.get("frame_rate")
    sqpe_frame = sqpe_result.get("frame_rate")
    this_sp = cfg_result.get("avg_sp")

    if this_roi is not None and sqpe_roi is not None and this_roi > sqpe_roi:
        return "SIDECAR_HELPS_VALUE"
    if this_frame is not None and sqpe_frame is not None and this_frame > sqpe_frame and (this_roi is None or sqpe_roi is None or this_roi <= sqpe_roi):
        return "SIDECAR_HELPS_FRAME"
    if (this_sp is not None and sqpe_sp is not None
            and this_sp < sqpe_sp * 0.92
            and this_sr is not None and sqpe_sr is not None and this_sr >= sqpe_sr):
        return "SIDECAR_OVERBETS_SHORT_PRICES"
    if this_sr is not None and sqpe_sr is not None and this_sr > sqpe_sr and (this_roi is None or sqpe_roi is None or this_roi <= sqpe_roi):
        return "SIDECAR_BADGE_ONLY"
    if this_roi is not None and sqpe_roi is not None and this_roi < sqpe_roi and (this_sr is None or sqpe_sr is None or this_sr >= sqpe_sr):
        return "SIDECAR_REDUCE_CANDIDATE"
    if (this_sr is not None and sqpe_sr is not None and this_sr < sqpe_sr
            and this_roi is not None and sqpe_roi is not None and this_roi < sqpe_roi):
        return "SIDECAR_FREEZE_CANDIDATE"
    if this_roi is not None and sqpe_roi is not None and this_roi < sqpe_roi:
        return "SIDECAR_REDUCE_CANDIDATE"
    return "SQPE_CORE_KEEP"


# ── Main ───────────────────────────────────────────────────────────────────────

def run_audit() -> dict[str, Any]:
    print(f"[sqpe_alone_control_audit] Starting at {datetime.now(UTC).isoformat()}")
    verdicts = _fetch_verdicts()
    print(f"  Fetched {len(verdicts)} latest verdicts")
    race_inputs = _build_race_inputs(verdicts)
    print(f"  Built {len(race_inputs)} race inputs with outcomes")

    if not race_inputs:
        return {
            "error": "No race inputs with closed outcomes found.",
            "generated_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        }

    # Pre-compute SQPE_ONLY top picks per race for comparison
    sqpe_ens = _make_custom_ensemble(CONFIGS[0])
    sqpe_top_per_race: dict[str, str] = {}
    for race in race_inputs:
        preds = sqpe_ens.predict_race(race["runners"], macro_context=race["macro_context"])
        if preds:
            top = preds[0]
            sqpe_top_per_race[race["race_id"]] = str(getattr(top, "horse_id", "") or getattr(top, "horse", ""))

    # Evaluate all configs
    results: list[dict] = []
    sqpe_result: dict = {}
    for i, cfg in enumerate(CONFIGS):
        print(f"  Evaluating config {i+1}/{len(CONFIGS)}: {cfg['name']} ...")
        r = _evaluate_config(cfg, race_inputs, sqpe_top_per_race)
        results.append(r)
        if cfg["name"] == "SQPE_ONLY":
            sqpe_result = r

    # Classify sidecars
    sidecar_map = {
        "SQPE_PLUS_IMPROVEMENT": "improvement_score",
        "SQPE_PLUS_MDS": "market_deception_score",
        "SQPE_PLUS_PLACE": "place_prob",
        "SQPE_PLUS_LONGSHOT": "longshot_score",
        "SQPE_PLUS_IMPROVE_MDS": "improvement_score + MDS",
    }
    classifications: list[dict] = []
    for r in results:
        if r["config"] in ("SQPE_ONLY", "FULL_ENSEMBLE"):
            continue
        cls = _classify_sidecar(r, sqpe_result)
        classifications.append({
            "config": r["config"],
            "sidecar": sidecar_map.get(r["config"], r["config"]),
            "classification": cls,
            "n": r["n"],
            "strike_rate": r["strike_rate"],
            "frame_rate": r["frame_rate"],
            "flat_roi": r["flat_roi"],
            "avg_sp": r["avg_sp"],
            "top_changes_vs_sqpe": r["top_selection_changes_vs_sqpe"],
        })

    # Answers to audit questions
    sqpe_roi = sqpe_result.get("flat_roi")
    full_roi = next((r.get("flat_roi") for r in results if r["config"] == "FULL_ENSEMBLE"), None)
    full_frame = next((r.get("frame_rate") for r in results if r["config"] == "FULL_ENSEMBLE"), None)
    sqpe_frame = sqpe_result.get("frame_rate")

    qa = {
        "A_sqpe_alone_better_roi": (
            sqpe_roi is not None and full_roi is not None and sqpe_roi > full_roi
        ),
        "B_ensemble_improves_frame_but_hurts_roi": (
            full_frame is not None and sqpe_frame is not None and full_frame > sqpe_frame
            and full_roi is not None and sqpe_roi is not None and full_roi < sqpe_roi
        ),
        "C_sidecars_improve_frame": [
            c["sidecar"] for c in classifications
            if c["classification"] in ("SIDECAR_HELPS_FRAME", "SIDECAR_BADGE_ONLY")
        ],
        "D_sidecars_improve_ev": [
            c["sidecar"] for c in classifications
            if c["classification"] == "SIDECAR_HELPS_VALUE"
        ],
        "E_sidecars_overbet_short": [
            c["sidecar"] for c in classifications
            if c["classification"] == "SIDECAR_OVERBETS_SHORT_PRICES"
        ],
        "F_sidecars_badge_only": [
            c["sidecar"] for c in classifications
            if c["classification"] == "SIDECAR_BADGE_ONLY"
        ],
    }

    return {
        "generated_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "race_inputs_with_outcomes": len(race_inputs),
        "configurations": results,
        "classifications": classifications,
        "qa": qa,
    }


def write_outputs(payload: dict[str, Any]) -> None:
    OUTPUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_JSON.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    if "error" in payload:
        OUTPUT_MD.write_text(f"# SQPE Alone Control Audit\n\nERROR: {payload['error']}\n")
        return

    lines = [
        "# SQPE Alone Control Audit",
        "",
        f"- Generated: `{payload['generated_at']}`",
        f"- Race inputs with outcomes: `{payload['race_inputs_with_outcomes']}`",
        "",
        "## Configuration Comparison",
        "",
        "| Config | n | SR | Frame | Flat ROI | Avg SP | Median SP | VP30 | Changes vs SQPE |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for r in payload["configurations"]:
        def _fmt(v): return f"{v:.4f}" if v is not None else "—"
        lines.append(
            f"| {r['config']} | {r['n']} | {_fmt(r['strike_rate'])} | {_fmt(r['frame_rate'])} | "
            f"{_fmt(r['flat_roi'])} | {_fmt(r['avg_sp'])} | {_fmt(r['median_sp'])} | "
            f"{r['vp30_count']} | {r['top_selection_changes_vs_sqpe']} |"
        )
    lines += ["", "## Sidecar Classifications", "", "| Config | Sidecar | Classification | n | SR | ROI |", "|---|---|---|---:|---:|---:|"]
    for c in payload["classifications"]:
        def _fmt(v): return f"{v:.4f}" if v is not None else "—"
        lines.append(f"| {c['config']} | {c['sidecar']} | {c['classification']} | {c['n']} | {_fmt(c['strike_rate'])} | {_fmt(c['flat_roi'])} |")

    qa = payload.get("qa", {})
    lines += [
        "",
        "## Audit Questions",
        "",
        f"A. SQPE alone improves ROI vs ensemble: `{qa.get('A_sqpe_alone_better_roi')}`",
        f"B. Ensemble improves frame but hurts ROI: `{qa.get('B_ensemble_improves_frame_but_hurts_roi')}`",
        f"C. Sidecars improve frame: `{qa.get('C_sidecars_improve_frame')}`",
        f"D. Sidecars improve EV (ROI positive vs SQPE): `{qa.get('D_sidecars_improve_ev')}`",
        f"E. Sidecars overbet short prices: `{qa.get('E_sidecars_overbet_short')}`",
        f"F. Sidecars that should be badges only: `{qa.get('F_sidecars_badge_only')}`",
        "",
        "---",
        "*Audit only. No scoring or model changes.*",
    ]
    OUTPUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"  Written: {OUTPUT_JSON.name}")
    print(f"  Written: {OUTPUT_MD.name}")


def main() -> int:
    payload = run_audit()
    write_outputs(payload)

    if "error" in payload:
        print(f"ERROR: {payload['error']}")
        return 1

    print()
    print("=" * 70)
    print("SQPE ALONE CONTROL AUDIT — SUMMARY")
    print("=" * 70)
    print(f"{'Config':<30} {'n':>5} {'SR':>8} {'ROI':>8} {'Avg SP':>8}")
    print(f"{'-'*30} {'-'*5} {'-'*8} {'-'*8} {'-'*8}")
    for r in payload["configurations"]:
        def _f(v): return f"{v:.4f}" if v is not None else "    —   "
        print(f"{r['config']:<30} {r['n']:>5} {_f(r['strike_rate']):>8} {_f(r['flat_roi']):>8} {_f(r['avg_sp']):>8}")

    print()
    print("Sidecar Classifications:")
    for c in payload["classifications"]:
        print(f"  {c['config']:<30} → {c['classification']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
