"""
VÉLØ Oracle — v17 Doctrine Feature Extractor (live inference)
==============================================================
Computes the 18 doctrine features for a single runner at prediction time,
using Racing API horse form history pulled live.

Usage:
    extractor = V17FeatureExtractor()
    features = extractor.extract(horse_id, race_context)
    # Returns dict of 18 feature values, ready to append to v16 features
"""

import logging
import os
import re
from typing import Any

import numpy as np
import requests

log = logging.getLogger("velo.v17_extractor")

RACING_API_BASE = os.getenv("RACING_API_BASE_URL", "https://api.theracingapi.com/v1").rstrip("/")
RACING_USER = os.getenv("RACING_API_USERNAME", "")
RACING_PASS = os.getenv("RACING_API_PASSWORD", "")

# Default/neutral values for features when insufficient history
DEFAULTS = {
    "runs_since_win": 5.0,
    "runs_since_place": 2.0,
    "runs_since_mkt_support": 3.0,
    "curr_or_minus_last_win_or": 0.0,
    "curr_or_minus_best_or": 0.0,
    "mark_compression_score": 0.0,
    "release_window_score": 0.0,
    "course_fit_score": 0.33,
    "going_fit_score": 0.33,
    "distance_fit_score": 0.33,
    "quiet_run_score": 0.0,
    "trainer_timing_score": 0.12,
    "jockey_switch_intent": 0.0,
    "odds_resilience_score": 3.0,
    "odds_contraction_score": 0.0,
    "decoy_support_flag": 0.0,
    "setup_run_flag": 0.0,
    "cash_run_flag": 0.0,
}


def _going_bucket(going_str: str) -> int:
    """0=fast/AW, 1=good, 2=soft, 3=heavy"""
    g = str(going_str).strip().upper()
    if any(x in g for x in ["STANDARD", "FAST", "TAPETA", "POLYTRACK"]):
        return 0
    if "HEAVY" in g or "VERY SOFT" in g:
        return 3
    if "SOFT" in g or "YIELD" in g:
        return 2
    return 1


def _parse_sp_dec(sp_str: str) -> float | None:
    if not sp_str or str(sp_str).strip() in ("", "–", "-"):
        return None
    s = str(sp_str).strip().upper().rstrip("F").rstrip("J").strip()
    if s in ("EVENS", "EVS"):
        return 2.0
    m = re.match(r"^(\d+(?:\.\d+)?)/(\d+(?:\.\d+)?)$", s)
    if m:
        return float(m.group(1)) / float(m.group(2)) + 1.0
    try:
        return float(s) + 1.0
    except ValueError:
        return None


def _safe_float(val: Any) -> float | None:
    if val is None:
        return None
    try:
        v = float(str(val).strip())
        return v if not np.isnan(v) else None
    except (ValueError, TypeError):
        return None


