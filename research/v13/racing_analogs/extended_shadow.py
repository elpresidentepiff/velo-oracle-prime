"""
extended_shadow.py — Extended Shadow Mode
==========================================
Runs the analog sidecar in parallel beside live VÉLØ.

What it does:
  1. Loads the persistent historical analog index (12-month raceform)
  2. Fetches the latest live velo_verdicts
  3. Maps each runner to a CanonicalRaceState using VÉLØ outputs
  4. Queries the historical analog index for each runner
  5. Logs: live VÉLØ view + analog memory view + agreement/disagreement
  6. Persists shadow comparison to Supabase for post-run analysis

What it does NOT do:
  - Does NOT modify VÉLØ rankings or decisions
  - Does NOT block any live operations
  - Does NOT touch the Trading Agent
  - Does NOT write to velo_verdicts

Extended shadow mode is ADVISORY ONLY until explicitly promoted.

⚠️  CLASSIFICATION: RESEARCH ONLY — DO NOT IMPORT FROM LIVE SCORING PATH
    This module must never be called from run_prime_today.py, app/main.py,
    or any endpoint that writes to velo_verdicts. It is safe to run as a
    standalone script for offline analysis only.

Env vars:
  SUPABASE_URL
  SUPABASE_SERVICE_KEY
  HISTORICAL_STATES_PICKLE  — path to states_12m_seq.pkl (default: /tmp/states_12m_seq.pkl)
"""

from __future__ import annotations

import json
import math
import os
import pickle
import time
import urllib.request
import urllib.error
from datetime import datetime, date
from typing import Any, Dict, List, Optional, Tuple

from .analog_index import AnalogIndex, Mode
from .analog_summary import AnalogSummaryBuilder
from .canonical_mapper import CanonicalMapper
from .fingerprint_features import FingerprintFeatureBuilder
from .schema import (
    AdvisoryOutput,
    AnalogSummary,
    CanonicalRaceState,
    FingerprintVector,
    Region,
    SQPEBand,
    SPBand,
)
from .vector_encoder import VectorEncoder


# ─── Supabase client ───────────────────────────────────────────────────────────

def _get_supabase_headers() -> dict:
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_KEY")
    if not url or not key:
        raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_KEY must be set")
    return {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    }


def _sb_get(path: str, params: str = "") -> List[Dict]:
    base = os.getenv("SUPABASE_URL", "").rstrip("/")
    url = f"{base}/rest/v1/{path}?{params}" if params else f"{base}/rest/v1/{path}"
    req = urllib.request.Request(url, headers=_get_supabase_headers())
    try:
        resp = urllib.request.urlopen(req)
        return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"SUPABASE GET {path} failed: {e.code} {e.reason}") from e


def _sb_post(path: str, rows: List[Dict]) -> None:
    base = os.getenv("SUPABASE_URL", "").rstrip("/")
    url = f"{base}/rest/v1/{path}"
    payload = json.dumps(rows). encode()
    req = urllib.request.Request(
        url,
        data=payload,
        headers={**_get_supabase_headers(), "Prefer": "return=minimal"},
        method="POST",
    )
    try:
        urllib.request.urlopen(req)
    except urllib.error.HTTPError as e:
        body = e.read().decode()[:500]
        raise RuntimeError(f"SUPABASE POST {path} failed ({e.code}): {body}") from e


# ─── Shadow comparison record ──────────────────────────────────────────────────

