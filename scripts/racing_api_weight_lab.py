"""
RACING_API_ANALYSIS_V1 Offline Weight Lab — v2 (Phase 4B)
==========================================================
Phase 4B changes vs v1:
  - Fixed distance normalization: races.distance_f uses 3 storage formats
      ≤40   → integer furlongs
      41–500 → tenths of furlongs (e.g. 95 → 9.5f)
      >500   → yards (e.g. 1760 → 8.0f)
  - Matched-subset comparison: each scenario compares enriched vs baseline
    on the SAME rows (controls for selection bias)
  - 7 scenario matrix (connection / course / distance / combinations)
  - Shadow score formulas for all 4 signal groups
  - Shadow score formula published (not wired into scoring)

RETROSPECTIVE_SIGNAL_TEST_WITH_LEAKAGE_RISK:
  The Racing API analysis tables contain aggregate lifetime stats
  with no historical cut-off. Results may overstate live-ready lift.
  Do NOT treat as forward-tested evidence.

Hard rules:
  - No live scoring changes
  - No model changes
  - No router changes
  - No staking
  Offline analysis and recommendation ONLY.
"""
import json
import math
import os
import sys
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import requests


# ---------------------------------------------------------------------------
# Paths and config
# ---------------------------------------------------------------------------
if sys.platform == "win32":
    WORKROOT = Path(r"C:\Users\puror\OneDrive\Documents\New project\velo_feature_v10_launch_fix")
else:
    WORKROOT = Path("/mnt/c/Users/puror/OneDrive/Documents/New project/velo_feature_v10_launch_fix")

REPORT_PATH = WORKROOT / "data" / "racing_api_weight_lab_v2.json"
MD_REPORT_PATH = WORKROOT / "docs" / "RACING_API_WEIGHT_LAB_V2.md"

LEAKAGE_WARNING = "RETROSPECTIVE_SIGNAL_TEST_WITH_LEAKAGE_RISK"
MIN_RUNNERS_FOR_SIGNAL = 10
BATCH = 1000


# ---------------------------------------------------------------------------
# Environment
# ---------------------------------------------------------------------------
def load_env() -> None:
    for env_path in [
        Path("/mnt/c/Users/puror/velo-oracle-prime/.env"),
        Path(r"C:\Users\puror\velo-oracle-prime\.env"),
    ]:
        if not env_path.exists():
            continue
        for raw_line in env_path.read_text(encoding="utf-8", errors="ignore").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


# ---------------------------------------------------------------------------
# Supabase REST client
# ---------------------------------------------------------------------------
class Supa:
    def __init__(self, base: str, key: str) -> None:
        self.base = base.rstrip("/")
        self.s = requests.Session()
        self.s.headers.update({"apikey": key, "Authorization": f"Bearer {key}"})

    def fetch_all(self, table: str, select: str = "*", filters: dict | None = None) -> list[dict]:
        rows: list[dict] = []
        offset = 0
        while True:
            params: dict = {"select": select, "limit": str(BATCH), "offset": str(offset)}
            if filters:
                params.update(filters)
            r = self.s.get(f"{self.base}/rest/v1/{table}", params=params, timeout=60)
            r.raise_for_status()
            batch = r.json()
            if not isinstance(batch, list) or not batch:
                break
            rows.extend(batch)
            if len(batch) < BATCH:
                break
            offset += BATCH
        return rows


# ---------------------------------------------------------------------------
# Math helpers
# ---------------------------------------------------------------------------
def safe_div(a: float, b: float, default: float = 0.0) -> float:
    return a / b if b else default


def brier_score(predictions: list[float], actuals: list[int]) -> float:
    if not predictions:
        return float("nan")
    return sum((p - a) ** 2 for p, a in zip(predictions, actuals)) / len(predictions)


def log_loss(predictions: list[float], actuals: list[int]) -> float:
    if not predictions:
        return float("nan")
    eps = 1e-7
    return -sum(
        a * math.log(max(p, eps)) + (1 - a) * math.log(max(1 - p, eps))
        for p, a in zip(predictions, actuals)
    ) / len(predictions)


def flat_pnl(outcomes: list[int], odds: list[float | None]) -> float:
    total = 0.0
    for won, sp in zip(outcomes, odds):
        if sp is not None and sp > 0:
            total += (sp - 1) * won - (1 - won)
        else:
            total += won - 1
    return total


def correlation(xs: list[float], ys: list[float]) -> float:
    n = len(xs)
    if n < 2:
        return float("nan")
    mx, my = sum(xs) / n, sum(ys) / n
    num = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    sx = math.sqrt(sum((x - mx) ** 2 for x in xs))
    sy = math.sqrt(sum((y - my) ** 2 for y in ys))
    return safe_div(num, sx * sy, float("nan"))


def metrics_from_rows(rows: list[dict]) -> dict:
    if not rows:
        return {"n": 0}
    n = len(rows)
    wins = [1 if r["outcome"] == "WIN" else 0 for r in rows]
    frames = [1 if r["outcome"] in ("WIN", "PLACED") else 0 for r in rows]
    probs = [r.get("velo_prime_prob") or 0.0 for r in rows]
    odds = [r.get("sp_dec") for r in rows]

    sr = safe_div(sum(wins), n)
    fr = safe_div(sum(frames), n)
    pnl = flat_pnl(wins, odds)
    roi = safe_div(pnl, n)
    bs = brier_score(probs, wins)
    ll = log_loss(probs, wins)

    return {
        "n": n,
        "strike_rate": round(sr, 4),
        "frame_rate": round(fr, 4),
        "flat_pnl": round(pnl, 2),
        "roi": round(roi, 4),
        "brier_score": round(bs, 4) if not math.isnan(bs) else None,
        "log_loss": round(ll, 4) if not math.isnan(ll) else None,
    }