class V17FeatureExtractor:
    """
    Computes v17 doctrine features for a single runner using Racing API form history.

    The extractor is stateless — instantiate once, call extract() per runner.
    Results are ready to be concatenated with v16 features for v17 model scoring.
    """

    def __init__(self):
        self._session = None

    def _get_session(self) -> requests.Session:
        if self._session is None:
            s = requests.Session()
            s.auth = (RACING_USER, RACING_PASS)
            s.headers["Accept"] = "application/json"
            self._session = s
        return self._session

    def _fetch_horse_results(self, horse_id: str) -> list[dict]:
        """
        Fetch historical results for a horse from Racing API.
        Returns list of result dicts, sorted chronologically (oldest first).
        Returns empty list on any error.
        """
        try:
            session = self._get_session()
            url = f"{RACING_API_BASE}/horses/{horse_id}/results"
            resp = session.get(url, timeout=15)
            if resp.status_code == 404:
                return []
            if resp.status_code == 402:
                log.warning("Racing API 402 on horse form — subscription may not include this endpoint")
                return []
            resp.raise_for_status()
            data = resp.json()
            results = data if isinstance(data, list) else data.get("results", [])
            # Sort oldest first
            results.sort(key=lambda r: r.get("date", ""), reverse=False)
            return results
        except Exception as e:
            log.debug("Failed to fetch form for %s: %s", horse_id, e)
            return []

    def extract(
        self,
        horse_id: str,
        race_context: dict,
        trainer_recent_form: dict | None = None,
    ) -> dict[str, float]:
        """
        Compute all 18 v17 doctrine features for a runner.

        Args:
            horse_id: Racing API horse ID (e.g. "hrs_12345678")
            race_context: dict with keys: course, going, dist_f, or_num, sp_dec,
                          jockey (name string), is_fav (0/1)
            trainer_recent_form: optional dict with keys: wins, starts
                                 (trainer's recent form from race card context)

        Returns:
            dict of 18 feature values (floats/ints), all filled with defaults
            if insufficient history.
        """
        features = dict(DEFAULTS)  # start with neutrals

        results = self._fetch_horse_results(horse_id)
        if not results:
            return features

        course = race_context.get("course", "")
        going_bkt = _going_bucket(race_context.get("going", "Good"))
        dist_f = _safe_float(race_context.get("dist_f"))
        current_or = _safe_float(race_context.get("or_num"))
        current_sp = _safe_float(race_context.get("sp_dec", 10.0)) or 10.0
        current_jockey = str(race_context.get("jockey", ""))
        is_fav = int(race_context.get("is_fav", 0))

        n = len(results)
        wins = [int(str(r.get("position", "99")).strip() == "1") for r in results]
        places = [int(str(r.get("position", "99")).strip() in ("1", "2", "3")) for r in results]
        sps = [_parse_sp_dec(r.get("sp", "")) for r in results]
        ors = [_safe_float(r.get("or")) for r in results]
        ovr_btns = [_safe_float(r.get("ovr_btn", 0)) or 0.0 for r in results]
        jockeys = [str(r.get("jockey", "")) for r in results]
        courses_hist = [str(r.get("course", "")) for r in results]
        goings_hist = [_going_bucket(r.get("going", "Good")) for r in results]
        dists_hist = [_safe_float(r.get("dist_f") or r.get("distance_f")) for r in results]
        mkt_support = [int((sps[i] or 99) < 3.5) for i in range(n)]

        # ── runs_since_win / place / market_support ──
        # Count backwards: how many runs ago was the last win/place/support
        def runs_since_last(flags):
            for i in range(len(flags) - 1, -1, -1):
                if flags[i]:
                    return len(flags) - 1 - i
            return len(flags)  # never happened

        features["runs_since_win"] = float(runs_since_last(wins))
        features["runs_since_place"] = float(runs_since_last(places))
        features["runs_since_mkt_support"] = float(runs_since_last(mkt_support))

        # ── OR mark features ──
        valid_ors = [o for o in ors if o is not None]
        if valid_ors and current_or is not None:
            best_or = max(valid_ors)
            last_win_or_idx = next((i for i in range(len(wins) - 1, -1, -1) if wins[i] and ors[i] is not None), None)
            if last_win_or_idx is not None:
                features["curr_or_minus_last_win_or"] = current_or - ors[last_win_or_idx]
            features["curr_or_minus_best_or"] = current_or - best_or
            if best_or > 0:
                features["mark_compression_score"] = (best_or - current_or) / best_or

        # ── release_window_score ──
        rsw = features["runs_since_win"]
        mc = features["mark_compression_score"]
        if 3.0 <= rsw <= 10.0 and mc > 0.05:
            features["release_window_score"] = min(1.0, mc * 5.0)

        # ── course / going / distance fit ──
        same_course = [(wins[i], places[i]) for i in range(n) if courses_hist[i] == course]
        same_going = [(wins[i], places[i]) for i in range(n) if goings_hist[i] == going_bkt]
        same_dist = [
            (wins[i], places[i])
            for i in range(n)
            if dists_hist[i] is not None and dist_f is not None and abs(dists_hist[i] - dist_f) <= dist_f * 0.2
        ]

        if same_course:
            features["course_fit_score"] = sum(w + p for w, p in same_course) / len(same_course)
        if same_going:
            features["going_fit_score"] = sum(w + p for w, p in same_going) / len(same_going)
        if same_dist:
            features["distance_fit_score"] = sum(w + p for w, p in same_dist) / len(same_dist)

        # ── quiet_run_score ── (last run was a heavy beating)
        if ovr_btns and ovr_btns[-1] > 12.0:
            features["quiet_run_score"] = min(1.0, (ovr_btns[-1] - 12.0) / 20.0)

        # ── trainer_timing_score ──
        if trainer_recent_form:
            tr_wins = trainer_recent_form.get("wins", 0)
            tr_starts = trainer_recent_form.get("starts", 1)
            if tr_starts > 0:
                features["trainer_timing_score"] = tr_wins / tr_starts

        # ── jockey_switch_intent ──
        if jockeys and current_jockey and jockeys[-1] and jockeys[-1] != current_jockey:
            features["jockey_switch_intent"] = 1.0

        # ── odds_resilience_score ── (SP std dev over last 3 runs)
        recent_sps = [s for s in sps[-3:] if s is not None]
        if len(recent_sps) >= 2:
            features["odds_resilience_score"] = float(np.std(recent_sps))

        # ── odds_contraction_score ── (shortened from last run)
        valid_sps = [s for s in sps if s is not None]
        if valid_sps:
            last_sp = valid_sps[-1]
            if last_sp > 0:
                features["odds_contraction_score"] = (last_sp - current_sp) / last_sp

        # ── decoy_support_flag ── (fav with cold trainer)
        if is_fav and features["trainer_timing_score"] < 0.08:
            features["decoy_support_flag"] = 1.0

        # ── setup_run_flag ── (last run was badly beaten prep)
        if ovr_btns and ovr_btns[-1] > 15.0:
            features["setup_run_flag"] = 1.0

        # ── cash_run_flag __ (trainer in form + dry spell + mark compressed)
        if (
            features["trainer_timing_score"] > 0.15
            and 3.0 <= features["runs_since_win"] <= 6.0
            and features["mark_compression_score"] > 0.0
        ):
            features["cash_run_flag"] = 1.0

        return features