class ShadowComparison:
    """
    A single runner's side-by-side view:
      - live: VÉLØ's live verdict
      - analog: what the historical memory says
      - flags: agreement/disagreement/warning
    """

    def __init__(
        self,
        race_id: str,
        runner_id: str,
        horse: str,
        # Live VÉLØ fields
        velo_prob: Optional[float],
        velo_tier: Optional[str],
        velo_sqpe_prob: Optional[float],  # sqpe_v17_prob from runner
        velo_top_rank: bool,  # is this the top-ranked horse in the race?
        velo_confidence: Optional[str],
        velo_decision_tier: Optional[str],  # race-level decision tier
        # Analog memory fields
        analog_count: int,
        analog_top_sqpe: Optional[float],
        analog_top_sp: Optional[str],
        analog_top_win_rate: Optional[float],
        analog_top_similarity: float,
        analog_confidence: Optional[float],
        analog_recommendation: Optional[str],
        # Comparison
        agreement: str,  # AGREE / DISAGREE / NO_DATA / UNCERTAIN
        warning: Optional[str] = None,
        sqpe_source: str = "live_ensemble_prob",  # source of live SQPE signal
    ):
        self.race_id = race_id
        self.runner_id = runner_id
        self.horse = horse
        self.velo_prob = velo_prob
        self.velo_tier = velo_tier
        self.velo_sqpe_prob = velo_sqpe_prob
        self.velo_top_rank = velo_top_rank
        self.velo_confidence = velo_confidence
        self.velo_decision_tier = velo_decision_tier
        self.analog_count = analog_count
        self.analog_top_sqpe = analog_top_sqpe
        self.analog_top_sp = analog_top_sp
        self.analog_top_win_rate = analog_top_win_rate
        self.analog_top_similarity = analog_top_similarity
        self.analog_confidence = analog_confidence
        self.analog_recommendation = analog_recommendation
        self.agreement = agreement
        self.warning = warning
        self.sqpe_source = sqpe_source

    def to_dict(self) -> Dict[str, Any]:
        return {
            "race_id": self.race_id,
            "runner_id": self.runner_id,
            "horse": self.horse,
            # VÉLØ live
            "velo_prob": round(self.velo_prob, 4) if self.velo_prob else None,
            "velo_tier": self.velo_tier,
            "velo_sqpe_prob": round(self.velo_sqpe_prob, 4) if self.velo_sqpe_prob else None,
            "velo_top_rank": self.velo_top_rank,
            "velo_confidence": self.velo_confidence,
            "velo_decision_tier": self.velo_decision_tier,
            # Analog memory
            "analog_count": self.analog_count,
            "analog_top_sqpe": round(self.analog_top_sqpe, 4) if self.analog_top_sqpe else None,
            "analog_top_sp": self.analog_top_sp,
            "analog_top_win_rate": round(self.analog_top_win_rate, 4) if self.analog_top_win_rate else None,
            "analog_top_similarity": round(self.analog_top_similarity, 4),
            "analog_confidence": round(self.analog_confidence, 4) if self.analog_confidence else None,
            "analog_recommendation": self.analog_recommendation,
            # Comparison
            "agreement": self.agreement,
            "warning": self.warning,
            # Bridge
            "sqpe_source": self.sqpe_source,  # live_ensemble_prob | historical_proxy
            "signal_version": "phase35_locked",
        }

    def summary_line(self) -> str:
        agree_flag = "✅ AGREE" if self.agreement == "AGREE" else (
            "❌ DISAGREE" if self.agreement == "DISAGREE" else
            "⚠️  NO_DATA" if self.agreement == "NO_DATA" else
            f"? {self.agreement}"
        )
        velo_str = f"velo_p={self.velo_prob:.3f}" if self.velo_prob else "velo_p=None"
        analog_str = (f"ana_q={self.analog_top_sqpe:.3f}({self.analog_top_sp})"
                      if self.analog_top_sqpe else "ana_q=None")
        warn_str = f" [!{self.warning}]" if self.warning else ""
        return (f"{self.horse[:20]:20s} | {velo_str} | {analog_str} "
                f"| sim={self.analog_top_similarity:.3f} | {agree_flag}{warn_str}")


# ─── Extended Shadow Runner ───────────────────────────────────────────────────

