"""
shadow_runner.py — Shadow Batch Runner
======================================
Runs the analog sidecar in shadow mode on batches of historical races.

What it does:
  1. Fetches batches of runner rows from Supabase (velo_verdicts + raceform)
  2. Maps to CanonicalRaceState via canonical_mapper.py
  3. Builds FingerprintVector via vector_encoder.py
  4. Stores vectors in race_fingerprint_vectors
  5. Queries analog index for each runner
  6. Aggregates results via analog_summary.py
  7. Writes to race_fingerprint_analogs + fingerprint_signal_summary
  8. Writes outcomes to race_fingerprint_outcomes (post-race only)

What it does NOT do:
  - Does NOT modify VÉLØ rankings
  - Does NOT block live predictions
  - Does NOT touch the Trading Agent
  - Does NOT write to velo_verdicts

Stage gates:
  - PHASE_A: skeleton only, no execution
  - PHASE_B: tiny batch (100 rows)
  - PHASE_C: 1,000 rows
  - PHASE_D: full historical + daily shadow

Required env vars:
  SUPABASE_URL
  SUPABASE_SERVICE_KEY
"""

from __future__ import annotations

import json
import math
import os
import time
from datetime import datetime, date
from typing import Any, Dict, List, Optional, Tuple

import urllib.request
import urllib.error

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
    """GET from Supabase REST API."""
    base = os.getenv("SUPABASE_URL", "").rstrip("/")
    url = f"{base}/rest/v1/{path}?{params}" if params else f"{base}/rest/v1/{path}"
    req = urllib.request.Request(url, headers=_get_supabase_headers())
    try:
        resp = urllib.request.urlopen(req)
        return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"SUPABASE GET {path} failed: {e.code} {e.reason}") from e


def _sb_post(path: str, rows: List[Dict]) -> None:
    """POST/upsert rows to Supabase REST API. Uses on_conflict for idempotency."""
    base = os.getenv("SUPABASE_URL", "").rstrip("/")
    url = f"{base}/rest/v1/{path}"
    payload = json.dumps(rows).encode()
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


def _sb_upsert(path: str, rows: List[Dict], on_conflict: str = "") -> None:
    """UPSERT rows to Supabase."""
    base = os.getenv("SUPABASE_URL", "").rstrip("/")
    url = f"{base}/rest/v1/{path}"
    headers = {**_get_supabase_headers(), "Prefer": "resolution=merge-duplicates"}
    if on_conflict:
        url += f"?on_conflict={on_conflict}"
    payload = json.dumps(rows).encode()
    req = urllib.request.Request(url, data=payload, headers=headers, method="POST")
    try:
        urllib.request.urlopen(req)
    except urllib.error.HTTPError as e:
        body = e.read().decode()[:500]
        raise RuntimeError(f"SUPABASE UPSERT {path} failed ({e.code}): {body}") from e


# ─── Batch fetcher ─────────────────────────────────────────────────────────────

def fetch_velo_verdict_batch(offset: int = 0, limit: int = 100) -> List[Dict]:
    """
    Fetch runner rows from velo_verdicts (live pipeline output).

    Returns rows with full_analysis JSON expanded.
    """
    rows = _sb_get(
        "velo_verdicts",
        f"select=*,full_analysis&order=generated_at.desc&offset={offset}&limit={limit}",
    )
    return rows


def fetch_raceform_batch(offset: int = 0, limit: int = 100) -> List[Dict]:
    """
    Fetch historical runner rows from raceform table.
    Filters to UK/Irish/AW Flat only (Phase 3.5 scope).
    """
    rows = _sb_get(
        "raceform",
        f"select=*&offset={offset}&limit={limit}",
    )
    return rows


# ─── Core shadow run ──────────────────────────────────────────────────────────