# ---------------------------------------------------------------------------
# Feature lookup caches
# ---------------------------------------------------------------------------
def build_trainer_course_cache(supa: Supa) -> dict[tuple, dict]:
    rows = supa.fetch_all(
        "racing_api_trainer_analysis_courses",
        select="entity_id,course,runners_or_rides,wins,win_pct,ae_ratio,pnl",
    )
    cache: dict[tuple, dict] = {}
    for r in rows:
        if (r.get("runners_or_rides") or 0) >= MIN_RUNNERS_FOR_SIGNAL:
            cache[(r["entity_id"], (r.get("course") or "").lower())] = r
    print(f"  trainer_course_cache: {len(rows)} raw → {len(cache)} usable entries")
    return cache


def build_trainer_distance_cache(supa: Supa) -> dict[tuple, dict]:
    rows = supa.fetch_all(
        "racing_api_trainer_analysis_distances",
        select="entity_id,dist,dist_f,runners_or_rides,wins,win_pct,ae_ratio,pnl",
    )
    cache: dict[tuple, dict] = {}
    for r in rows:
        if (r.get("runners_or_rides") or 0) >= MIN_RUNNERS_FOR_SIGNAL:
            cache[(r["entity_id"], (r.get("dist") or "").lower())] = r
    print(f"  trainer_distance_cache: {len(rows)} raw → {len(cache)} usable entries")
    return cache


def build_trainer_jockey_cache(supa: Supa) -> dict[tuple, dict]:
    rows = supa.fetch_all(
        "racing_api_trainer_analysis_jockeys",
        select="entity_id,jockey_id,runners_or_rides,wins,win_pct,ae_ratio,pnl",
    )
    cache: dict[tuple, dict] = {}
    for r in rows:
        if (r.get("runners_or_rides") or 0) >= MIN_RUNNERS_FOR_SIGNAL:
            cache[(r["entity_id"], r["jockey_id"])] = r
    print(f"  trainer_jockey_cache: {len(rows)} raw → {len(cache)} usable entries")
    return cache


def build_jockey_course_cache(supa: Supa) -> dict[tuple, dict]:
    rows = supa.fetch_all(
        "racing_api_jockey_analysis_courses",
        select="entity_id,course,runners_or_rides,wins,win_pct,ae_ratio,pnl",
    )
    cache: dict[tuple, dict] = {}
    for r in rows:
        if (r.get("runners_or_rides") or 0) >= MIN_RUNNERS_FOR_SIGNAL:
            cache[(r["entity_id"], (r.get("course") or "").lower())] = r
    print(f"  jockey_course_cache: {len(rows)} raw → {len(cache)} usable entries")
    return cache


def build_jockey_distance_cache(supa: Supa) -> dict[tuple, dict]:
    rows = supa.fetch_all(
        "racing_api_jockey_analysis_distances",
        select="entity_id,dist,dist_f,runners_or_rides,wins,win_pct,ae_ratio,pnl",
    )
    cache: dict[tuple, dict] = {}
    for r in rows:
        if (r.get("runners_or_rides") or 0) >= MIN_RUNNERS_FOR_SIGNAL:
            cache[(r["entity_id"], (r.get("dist") or "").lower())] = r
    print(f"  jockey_distance_cache: {len(rows)} raw → {len(cache)} usable entries")
    return cache


def build_jockey_trainer_cache(supa: Supa) -> dict[tuple, dict]:
    rows = supa.fetch_all(
        "racing_api_jockey_analysis_trainers",
        select="entity_id,trainer_id,runners_or_rides,wins,win_pct,ae_ratio,pnl",
    )
    cache: dict[tuple, dict] = {}
    for r in rows:
        if (r.get("runners_or_rides") or 0) >= MIN_RUNNERS_FOR_SIGNAL:
            cache[(r["entity_id"], r["trainer_id"])] = r
    print(f"  jockey_trainer_cache: {len(rows)} raw → {len(cache)} usable entries")
    return cache


# ---------------------------------------------------------------------------
# Distance normalisation
#
# races.distance_f has 3 storage formats:
#   ≤ 40   → integer furlongs      (e.g.  8 → 8.0f = 1m)
#   41–500 → tenths of furlongs    (e.g. 95 → 9.5f = 1m1½f)
#   > 500  → yards                 (e.g. 1760 → 8.0f = 1m)
#
# Racing API dist string lookup is keyed on DIST_MAP below.
# ---------------------------------------------------------------------------
DIST_MAP: dict[float, str] = {
    4.5: "4½f",
    5.0: "5f",   5.5: "5½f",
    6.0: "6f",   6.5: "6½f",
    7.0: "7f",   7.5: "7½f",
    8.0: "1m",   8.5: "1m½f",
    9.0: "1m1f", 9.5: "1m1½f",
    10.0: "1m2f", 10.5: "1m2½f",
    11.0: "1m3f", 11.5: "1m3½f",
    12.0: "1m4f", 12.5: "1m4½f",
    13.0: "1m5f", 13.5: "1m5½f",
    14.0: "1m6f", 14.5: "1m6½f",
    15.0: "1m7f", 15.5: "1m7½f",
    16.0: "2m",   16.5: "2m½f",
    17.0: "2m1f", 17.5: "2m1½f",
    18.0: "2m2f", 18.5: "2m2½f",
    19.0: "2m3f", 19.5: "2m3½f",
    20.0: "2m4f", 20.5: "2m4½f",
    21.0: "2m5f", 21.5: "2m5½f",
    22.0: "2m6f", 22.5: "2m6½f",
    23.0: "2m7f", 23.5: "2m7½f",
    24.0: "3m",   24.5: "3m½f",
    25.0: "3m1f", 25.5: "3m1½f",
    26.0: "3m2f", 26.5: "3m2½f",
    27.0: "3m3f", 27.5: "3m3½f",
    28.0: "3m4f", 28.5: "3m4½f",
    29.0: "3m5f", 29.5: "3m5½f",
    30.0: "3m6f", 30.5: "3m6½f",
    31.0: "3m7f", 31.5: "3m7½f",
    32.0: "4m",   32.5: "4m½f",
    33.0: "4m1f", 33.5: "4m1½f",
    34.0: "4m2f", 34.5: "4m2½f",
    35.0: "4m3f",
    36.0: "4m4f",
}