class ExtendedShadowRunner:
    """
    Runs live velo_verdicts against the persistent historical analog index.

    Build order:
      1. load_historical_index()  — load 12-month states, build persistent index
      2. fetch_live_verdicts()   — pull latest velo_verdicts
      3. map_and_query()         — map runners, query historical index
      4. compare()                — side-by-side live vs. analog view
      5. persist()                — write shadow comparisons to Supabase
    """

    def __init__(self, historical_states_path: str = "/tmp/states_12m_seq.pkl"):
        self.historical_states_path = historical_states_path
        self.mapper = CanonicalMapper()
        self.builder = FingerprintFeatureBuilder()
        self.encoder = VectorEncoder()
        self.summer = AnalogSummaryBuilder()
        self.index: Optional[AnalogIndex] = None
        self.historical_states: List[CanonicalRaceState] = []
        self._comparisons: List[ShadowComparison] = []

    def load_historical_index(self) -> int:
        """Load 12-month states and build the persistent historical analog index."""
        if not os.path.exists(self.historical_states_path):
            raise FileNotFoundError(
                f"Historical states not found at {self.historical_states_path}. "
                "Run the 12-month sequential backfill first."
            )
        print(f"[extended_shadow] Loading historical states from {self.historical_states_path}")
        with open(self.historical_states_path, "rb") as f:
            states = pickle.load(f)
        print(f"[extended_shadow] Loaded {len(states)} historical states")

        t0 = time.time()
        self.index = AnalogIndex(mode=Mode.HISTORICAL, top_k=20, min_similarity=0.55)
        indexed = self.index.build_index(states)
        self.historical_states = states
        print(f"[extended_shadow] Built historical index: {indexed} vectors in {time.time()-t0:.1f}s")
        return indexed

    def fetch_live_verdicts(self, limit: int = 50) -> List[Dict]:
        """Fetch latest live velo_verdicts rows."""
        rows = _sb_get(
            "velo_verdicts",
            f"select=*&order=generated_at.desc&limit={limit}"
        )
        print(f"[extended_shadow] Fetched {len(rows)} live verdict rows")
        return rows

    def map_and_query(self, verdict_rows: List[Dict]) -> List[ShadowComparison]:
        """
        Map each runner from live verdicts to CanonicalRaceState,
        query the historical analog index, and build comparison records.
        """
        comparisons = []
        top_rank_horse_id = None
        race_id = None

        for row in verdict_rows:
            race_id = row.get("race_id")

            # Determine top-ranked horse for this race
            top_rank_horse_id = row.get("top_rank_horse_id")

            # Parse full_analysis
            fa_raw = row.get("full_analysis", [])
            if isinstance(fa_raw, str):
                try: fa_raw = json.loads(fa_raw)
                except: fa_raw = []
            if not fa_raw:
                continue

            region_raw = row.get("region", "uk")
            try:
                region = Region(str(region_raw).lower())
            except ValueError:
                region = Region.UK

            velo_decision_tier = row.get("decision_tier")
            velo_confidence = row.get("confidence_level")
            generated_at = row.get("generated_at", "")

            for runner_data in fa_raw:
                try:
                    # Map live runner to canonical state
                    state = self.mapper.from_velo_verdict_runner(
                        verdict_row=row,
                        runner_data=runner_data,
                        region=region,
                        selections=None,
                    )
                except Exception as exc:
                    print(f"[extended_shadow] Skip runner {runner_data.get('horse_id','?')}: {exc}")
                    continue

                # Query historical index
                analog_matches = []
                if self.index:
                    try:
                        query_fp = self.encoder.encode(state)
                        analog_matches = self.index.query(query_fp, sqpe_band_filter=False)
                    except Exception as exc:
                        print(f"[extended_shadow] Query failed for {state.runner_id}: {exc}")

                # Build comparison
                comparison = self._build_comparison(
                    state=state,
                    runner_data=runner_data,
                    top_rank_horse_id=top_rank_horse_id,
                    velo_decision_tier=velo_decision_tier,
                    velo_confidence=velo_confidence,
                    analog_matches=analog_matches,
                )
                comparisons.append(comparison)

        self._comparisons.extend(comparisons)
        return comparisons

    def _build_comparison(
        self,
        state: CanonicalRaceState,
        runner_data: Dict,
        top_rank_horse_id: Optional[str],
        velo_decision_tier: Optional[str],
        velo_confidence: Optional[str],
        analog_matches: List[Any],
    ) -> ShadowComparison:
        """Build a ShadowComparison for a single runner."""

        # ── Live VÉLØ fields ─────────────────────────────────────────────
        horse_id = runner_data.get("horse_id") or state.runner_id
        horse = runner_data.get("horse", "?")
        velo_prob = runner_data.get("velo_prime_prob")  # Ensemble output probability

        # velo_sqpe_prob: use velo_prime_prob as the live SQPE signal.
        # sqpe_v17_prob is isotonic-calibrated and falls in very_low band for ALL runners
        # (0.03-0.06 range), making it useless for discrimination.
        # velo_prime_prob has real range (0.03-0.37) and is what VÉLØ actually ranks on.
        # Tag honestly as live_ensemble_prob — not raw SQPE.
        velo_sqpe_prob = runner_data.get("velo_prime_prob")
        sqpe_source_tag = "live_ensemble_prob"

        velo_tier = runner_data.get("tier")  # may be None at runner level
        velo_top_rank = (horse_id == top_rank_horse_id)

        # ── Analog memory fields ────────────────────────────────────────
        top = analog_matches[0] if analog_matches else None
        analog_count = len(analog_matches)
        analog_top_sqpe = top.analog_sqpe if top else None
        analog_top_sp = top.analog_sp_band if top else None
        analog_top_win_rate = top.analog_win if top else None
        analog_top_similarity = top.similarity_score if top else 0.0

        # Derive analog confidence and recommendation from matches
        analog_confidence = None
        analog_recommendation = None
        if analog_matches:
            wins = [m.analog_win for m in analog_matches if m.analog_win is not None]
            if wins:
                analog_top_win_rate = sum(wins) / len(wins)
            if analog_top_similarity >= 0.85 and analog_top_win_rate is not None:
                if analog_top_win_rate >= 0.25:
                    analog_recommendation = "BACK"
                elif analog_top_win_rate >= 0.15:
                    analog_recommendation = "HOLD"
                else:
                    analog_recommendation = "PASS"
            else:
                analog_recommendation = "MONITOR"
            # Confidence: product of similarity × evidence strength
            analog_confidence = analog_top_similarity * (1.0 - abs((analog_top_sqpe or 0) - 0.35) / 0.5)
            analog_confidence = max(0.0, min(1.0, analog_confidence))

        # ── Agreement logic ──────────────────────────────────────────────
        agreement, warning = self._compute_agreement(
            velo_prob=velo_prob,
            velo_top_rank=velo_top_rank,
            velo_tier=velo_tier,
            analog_recommendation=analog_recommendation,
            analog_top_similarity=analog_top_similarity,
            analog_count=analog_count,
        )

        return ShadowComparison(
            race_id=state.race_id,
            runner_id=horse_id,
            horse=horse,
            velo_prob=velo_prob,
            velo_tier=velo_tier,
            velo_sqpe_prob=velo_sqpe_prob,
            velo_top_rank=velo_top_rank,
            velo_confidence=velo_confidence,
            velo_decision_tier=velo_decision_tier,
            analog_count=analog_count,
            analog_top_sqpe=analog_top_sqpe,
            analog_top_sp=analog_top_sp,
            analog_top_win_rate=analog_top_win_rate,
            analog_top_similarity=analog_top_similarity,
            analog_confidence=analog_confidence,
            analog_recommendation=analog_recommendation,
            agreement=agreement,
            warning=warning,
            sqpe_source=sqpe_source_tag,
        )

    def _compute_agreement(
        self,
        velo_prob: Optional[float],
        velo_top_rank: bool,
        velo_tier: Optional[str],
        analog_recommendation: Optional[str],
        analog_top_similarity: float,
        analog_count: int,
    ) -> Tuple[str, Optional[str]]:
        """Determine if VÉLØ and the analog memory agree."""
        warning = None

        if analog_count == 0:
            return "NO_DATA", "no analog matches found"

        if analog_top_similarity < 0.55:
            warning = f"low_similarity({analog_top_similarity:.3f})"
            return "UNCERTAIN", warning

        if velo_prob is None:
            return "NO_DATA", "velo_prob unavailable"

        # VÉLØ top rank → analog should agree BACK or HOLD
        if velo_top_rank:
            if analog_recommendation in ("BACK", "HOLD"):
                return "AGREE", None
            elif analog_recommendation == "PASS":
                return "DISAGREE", "velo_top_rank but analog says PASS"
            else:
                return "UNCERTAIN", None

        # VÉLØ low probability → analog should agree PASS or MONITOR
        if velo_prob < 0.10:
            if analog_recommendation in ("PASS", "MONITOR"):
                return "AGREE", None
            elif analog_recommendation == "BACK":
                return "DISAGREE", "velo_low_prob but analog says BACK"
            else:
                return "UNCERTAIN", None

        # Mid-range: both should land in same territory
        return "UNCERTAIN", "mid_range_no_strong_signal"

    def run(self, live_limit: int = 50) -> List[ShadowComparison]:
        """
        Full extended shadow run:
          1. Load historical index
          2. Fetch live verdicts
          3. Map and query
          4. Return all comparisons
        """
        t0 = time.time()
        self.load_historical_index()
        verdict_rows = self.fetch_live_verdicts(limit=live_limit)
        comparisons = self.map_and_query(verdict_rows)
        print(f"[extended_shadow] Built {len(comparisons)} comparisons in {time.time()-t0:.1f}s")
        return comparisons

    def print_report(self, comparisons: List[ShadowComparison]) -> None:
        """Print a readable shadow report."""
        print(f"\n{'='*90}")
        print(f"EXTENDED SHADOW REPORT — {len(comparisons)} runners")
        print(f"{'='*90}")

        # Agreement summary
        agree_counts = {}
        for c in comparisons:
            agree_counts[c.agreement] = agree_counts.get(c.agreement, 0) + 1
        print(f"\nAgreement distribution:")
        for k, v in sorted(agree_counts.items()):
            print(f"  {k:12s}: {v:4d} ({100*v/len(comparisons):.1f}%)")

        # Warnings
        warnings = [c for c in comparisons if c.warning]
        if warnings:
            print(f"\nWarnings ({len(warnings)}):")
            for w in warnings[:5]:
                print(f"  {w.summary_line()}")

        # Full runner list
        print(f"\n{'='*90}")
        print(f"{'Horse':20s} | {'VÉLØ':^22s} | {'Analog Memory':^30s} | {'Agree':^12s}")
        print(f"{'':20s} | {'prob':>7s} {'tier':>6s} {'top':>4s} | "
              f"{'sqpe':>7s} {'sp':>10s} {'sim':>6s} {'rec':>6s} |")
        print(f"{'-'*90}")
        for c in comparisons:
            vp = f"{c.velo_prob:.3f}" if c.velo_prob else "  None"
            vt = f"{c.velo_tier or '?':>6s}"
            tr = "★" if c.velo_top_rank else " "
            aq = f"{c.analog_top_sqpe:.3f}" if c.analog_top_sqpe else "   None"
            asp = f"{c.analog_top_sp or '?':>10s}"
            sim = f"{c.analog_top_similarity:.3f}"
            rec = f"{c.analog_recommendation or '?':>6s}"
            agree = c.agreement[:4]
            print(f"{c.horse[:20]:20s} | {vp:>7s} {vt:>6s} {tr:>4s} | "
                  f"{aq:>7s} {asp:>10s} {sim:>6s} {rec:>6s} | {agree:>12s}")

    def persist(self, comparisons: List[ShadowComparison]) -> int:
        """
        Persist shadow comparisons to Supabase.
        Writes to a dedicated shadow_log table or as JSONB to an existing table.
        """
        if not comparisons:
            print("[extended_shadow] No comparisons to persist")
            return 0

        rows = [c.to_dict() for c in comparisons]

        # Check if shadow_log table exists; if not, skip with note
        try:
            _sb_post("shadow_log", rows)
            print(f"[extended_shadow] Persisted {len(rows)} shadow comparisons")
            return len(rows)
        except Exception as e:
            # Table may not exist — log to fingerprint_signal_summary as shadow_only flag
            print(f"[extended_shadow] shadow_log table unavailable ({e}). "
                  "Writing to fingerprint_signal_summary with shadow_only flag.")
            summary_rows = []
            for c in comparisons:
                summary_rows.append({
                    "race_id": c.race_id,
                    "runner_id": c.runner_id,
                    "meeting_date": datetime.utcnow().strftime("%Y-%m-%d"),
                    "sqpe": round(c.velo_sqpe_prob, 4) if c.velo_sqpe_prob else 0.0,
                    "sqpe_band": SQPEBand.from_sqpe(c.velo_sqpe_prob or 0).value,
                    "trainer_signal_type": "unknown",
                    "analog_count": c.analog_count,
                    "analog_win_rate": round(c.analog_top_win_rate, 4) if c.analog_top_win_rate else None,
                    "confidence_score": round(c.analog_confidence, 4) if c.analog_confidence else 0.0,
                    "top_similarity": round(c.analog_top_similarity, 4),
                    "confidence": c.agreement,
                    "warnings": [c.warning] if c.warning else [],
                    "explanation": f"shadow_only: analog_rec={c.analog_recommendation}, "
                                   f"velo_prob={c.velo_prob}, velo_top={c.velo_top_rank}",
                    "shadow_only": True,
                    "feature_version": "phase35_locked",
                    "signal_version": "phase35_locked",
                })
            try:
                _sb_post("fingerprint_signal_summary", summary_rows)
                print(f"[extended_shadow] Persisted {len(summary_rows)} shadow summaries")
                return len(summary_rows)
            except Exception as e2:
                print(f"[extended_shadow] Failed to persist: {e2}")
                return 0


# ─── CLI entry point ───────────────────────────────────────────────────────────

def run_extended_shadow(live_limit: int = 50, persist: bool = True) -> List[ShadowComparison]:
    """
    Run extended shadow mode: live VÉLØ vs. historical analog memory.

    Args:
        live_limit: Number of latest velo_verdicts rows to process
        persist: Whether to write results to Supabase
    """
    states_path = os.getenv("HISTORICAL_STATES_PICKLE", "/tmp/states_12m_seq.pkl")
    runner = ExtendedShadowRunner(historical_states_path=states_path)
    comparisons = runner.run(live_limit=live_limit)
    runner.print_report(comparisons)
    if persist:
        runner.persist(comparisons)
    return comparisons


if __name__ == "__main__":
    live_limit = int(os.getenv("LIVE_LIMIT", "20"))
    comparisons = run_extended_shadow(live_limit=live_limit, persist=True)
    print(f"\n[extended_shadow] DONE — {len(comparisons)} comparisons")