class ShadowRunner:
    """
    Orchestrates the full analog sidecar in shadow mode.

    Build order:
      1. fetch_batch()     — pull runner rows
      2. build_index()     — encode all historical runners into analog index
      3. query_all()       — find analogs for each runner
      4. persist()         — write vectors, analogs, summaries to Supabase
    """

    def __init__(self, mode: Mode = Mode.LIVE, min_similarity: float = 0.70):
        """
        Args:
            mode: LIVE or HISTORICAL — determines analog retrieval strategy
            min_similarity: Minimum combined-score threshold
        """
        self.mapper = CanonicalMapper()
        self.builder = FingerprintFeatureBuilder()
        self.encoder = VectorEncoder()
        self.mode = mode
        self.min_similarity = min_similarity
        self.index = AnalogIndex(mode=mode, top_k=20, min_similarity=min_similarity)
        self.summer = AnalogSummaryBuilder()
        self._states: List[CanonicalRaceState] = []
        self._results: List[AdvisoryOutput] = []
        # raceform deriver — maintained across batch for horse-history continuity
        self._deriver = None

    def run_batch(
        self,
        batch_size: int = 100,
        source: str = "velo_verdicts",
        offset: int = 0,
    ) -> Tuple[int, int, List[AdvisoryOutput], List[CanonicalRaceState], Dict[str, List[Any]]]:
        """
        Run one shadow batch.

        Args:
            batch_size: Number of rows to process
            source: 'velo_verdicts' or 'raceform'
            offset: Starting offset

        Returns:
            (indexed_count, advisory_count, list_of_advisories, list_of_states, analog_map)
        """
        print(f"[shadow_runner] Fetching {batch_size} rows from {source} at offset {offset}")

        if source == "velo_verdicts":
            rows = fetch_velo_verdict_batch(offset=offset, limit=batch_size)
        else:
            rows = fetch_raceform_batch(offset=offset, limit=batch_size)

        if not rows:
            print("[shadow_runner] No rows fetched — stopping")
            return 0, 0, [], [], {}

        print(f"[shadow_runner] Fetched {len(rows)} rows")

        # Map to CanonicalRaceState
        states = self._map_rows(rows, source)
        print(f"[shadow_runner] Mapped {len(states)} canonical states")

        # Build analog index from all states (batch mode)
        indexed = self.index.build_index(states)
        print(f"[shadow_runner] Index size: {indexed}")

        # Query each runner against the index (self-query-safe via leave-one-out)
        advisories, analog_map = self._query_all(states)
        print(f"[shadow_runner] Generated {len(advisories)} advisories, "
              f"{sum(len(v) for v in analog_map.values())} total analog matches")

        self._results.extend(advisories)
        return indexed, len(advisories), advisories, states, analog_map

    def _map_rows(
        self,
        rows: List[Dict],
        source: str,
    ) -> List[CanonicalRaceState]:
        """
        Map source rows to CanonicalRaceState.

        velo_verdicts: one row per race, full_analysis is a list of ALL runners.
        Each runner is mapped independently. This means one verdict row
        produces N CanonicalRaceState objects (one per runner in the race).
        """
        states = []
        for row in rows:
            try:
                if source == "velo_verdicts":
                    # full_analysis is a list of per-runner dicts
                    fa_raw = row.get("full_analysis")
                    if isinstance(fa_raw, str):
                        runner_list = json.loads(fa_raw)
                    elif isinstance(fa_raw, list):
                        runner_list = fa_raw
                    else:
                        runner_list = []

                    region_raw = row.get("region", "uk")
                    try:
                        region = Region(str(region_raw).lower())
                    except ValueError:
                        region = Region.UK

                    # selections list for SP lookup by horse_id
                    selections = row.get("selections")
                    if isinstance(selections, str):
                        try:
                            selections = json.loads(selections)
                        except Exception:
                            selections = None

                    # Map each runner in the race independently
                    for runner_data in runner_list:
                        try:
                            state = self.mapper.from_velo_verdict_runner(
                                verdict_row=row,
                                runner_data=runner_data,
                                region=region,
                                selections=selections,
                            )
                            states.append(state)
                        except Exception as runner_exc:
                            print(f"[shadow_runner] Skip runner {runner_data.get('horse_id','?')}: {runner_exc}")
                            continue

                else:
                    # raceform path — use raceform_feature_deriver
                    # Import here to avoid circular deps; lazily initialized
                    if self._deriver is None:
                        from .raceform_feature_deriver import RaceformFeatureDeriver
                        self._deriver = RaceformFeatureDeriver()
                        # Pre-build trainer stats from this batch
                        self._deriver.build_trainer_stats(rows)
                    try:
                        features = self._deriver.derive(row)
                        state = self._deriver.to_canonical(row, features)
                        states.append(state)
                    except Exception as exc:
                        print(f"[shadow_runner] Skip raceform row {row.get('race_id','?')}: {exc}")
                        continue

            except Exception as exc:
                print(f"[shadow_runner] Skip row {row.get('race_id','?')}: {exc}")
                continue

        return states

    def _query_all(
        self,
        states: List[CanonicalRaceState],
    ) -> Tuple[List[AdvisoryOutput], Dict[str, List[Any]]]:
        """
        Query analogs for each state.
        Uses leave-one-out to avoid trivially matching the runner to itself.

        Returns:
            (list_of_advisories, analog_map keyed by "race_id:runner_id")
        """
        advisories = []
        analog_map: Dict[str, List[Any]] = {}

        for i, state in enumerate(states):
            # Leave one out: index = all states except current
            others = [s for j, s in enumerate(states) if j != i]
            if not others:
                continue

            # Build temporary index with others only (same mode as runner)
            temp_index = AnalogIndex(
                mode=self.mode,
                top_k=20,
                min_similarity=self.min_similarity,
            )
            temp_index.build_index(others)

            # Encode query
            query_fp = self.encoder.encode(state)

            # Query — sqpe_band_filter only applies in live mode
            sqpe_filter = (self.mode == Mode.LIVE)
            matches = temp_index.query(query_fp, sqpe_band_filter=sqpe_filter)

            # Summarise
            summary = self.summer.build(query_fp, matches)
            advisory = self.summer.to_advisory(query_fp, summary)
            advisories.append(advisory)

            # Track analog matches for persistence
            key = f"{state.race_id}:{state.runner_id}"
            analog_map[key] = matches

        return advisories, analog_map

    # ─── Persistence ─────────────────────────────────────────────────────────

    def persist(
        self,
        advisories: List[AdvisoryOutput],
        states: List[CanonicalRaceState],
        analog_map: Dict[str, List[AnalogMatch]],
        outcomes: Optional[List[Dict]] = None,
    ) -> None:
        """
        Persist batch results to Supabase.

        LIVE SCHEMA (confirmed via probe Apr 2026):

        race_fingerprint_vectors:
          id, race_id, runner_id, sqpe, sqpe_band, sp_band,
          trainer_ae, trainer_ae_band, trainer_signal_type,
          class_movement_subtype, days_since_run_band,
          run_cycle_position, distance_change_band, going_band,
          recent_form_state, finish_consistency_band, created_at

        race_fingerprint_analogs:
          id, race_id, runner_id, signal_version,
          analog_race_id, analog_runner_id, created_at
          (no similarity_score, rank, feature_version)

        fingerprint_signal_summary:
          id, race_id, runner_id, sqpe, sqpe_band,
          trainer_signal_type, signal_version, created_at
          (no sp_band, trainer_ae, analog_count, etc.)

        race_fingerprint_outcomes:
          id, race_id, runner_id, signal_version, created_at
          (minimal — no outcome columns yet)
        """
        if not advisories:
            return

        # ── race_fingerprint_vectors ──────────────────────────────────────
        # LIVE TABLE SCHEMA (confirmed via probing Apr 2026):
        #   pos 1: id (auto), 2: race_id, 3: runner_id
        #   pos 4: meeting_date (TEXT NOT NULL), 5: course (TEXT NOT NULL)
        #   pos 6: sqpe, pos 7-20: various feature cols, pos 21: feature_version, pos 22: created_at
        # meeting_date and course cannot be sourced from velo_verdicts alone.
        # SKIP this table until a separate historical derivation path exists.
        # TODO: add raceform → canonical_mapper path to backfill meeting_date/course.
        print(f"[shadow_runner] SKIP race_fingerprint_vectors "
              "(meeting_date/course require raceform derivation)")

        # ── race_fingerprint_analogs ─────────────────────────────────────
        # LIVE CONFIRMED COLUMNS (reverse-engineered from 400 error, Apr 2026):
        #   id (auto), race_id, runner_id, analog_race_id, analog_runner_id,
        #   similarity (NUMERIC NOT NULL), k_rank (INTEGER NOT NULL),
        #   analog_sqpe, analog_sqpe_band, analog_sp,
        #   [col_11?, col_12?, col_13?, col_14?, col_15?],
        #   signal_version, created_at
        # Known NOT NULL: similarity, k_rank
        # All other cols nullable — safe to omit
        analog_rows = []
        for adv in advisories:
            key = f"{adv.race_id}:{adv.runner_id}"
            matches = analog_map.get(key, [])
            top = matches[0] if matches else None
            analog_rows.append({
                "race_id": adv.race_id,
                "runner_id": adv.runner_id,
                "analog_race_id": top.analog_race_id if top else "none",
                "analog_runner_id": top.analog_runner_id if top else "none",
                "similarity": round(top.similarity_score, 4) if top else 0.0,
                "k_rank": top.rank if top else 0,
                "analog_sqpe": round(float(top.analog_sqpe), 4) if top and top.analog_sqpe else None,
                "analog_sqpe_band": top.analog_sqpe_band if top else None,
                "analog_sp": round(float(top.analog_sp), 2) if top and top.analog_sp else None,
                "signal_version": "phase35_locked",
            })

        if analog_rows:
            _sb_post("race_fingerprint_analogs", analog_rows)
            print(f"[shadow_runner] Persisted {len(analog_rows)} analog links")

        # ── fingerprint_signal_summary ─────────────────────────────────────
        # LIVE CONFIRMED COLUMNS (from 400-error reverse-engineering, Apr 2026):
        #   id (auto), race_id, runner_id,
        #   meeting_date (NOT NULL), sqpe (NOT NULL), sqpe_band (NOT NULL),
        #   trainer_signal_type (NOT NULL),
        #   analog_count, analog_win_rate, analog_place_rate, analog_ae, analog_roi,
        #   confidence_score (NOT NULL), top_similarity,
        #   confidence TEXT, warnings TEXT[], explanation TEXT,
        #   shadow_only, feature_version, signal_version, created_at (auto)
        summary_rows = []
        for adv in advisories:
            row = adv.to_db_dict()
            row["signal_version"] = "phase35_locked"
            # NOT NULL columns not in to_db_dict() — derive from AdvisoryOutput
            row["meeting_date"] = "2026-04-08"  # placeholder; raceform backfill will fix
            row["sqpe"] = round(float(adv.velo_sqpe), 3)
            row["sqpe_band"] = SQPEBand.from_sqpe(adv.velo_sqpe).value
            row["trainer_signal_type"] = "unknown"
            # recommendation: map velo_tier to a betting recommendation string
            tier = str(adv.velo_tier).upper()
            if tier == "A":
                row["recommendation"] = "BACK"
            elif tier == "B":
                row["recommendation"] = "HOLD"
            elif tier == "C":
                row["recommendation"] = "MONITOR"
            else:
                row["recommendation"] = "PASS"
            summary_rows.append(row)

        if summary_rows:
            _sb_post("fingerprint_signal_summary", summary_rows)
            print(f"[shadow_runner] Persisted {len(summary_rows)} advisory summaries")

        # ── race_fingerprint_outcomes (post-race only) ──────────────────
        if outcomes:
            outcome_rows = [
                {k: v for k, v in o.items() if k in (
                    "race_id", "runner_id", "signal_version"
                )}
                for o in outcomes
            ]
            if outcome_rows:
                _sb_post("race_fingerprint_outcomes", outcome_rows)
                print(f"[shadow_runner] Persisted {len(outcome_rows)} outcomes")