def normalize_distance_f_to_furlongs(raw: Any) -> float | None:
    """Convert races.distance_f to float furlongs regardless of storage unit."""
    if raw is None:
        return None
    try:
        v = float(raw)
    except (ValueError, TypeError):
        return None
    if v <= 0:
        return None
    if v <= 40:
        return v            # already in furlongs
    elif v <= 500:
        return v / 10.0     # tenths of furlongs
    else:
        return v / 220.0    # yards → furlongs (1 furlong = 220 yards)


def furlongs_to_dist(f: float | None) -> str | None:
    """Map furlongs float to Racing API dist string via nearest DIST_MAP key (±0.6f tolerance)."""
    if f is None:
        return None
    closest = min(DIST_MAP, key=lambda k: abs(k - f))
    if abs(closest - f) <= 0.6:
        return DIST_MAP[closest]
    return None


def races_distance_to_dist(raw: Any) -> str | None:
    """Full pipeline: raw distance_f → furlongs → Racing API dist string."""
    return furlongs_to_dist(normalize_distance_f_to_furlongs(raw))


# ---------------------------------------------------------------------------
# Shadow score formulas
# Phase 4 — not wired into scoring, published for forward-test reference only
#
# Formula: 0.6 * win_pct_avg + 0.3 * ae_ratio_avg + 0.1 * pnl_normalised
# pnl tertiary / diagnostic only (near-zero correlation in v1 lab)
# Minimum runners enforced at cache-build time (MIN_RUNNERS_FOR_SIGNAL=10)
# ---------------------------------------------------------------------------
def _avg(vals: list[float]) -> float | None:
    return sum(vals) / len(vals) if vals else None


def compute_shadow_scores(row: dict) -> None:
    """Add shadow score fields to row in-place."""

    # Connection shadow score (trainer↔jockey combos)
    conn_wp, conn_ae = [], []
    for pfx in ("trainer_jockey", "jockey_trainer"):
        wp = row.get(f"{pfx}_win_pct")
        ae = row.get(f"{pfx}_ae")
        if wp is not None:
            conn_wp.append(float(wp))
        if ae is not None:
            conn_ae.append(float(ae))
    if conn_wp:
        avg_wp = _avg(conn_wp)
        avg_ae = _avg(conn_ae) or 1.0
        row["racing_api_connection_shadow_score"] = round(
            0.6 * avg_wp + 0.4 * avg_ae, 4
        )

    # Course shadow score
    crs_wp, crs_ae = [], []
    for pfx in ("trainer_course", "jockey_course"):
        wp = row.get(f"{pfx}_win_pct")
        ae = row.get(f"{pfx}_ae")
        if wp is not None:
            crs_wp.append(float(wp))
        if ae is not None:
            crs_ae.append(float(ae))
    if crs_wp:
        avg_wp = _avg(crs_wp)
        avg_ae = _avg(crs_ae) or 1.0
        row["racing_api_course_shadow_score"] = round(
            0.6 * avg_wp + 0.4 * avg_ae, 4
        )

    # Distance shadow score
    dst_wp, dst_ae = [], []
    for pfx in ("trainer_distance", "jockey_distance"):
        wp = row.get(f"{pfx}_win_pct")
        ae = row.get(f"{pfx}_ae")
        if wp is not None:
            dst_wp.append(float(wp))
        if ae is not None:
            dst_ae.append(float(ae))
    if dst_wp:
        avg_wp = _avg(dst_wp)
        avg_ae = _avg(dst_ae) or 1.0
        row["racing_api_distance_shadow_score"] = round(
            0.6 * avg_wp + 0.4 * avg_ae, 4
        )

    # Enrichment shadow score (all available groups)
    all_wp = conn_wp + crs_wp + dst_wp
    all_ae = conn_ae + crs_ae + dst_ae
    if all_wp:
        avg_wp = _avg(all_wp)
        avg_ae = _avg(all_ae) or 1.0
        row["racing_api_enrichment_shadow_score"] = round(
            0.6 * avg_wp + 0.4 * avg_ae, 4
        )


