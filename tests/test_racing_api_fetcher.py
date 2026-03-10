"""
Tests for workers/racing_api_fetcher.py
"""
import pytest
from unittest.mock import MagicMock, patch
import sys
import os

# Ensure workers is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from workers.racing_api_fetcher import (
    TokenBucket,
    _calculate_differentials,
    _enrich_runners,
)


# ─────────────────────────────────────────────
# TokenBucket
# ─────────────────────────────────────────────
class TestTokenBucket:
    def test_acquires_without_blocking_when_full(self):
        bucket = TokenBucket(rate=5)
        # Should not raise or hang
        for _ in range(5):
            bucket.acquire()

    def test_rate_is_respected(self):
        import time
        bucket = TokenBucket(rate=5)
        # Drain the bucket
        for _ in range(5):
            bucket.acquire()
        # Next acquire should take ~0.2s
        start = time.monotonic()
        bucket.acquire()
        elapsed = time.monotonic() - start
        assert elapsed >= 0.15, f"Expected ~0.2s wait, got {elapsed:.3f}s"


# ─────────────────────────────────────────────
# Differential calculations
# ─────────────────────────────────────────────
class TestCalculateDifferentials:
    def test_both_present(self):
        runner = {"ts": 110, "rpr": 105, "or": 100}
        result = _calculate_differentials(runner)
        assert result["ts_vs_or"] == 10.0
        assert result["rpr_vs_or"] == 5.0

    def test_missing_or(self):
        runner = {"ts": 110, "rpr": 105}
        result = _calculate_differentials(runner)
        assert result["ts_vs_or"] is None
        assert result["rpr_vs_or"] is None

    def test_missing_ts(self):
        runner = {"rpr": 105, "or": 100}
        result = _calculate_differentials(runner)
        assert result["ts_vs_or"] is None
        assert result["rpr_vs_or"] == 5.0

    def test_none_values(self):
        runner = {"ts": None, "rpr": None, "or": None}
        result = _calculate_differentials(runner)
        assert result["ts_vs_or"] is None
        assert result["rpr_vs_or"] is None

    def test_string_numbers(self):
        runner = {"ts": "112", "rpr": "108", "or": "100"}
        result = _calculate_differentials(runner)
        assert result["ts_vs_or"] == 12.0
        assert result["rpr_vs_or"] == 8.0

    def test_alternative_field_names(self):
        runner = {"topspeed": 115, "rpr": 110, "official_rating": 105}
        result = _calculate_differentials(runner)
        assert result["ts_vs_or"] == 10.0
        assert result["rpr_vs_or"] == 5.0


# ─────────────────────────────────────────────
# Enrich runners
# ─────────────────────────────────────────────
class TestEnrichRunners:
    def test_enriches_all_runners(self):
        runners = [
            {"name": "Horse A", "ts": 110, "rpr": 105, "or": 100},
            {"name": "Horse B", "ts": 95, "rpr": 90, "or": 98},
        ]
        enriched = _enrich_runners(runners)
        assert len(enriched) == 2
        assert enriched[0]["ts_vs_or"] == 10.0
        assert enriched[1]["ts_vs_or"] == -3.0

    def test_empty_list(self):
        assert _enrich_runners([]) == []

    def test_preserves_original_fields(self):
        runners = [{"name": "Horse A", "ts": 110, "or": 100, "extra": "data"}]
        enriched = _enrich_runners(runners)
        assert enriched[0]["name"] == "Horse A"
        assert enriched[0]["extra"] == "data"