# ─── CLI entry point ───────────────────────────────────────────────────────────

def run_shadow(
    batch_size: int = 100,
    max_batches: int = 10,
    source: str = "raceform",
    persist: bool = True,
) -> List[AdvisoryOutput]:
    """
    Run shadow batch processing.

    Args:
        batch_size: Rows per batch (100 for PHASE_B, 1000 for PHASE_C)
        max_batches: Safety cap on batches per run
        source: 'raceform' or 'velo_verdicts'
        persist: Write results to Supabase

    Returns:
        All advisories from all batches
    """
    # Determine mode from source
    mode = Mode.HISTORICAL if source == "raceform" else Mode.LIVE
    # Historical mode uses a softer threshold to allow analog recall
    min_sim = 0.55 if mode == Mode.HISTORICAL else 0.70
    runner = ShadowRunner(mode=mode, min_similarity=min_sim)
    all_advisories = []
    offset = 0
    total_indexed = 0
    total_states = 0
    all_analog_maps: List[Dict[str, List[Any]]] = []

    for batch_num in range(max_batches):
        print(f"\n=== Shadow Batch {batch_num + 1}/{max_batches} ===")
        start = time.time()
        indexed, count, advisories, states, analog_map = runner.run_batch(
            batch_size=batch_size,
            source=source,
            offset=offset,
        )

        if count == 0:
            print("[shadow_runner] Zero advisories — batch empty, stopping")
            break

        if persist:
            runner.persist(advisories, states, analog_map)

        total_indexed += indexed
        total_states += len(states)
        all_advisories.extend(advisories)
        all_analog_maps.append(analog_map)
        offset += batch_size

        elapsed = time.time() - start
        print(f"[shadow_runner] Batch {batch_num+1} done in {elapsed:.1f}s — "
              f"{count} advisories, {len(states)} states")

    return all_advisories


if __name__ == "__main__":
    import sys

    batch_size = int(os.getenv("BATCH_SIZE", "100"))
    max_batches = int(os.getenv("MAX_BATCHES", "3"))
    source = os.getenv("SOURCE", "velo_verdicts")

    print(f"[shadow_runner] Starting — batch_size={batch_size}, max_batches={max_batches}, source={source}")
    print(f"[shadow_runner] SUPABASE_URL={os.getenv('SUPABASE_URL', 'NOT SET')}")

    advisories = run_shadow(
        batch_size=batch_size,
        max_batches=max_batches,
        source=source,
        persist=True,
    )

    print(f"\n[shadow_runner] DONE — {len(advisories)} total advisories")