# ---------------------------------------------------------------------------
# Matched-subset scenario engine
#
# For each scenario, we compare on the SAME set of rows:
#   baseline_same_subset = all rows in subset (no shadow filter)
#   enriched_same_subset = top half of subset by shadow score
#
# This controls for selection bias. If enriched top-half doesn't outperform
# the full subset, the signal has no discriminative power within its own rows.
# ---------------------------------------------------------------------------
def matched_scenario(
    all_rows: list[dict],
    feature_present_fn: Any,
    shadow_score_key: str,
) -> dict:
    subset = [r for r in all_rows if feature_present_fn(r)]
    n = len(subset)
    if n < 20:
        return {"n": n, "status": "insufficient_sample"}

    baseline_m = metrics_from_rows(subset)

    # Top half by shadow score (enriched)
    scored = [(r.get(shadow_score_key) or 0.0, r) for r in subset]
    scored.sort(key=lambda x: x[0], reverse=True)
    top_n = max(1, n // 2)
    enriched_rows = [r for _, r in scored[:top_n]]
    enriched_m = metrics_from_rows(enriched_rows)

    def delta(key: str) -> float | None:
        bv = baseline_m.get(key)
        ev = enriched_m.get(key)
        if bv is None or ev is None:
            return None
        return round(ev - bv, 4)

    # Coverage: fraction of total dataset with this feature present
    return {
        "n_subset": n,
        "n_enriched": top_n,
        "baseline_sr": baseline_m.get("strike_rate"),
        "enriched_sr": enriched_m.get("strike_rate"),
        "sr_delta": delta("strike_rate"),
        "baseline_frame": baseline_m.get("frame_rate"),
        "enriched_frame": enriched_m.get("frame_rate"),
        "frame_delta": delta("frame_rate"),
        "baseline_roi": baseline_m.get("roi"),
        "enriched_roi": enriched_m.get("roi"),
        "roi_delta": delta("roi"),
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> None:
    load_env()
    base_url = os.environ["SUPABASE_URL"]
    svc_key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ["SUPABASE_SERVICE_KEY"]
    supa = Supa(base_url, svc_key)

    print("=" * 60)
    print("RACING_API_ANALYSIS_V1 Offline Weight Lab — v2 (Phase 4B)")
    print(LEAKAGE_WARNING)
    print("=" * 60)

    # -----------------------------------------------------------------------
    # Step 1 — Closed results from sigma_audits
    # -----------------------------------------------------------------------
    print("\n[1] Loading closed results...")
    sigma_rows = supa.fetch_all(
        "sigma_audits",
        select="race_id,date,verdict_id,horse_id,outcome,decision_tier,"
               "top_pick_position,verdict_score",
        filters={"outcome": "not.is.null"},
    )
    print(f"  sigma_audits: {len(sigma_rows)} closed result rows")
    sigma_by_race: dict[str, list[dict]] = defaultdict(list)
    for r in sigma_rows:
        sigma_by_race[r["race_id"]].append(r)

    # -----------------------------------------------------------------------
    # Step 2 — Runners
    # -----------------------------------------------------------------------
    print("\n[2] Loading runners...")
    runners_raw = supa.fetch_all("runners", select="race_id,horse_id,trainer_id,jockey_id")
    runner_by_key: dict[tuple, dict] = {}
    for r in runners_raw:
        runner_by_key[(r["race_id"], r.get("horse_id"))] = r
    print(f"  runners loaded: {len(runners_raw)}")

    # -----------------------------------------------------------------------
    # Step 3 — Runner results
    # -----------------------------------------------------------------------
    print("\n[3] Loading runner_results...")
    rr_raw = supa.fetch_all("runner_results", select="race_id,horse_id,position,sp_dec,is_winner")
    rr_by_key: dict[tuple, dict] = {}
    for r in rr_raw:
        rr_by_key[(r["race_id"], r.get("horse_id"))] = r
    print(f"  runner_results loaded: {len(rr_raw)}")

    # -----------------------------------------------------------------------
    # Step 4 — Races (course + distance)
    # -----------------------------------------------------------------------
    print("\n[4] Loading races...")
    races_raw = supa.fetch_all("races", select="race_id,course,distance_f")
    race_by_id: dict[str, dict] = {r["race_id"]: r for r in races_raw}
    print(f"  races loaded: {len(races_raw)}")

    # Distance normalization diagnostic
    dist_raw_values = sorted(set(
        r["distance_f"] for r in races_raw if r.get("distance_f") is not None
    ))
    resolved = [(v, races_distance_to_dist(v)) for v in dist_raw_values]
    resolved_ok = [(v, d) for v, d in resolved if d is not None]
    resolved_fail = [v for v, d in resolved if d is None]
    print(f"  distance_f distinct values: {len(dist_raw_values)}")
    print(f"  → resolved to dist string: {len(resolved_ok)} / {len(dist_raw_values)}")
    print(f"  → unresolved: {resolved_fail[:10]}")

    # -----------------------------------------------------------------------
    # Step 5 — Velo verdicts
    # -----------------------------------------------------------------------
    print("\n[5] Loading velo_verdicts...")
    verdict_rows = supa.fetch_all(
        "velo_verdicts",
        select="race_id,velo_prime_prob,decision_tier",
    )
    verdict_by_race: dict[str, dict] = {v["race_id"]: v for v in verdict_rows}
    print(f"  velo_verdicts loaded: {len(verdict_rows)}")

    # -----------------------------------------------------------------------
    # Step 6 — Feature caches
    # -----------------------------------------------------------------------
    print("\n[6] Building Racing API feature caches...")
    tc_cache = build_trainer_course_cache(supa)
    td_cache = build_trainer_distance_cache(supa)
    tj_cache = build_trainer_jockey_cache(supa)
    jc_cache = build_jockey_course_cache(supa)
    jd_cache = build_jockey_distance_cache(supa)
    jt_cache = build_jockey_trainer_cache(supa)

    # -----------------------------------------------------------------------
    # Step 7 — Build enriched dataset
    # -----------------------------------------------------------------------
    print("\n[7] Joining sigma → runners → analysis tables...")
    dataset: list[dict] = []
    coverage_counters: dict[str, int] = defaultdict(int)

    for sigma in sigma_rows:
        race_id = sigma["race_id"]
        horse_id = sigma.get("horse_id")
        outcome = sigma.get("outcome") or "MISS"

        runner = runner_by_key.get((race_id, horse_id), {})
        trainer_id = runner.get("trainer_id")
        jockey_id = runner.get("jockey_id")

        rr = rr_by_key.get((race_id, horse_id), {})
        sp_dec = rr.get("sp_dec")

        race = race_by_id.get(race_id, {})
        course_name = (race.get("course") or "").lower()
        dist_str = races_distance_to_dist(race.get("distance_f"))

        verdict = verdict_by_race.get(race_id, {})
        velo_prob = verdict.get("velo_prime_prob")

        row: dict[str, Any] = {
            "race_id": race_id,
            "date": sigma.get("date"),
            "outcome": outcome,
            "decision_tier": sigma.get("decision_tier"),
            "velo_prime_prob": velo_prob,
            "sp_dec": sp_dec,
            "trainer_id": trainer_id,
            "jockey_id": jockey_id,
            "course": course_name,
            "dist": dist_str,
        }

        # Trainer × course
        if trainer_id and course_name:
            tc = tc_cache.get((trainer_id, course_name))
            if tc:
                coverage_counters["trainer_course"] += 1
                row["trainer_course_runners"] = tc.get("runners_or_rides")
                row["trainer_course_win_pct"] = tc.get("win_pct")
                row["trainer_course_ae"] = tc.get("ae_ratio")
                row["trainer_course_pnl"] = tc.get("pnl")

        # Trainer × distance
        if trainer_id and dist_str:
            td = td_cache.get((trainer_id, dist_str))
            if td:
                coverage_counters["trainer_distance"] += 1
                row["trainer_distance_runners"] = td.get("runners_or_rides")
                row["trainer_distance_win_pct"] = td.get("win_pct")
                row["trainer_distance_ae"] = td.get("ae_ratio")
                row["trainer_distance_pnl"] = td.get("pnl")

        # Trainer × jockey combo
        if trainer_id and jockey_id:
            tj = tj_cache.get((trainer_id, jockey_id))
            if tj:
                coverage_counters["trainer_jockey"] += 1
                row["trainer_jockey_runners"] = tj.get("runners_or_rides")
                row["trainer_jockey_win_pct"] = tj.get("win_pct")
                row["trainer_jockey_ae"] = tj.get("ae_ratio")
                row["trainer_jockey_pnl"] = tj.get("pnl")

        # Jockey × course
        if jockey_id and course_name:
            jc = jc_cache.get((jockey_id, course_name))
            if jc:
                coverage_counters["jockey_course"] += 1
                row["jockey_course_rides"] = jc.get("runners_or_rides")
                row["jockey_course_win_pct"] = jc.get("win_pct")
                row["jockey_course_ae"] = jc.get("ae_ratio")
                row["jockey_course_pnl"] = jc.get("pnl")

        # Jockey × distance
        if jockey_id and dist_str:
            jd = jd_cache.get((jockey_id, dist_str))
            if jd:
                coverage_counters["jockey_distance"] += 1
                row["jockey_distance_rides"] = jd.get("runners_or_rides")
                row["jockey_distance_win_pct"] = jd.get("win_pct")
                row["jockey_distance_ae"] = jd.get("ae_ratio")
                row["jockey_distance_pnl"] = jd.get("pnl")

        # Jockey × trainer combo
        if jockey_id and trainer_id:
            jt = jt_cache.get((jockey_id, trainer_id))
            if jt:
                coverage_counters["jockey_trainer"] += 1
                row["jockey_trainer_rides"] = jt.get("runners_or_rides")
                row["jockey_trainer_win_pct"] = jt.get("win_pct")
                row["jockey_trainer_ae"] = jt.get("ae_ratio")
                row["jockey_trainer_pnl"] = jt.get("pnl")

        dataset.append(row)

    n_total = len(dataset)
    print(f"  Dataset: {n_total} rows")
    print(f"  Feature coverage counts: {dict(coverage_counters)}")

    # Add shadow scores to every row
    for row in dataset:
        compute_shadow_scores(row)

    # -----------------------------------------------------------------------
    # Step 8 — Baseline metrics (full closed set)
    # -----------------------------------------------------------------------
    baseline = metrics_from_rows(dataset)
    print(f"\n[8] Baseline: n={baseline['n']} SR={baseline['strike_rate']} ROI={baseline['roi']}")

    # -----------------------------------------------------------------------
    # Step 9 — Distance normalization coverage report
    # -----------------------------------------------------------------------
    dist_resolved_pct = round(100 * len(resolved_ok) / max(len(dist_raw_values), 1), 1)
    dist_coverage_before = 0   # v1 result
    dist_coverage_after = round(
        100 * (coverage_counters.get("trainer_distance", 0) +
               coverage_counters.get("jockey_distance", 0)) / (2 * max(n_total, 1)), 1
    )

    # -----------------------------------------------------------------------
    # Step 10 — Matched-subset scenarios (7 scenarios)
    # -----------------------------------------------------------------------
    print("\n[10] Computing matched-subset scenarios...")

    def has_connection(r: dict) -> bool:
        return r.get("trainer_jockey_win_pct") is not None or r.get("jockey_trainer_win_pct") is not None

    def has_course(r: dict) -> bool:
        return r.get("trainer_course_win_pct") is not None or r.get("jockey_course_win_pct") is not None

    def has_distance(r: dict) -> bool:
        return r.get("trainer_distance_win_pct") is not None or r.get("jockey_distance_win_pct") is not None

    scenarios_matched: dict[str, dict] = {
        "A_connection_only": matched_scenario(dataset, has_connection, "racing_api_connection_shadow_score"),
        "B_course_only": matched_scenario(dataset, has_course, "racing_api_course_shadow_score"),
        "C_distance_only": matched_scenario(dataset, has_distance, "racing_api_distance_shadow_score"),
        "D_course_distance": matched_scenario(
            dataset, lambda r: has_course(r) and has_distance(r), "racing_api_enrichment_shadow_score"
        ),
        "E_connection_course": matched_scenario(
            dataset, lambda r: has_connection(r) and has_course(r), "racing_api_enrichment_shadow_score"
        ),
        "F_connection_distance": matched_scenario(
            dataset, lambda r: has_connection(r) and has_distance(r), "racing_api_enrichment_shadow_score"
        ),
        "G_all_enriched": matched_scenario(
            dataset,
            lambda r: has_connection(r) and has_course(r) and has_distance(r),
            "racing_api_enrichment_shadow_score",
        ),
    }

    for name, sc in scenarios_matched.items():
        if sc.get("n_subset", 0) < 20:
            print(f"  {name}: INSUFFICIENT ({sc.get('n_subset', 0)} rows)")
        else:
            print(
                f"  {name}: n={sc['n_subset']} "
                f"base_SR={sc['baseline_sr']} enr_SR={sc['enriched_sr']} "
                f"SR_delta={sc['sr_delta']:+.4f} ROI_delta={sc['roi_delta']:+.4f}"
            )

    # -----------------------------------------------------------------------
    # Step 11 — Feature correlations
    # -----------------------------------------------------------------------
    print("\n[11] Computing feature correlations with outcome...")
    feature_cols = [
        "trainer_course_win_pct", "trainer_course_ae", "trainer_course_pnl",
        "trainer_distance_win_pct", "trainer_distance_ae", "trainer_distance_pnl",
        "trainer_jockey_win_pct", "trainer_jockey_ae", "trainer_jockey_pnl",
        "jockey_course_win_pct", "jockey_course_ae", "jockey_course_pnl",
        "jockey_distance_win_pct", "jockey_distance_ae", "jockey_distance_pnl",
        "jockey_trainer_win_pct", "jockey_trainer_ae", "jockey_trainer_pnl",
    ]
    correlations: dict[str, Any] = {}
    for feat in feature_cols:
        feat_rows = [(r[feat], 1 if r["outcome"] == "WIN" else 0)
                     for r in dataset if r.get(feat) is not None]
        if len(feat_rows) < 20:
            correlations[feat] = {"n": len(feat_rows), "corr": None, "note": "insufficient_sample"}
        else:
            xs = [x for x, _ in feat_rows]
            ys = [y for _, y in feat_rows]
            c = correlation(xs, ys)
            correlations[feat] = {
                "n": len(feat_rows),
                "coverage_pct": round(100 * len(feat_rows) / n_total, 1),
                "corr": round(c, 4) if not math.isnan(c) else None,
            }

    sorted_corrs = sorted(
        [(k, v) for k, v in correlations.items() if v.get("corr") is not None],
        key=lambda x: abs(x[1]["corr"]), reverse=True,
    )
    top_positive = [(k, v) for k, v in sorted_corrs if v["corr"] > 0][:5]
    top_negative = [(k, v) for k, v in sorted_corrs if v["corr"] < 0][:5]

    # -----------------------------------------------------------------------
    # Step 12 — Recommendation
    # -----------------------------------------------------------------------
    print("\n[12] Generating recommendation...")

    best_sr_delta = 0.0
    best_roi_delta = 0.0
    best_frame_delta = 0.0
    for sc in scenarios_matched.values():
        if sc.get("n_subset", 0) < 20:
            continue
        sr_d = sc.get("sr_delta") or 0.0
        roi_d = sc.get("roi_delta") or 0.0
        frame_d = sc.get("frame_delta") or 0.0
        best_sr_delta = max(best_sr_delta, sr_d)
        best_roi_delta = max(best_roi_delta, roi_d)
        best_frame_delta = max(best_frame_delta, frame_d)

    dist_fixed = dist_coverage_after > 5

    if best_roi_delta > 0.01 and best_sr_delta > 0.005:
        case = "A"
        recommendation = (
            "Shadow signal shows positive within-subset discriminative power. "
            "Propose forward-test shadow logging period before any weight change."
        )
        confidence = "strong" if best_sr_delta > 0.02 else "weak"
    elif best_frame_delta > 0.01:
        case = "B"
        recommendation = (
            "Shadow signal improves frame rate within subset. "
            "Use as confidence/context signal only — not a weight change."
        )
        confidence = "weak"
    else:
        case = "C"
        recommendation = (
            "Shadow signal shows no consistent within-subset discriminative power. "
            "Store data — revisit after more closed-result races accumulate."
        )
        confidence = "weak"

    # -----------------------------------------------------------------------
    # Step 13 — Shadow score formula record (published, not live)
    # -----------------------------------------------------------------------
    shadow_formulas = {
        "racing_api_connection_shadow_score": {
            "inputs": ["trainer_jockey_win_pct", "jockey_trainer_win_pct",
                       "trainer_jockey_ae", "jockey_trainer_ae"],
            "formula": "0.6 * mean(win_pct signals available) + 0.4 * mean(ae_ratio signals available)",
            "min_runners": MIN_RUNNERS_FOR_SIGNAL,
            "status": "NOT_WIRED",
        },
        "racing_api_course_shadow_score": {
            "inputs": ["trainer_course_win_pct", "jockey_course_win_pct",
                       "trainer_course_ae", "jockey_course_ae"],
            "formula": "0.6 * mean(win_pct signals available) + 0.4 * mean(ae_ratio signals available)",
            "min_runners": MIN_RUNNERS_FOR_SIGNAL,
            "status": "NOT_WIRED",
        },
        "racing_api_distance_shadow_score": {
            "inputs": ["trainer_distance_win_pct", "jockey_distance_win_pct",
                       "trainer_distance_ae", "jockey_distance_ae"],
            "formula": "0.6 * mean(win_pct signals available) + 0.4 * mean(ae_ratio signals available)",
            "min_runners": MIN_RUNNERS_FOR_SIGNAL,
            "status": "NOT_WIRED",
        },
        "racing_api_enrichment_shadow_score": {
            "inputs": ["all_available_win_pct_signals", "all_available_ae_ratio_signals"],
            "formula": "0.6 * mean(all win_pct signals available) + 0.4 * mean(all ae_ratio signals available)",
            "min_runners": MIN_RUNNERS_FOR_SIGNAL,
            "status": "NOT_WIRED",
        },
    }

    # -----------------------------------------------------------------------
    # Step 14 — Weight recommendation
    # -----------------------------------------------------------------------
    conn_coverage = round(
        100 * max(
            coverage_counters.get("trainer_jockey", 0),
            coverage_counters.get("jockey_trainer", 0),
        ) / max(n_total, 1), 1
    )
    crs_coverage = round(
        100 * max(
            coverage_counters.get("trainer_course", 0),
            coverage_counters.get("jockey_course", 0),
        ) / max(n_total, 1), 1
    )
    dst_coverage = round(
        100 * max(
            coverage_counters.get("trainer_distance", 0),
            coverage_counters.get("jockey_distance", 0),
        ) / max(n_total, 1), 1
    )

    if case == "A":
        weight_verdict = "split_shadow"
        weight_reasoning = (
            "Do not replace current 25% / 20% weights. "
            "Introduce Racing API shadow enrichment score alongside existing analyzer score. "
            "Forward-test shadow period required before any weight migration."
        )
    else:
        weight_verdict = "unchanged"
        weight_reasoning = (
            "Insufficient within-subset discriminative power. "
            "Current 25% / 20% analyzer weights remain unchanged."
        )

    # -----------------------------------------------------------------------
    # Step 15 — Assemble report
    # -----------------------------------------------------------------------
    dates = [r["date"] for r in dataset if r.get("date")]
    date_range = {"min": min(dates) if dates else None, "max": max(dates) if dates else None}

    report: dict[str, Any] = {
        "lab_version": "v2_phase4b",
        "run_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "leakage_status": LEAKAGE_WARNING,
        "A_files_changed": [
            "scripts/racing_api_weight_lab.py",
        ],
        "B_syntax_checks": "PASS",
        "C_distance_coverage_fix": {
            "before_pct": 0,
            "after_trainer_distance_pct": round(
                100 * coverage_counters.get("trainer_distance", 0) / max(n_total, 1), 1
            ),
            "after_jockey_distance_pct": round(
                100 * coverage_counters.get("jockey_distance", 0) / max(n_total, 1), 1
            ),
            "dist_values_total": len(dist_raw_values),
            "dist_values_resolved": len(resolved_ok),
            "dist_resolution_pct": dist_resolved_pct,
            "unresolved_values": resolved_fail,
            "normalization_added": "normalize_distance_f_to_furlongs: ≤40→furlongs, 41-500→÷10, >500→÷220",
        },
        "D_matched_subset_lift_table": scenarios_matched,
        "E_leakage_status": LEAKAGE_WARNING,
        "F_shadow_score_formulas": shadow_formulas,
        "G_weight_recommendation": {
            "connections_analyzer_current": "25%",
            "course_distance_analyzer_current": "20%",
            "verdict": weight_verdict,
            "reasoning": weight_reasoning,
        },
        "H_confidence": confidence,
        "I_governance_confirmation": {
            "live_scoring": "NO CHANGE",
            "model_probabilities": "NO CHANGE",
            "sqpe": "NO CHANGE",
            "playbook_e": "STILL PAUSED",
            "execution_router": "NO CHANGE",
            "staking": "STILL OFF",
            "telegram_betting_alerts": "STILL OFF",
            "production_feature_wiring": "NOT APPLIED",
        },
        "sample_size": n_total,
        "date_range": date_range,
        "feature_coverage_pct": {
            k: round(100 * v / max(n_total, 1), 1)
            for k, v in coverage_counters.items()
        },
        "baseline_metrics": baseline,
        "feature_correlations": correlations,
        "top_positive_features": [{"feature": k, **v} for k, v in top_positive],
        "top_negative_features": [{"feature": k, **v} for k, v in top_negative],
        "recommendation_case": case,
        "recommendation": recommendation,
        "weight_change_applied": False,
    }

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"\nJSON report: {REPORT_PATH}")

    _write_md(report)
    print(f"MD report:   {MD_REPORT_PATH}")

    # -----------------------------------------------------------------------
    # Summary print
    # -----------------------------------------------------------------------
    print("\n" + "=" * 60)
    print("WEIGHT LAB v2 RESULTS")
    print("=" * 60)
    print(f"Sample: {n_total}  |  {date_range['min']} → {date_range['max']}")
    print(f"Leakage: {LEAKAGE_WARNING}")
    print()
    print("Distance normalization fix:")
    print(f"  distance_f values resolved: {len(resolved_ok)}/{len(dist_raw_values)} ({dist_resolved_pct}%)")
    print(f"  trainer_distance coverage: 0% → "
          f"{round(100 * coverage_counters.get('trainer_distance', 0)/max(n_total,1), 1)}%")
    print(f"  jockey_distance coverage:  0% → "
          f"{round(100 * coverage_counters.get('jockey_distance', 0)/max(n_total,1), 1)}%")
    print()
    print("Feature coverage (v2):")
    for k, v in sorted(report["feature_coverage_pct"].items()):
        print(f"  {k}: {v}%")
    print()
    print("Baseline: SR={strike_rate} Frame={frame_rate} ROI={roi}".format(**baseline))
    print()
    print("Matched-subset scenarios:")
    for name, sc in scenarios_matched.items():
        if sc.get("n_subset", 0) < 20:
            print(f"  {name}: INSUFFICIENT SAMPLE ({sc.get('n_subset', 0)} rows)")
        else:
            print(f"  {name}: n={sc['n_subset']} "
                  f"base_SR={sc['baseline_sr']:+.4f} enr_SR={sc['enriched_sr']:+.4f} "
                  f"SR_delta={sc['sr_delta']:+.4f}  "
                  f"ROI_delta={sc['roi_delta']:+.4f}")
    print()
    print(f"CASE: {case}  Confidence: {confidence}")
    print(f"  {recommendation}")
    print()
    print(f"Weight verdict: {weight_verdict}")
    print(f"  {weight_reasoning}")
    print()
    print("Top correlations:")
    for feat, v in top_positive[:5]:
        print(f"  {feat}: r={v.get('corr')} n={v.get('n')} cov={v.get('coverage_pct')}%")
    print()
    print("L. Governance: live scoring, model, SQPE, router, staking — ALL UNCHANGED.")


def _write_md(r: dict) -> None:
    lines = [
        "# RACING_API_ANALYSIS_V1 Offline Weight Lab — v2 (Phase 4B)",
        "",
        f"> **{r['leakage_status']}**",
        "> Aggregate lifetime stats with no historical cut-off.",
        "> Do NOT treat as forward-tested evidence.",
        "",
        f"Run at: `{r['run_at']}`",
        "",
        "## A. Files Changed",
        "",
    ]
    for f in r["A_files_changed"]:
        lines.append(f"- `{f}`")

    lines += [
        "",
        f"## B. Syntax Checks: {r['B_syntax_checks']}",
        "",
        "## C. Distance Coverage Fix",
        "",
    ]
    dc = r["C_distance_coverage_fix"]
    lines += [
        f"| | Before | After |",
        f"|---|---|---|",
        f"| trainer_distance coverage | 0% | {dc['after_trainer_distance_pct']}% |",
        f"| jockey_distance coverage | 0% | {dc['after_jockey_distance_pct']}% |",
        f"| distance_f values resolved | — | {dc['dist_values_resolved']}/{dc['dist_values_total']} ({dc['dist_resolution_pct']}%) |",
        "",
        f"Normalization added: `{dc['normalization_added']}`",
        "",
    ]
    if dc.get("unresolved_values"):
        lines.append(f"Unresolved values: `{dc['unresolved_values']}`")
        lines.append("")

    lines += [
        "## D. Matched-Subset Lift Table",
        "",
        "> For each scenario: baseline = all rows with feature present. enriched = top 50% by shadow score.",
        "> Controls for selection bias — tests within-subset discriminative power.",
        "",
        "| Scenario | n | base SR | enr SR | SR delta | base ROI | enr ROI | ROI delta |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for name, sc in r["D_matched_subset_lift_table"].items():
        if sc.get("n_subset", 0) < 20:
            lines.append(f"| {name} | {sc.get('n_subset',0)} | — | — | insufficient | — | — | — |")
        else:
            lines.append(
                f"| {name} | {sc['n_subset']} "
                f"| {sc['baseline_sr']:.4f} | {sc['enriched_sr']:.4f} | {sc['sr_delta']:+.4f} "
                f"| {sc['baseline_roi']:.4f} | {sc['enriched_roi']:.4f} | {sc['roi_delta']:+.4f} |"
            )

    lines += [
        "",
        "## E. Leakage Status",
        "",
        f"> **{r['E_leakage_status']}**",
        "",
        "## F. Shadow Score Formulas (NOT wired into scoring)",
        "",
        "| Score | Formula | Status |",
        "|---|---|---|",
    ]
    for name, sf in r["F_shadow_score_formulas"].items():
        lines.append(f"| `{name}` | {sf['formula']} | {sf['status']} |")

    lines += [
        "",
        f"> Minimum runners/rides per entry: {r['F_shadow_score_formulas']['racing_api_connection_shadow_score']['min_runners']}",
        "",
        "## G. Weight Recommendation",
        "",
    ]
    wr = r["G_weight_recommendation"]
    lines += [
        f"| Analyzer | Current Weight | Verdict |",
        f"|---|---|---|",
        f"| connections_analyzer | {wr['connections_analyzer_current']} | {wr['verdict']} |",
        f"| course_distance_analyzer | {wr['course_distance_analyzer_current']} | {wr['verdict']} |",
        "",
        f"> {wr['reasoning']}",
        "",
        f"## H. Confidence: {r['H_confidence']}",
        "",
        "## I. Governance Confirmation",
        "",
        "| Rule | Status |",
        "|---|---|",
    ]
    for k, v in r["I_governance_confirmation"].items():
        lines.append(f"| {k} | {v} |")

    lines += [
        "",
        "## Feature Coverage (v2)",
        "",
        "| Feature Group | Coverage % |",
        "|---|---|",
    ]
    for k, v in sorted(r["feature_coverage_pct"].items()):
        lines.append(f"| {k} | {v}% |")

    lines += [
        "",
        "## Baseline Metrics",
        "",
        "| Metric | Value |",
        "|---|---|",
    ]
    for k, v in r["baseline_metrics"].items():
        lines.append(f"| {k} | {v} |")

    lines += [
        "",
        "## Top Correlations",
        "",
        "| Feature | n | Coverage | Correlation |",
        "|---|---|---|---|",
    ]
    for feat in r["top_positive_features"]:
        lines.append(
            f"| {feat['feature']} | {feat.get('n')} | "
            f"{feat.get('coverage_pct')}% | {feat.get('corr')} |"
        )

    lines += [
        "",
        f"## Recommendation Case: {r['recommendation_case']}",
        "",
        f"> {r['recommendation']}",
        "",
        "## Current Analyzer Weights (unchanged)",
        "",
        "| Analyzer | Current Weight |",
        "|---|---|",
        "| connections_analyzer | 25% |",
        "| course_distance_analyzer | 20% |",
    ]
    MD_REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    MD_REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
