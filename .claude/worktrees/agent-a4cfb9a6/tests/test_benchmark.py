"""
Unit tests for benchmark module.
"""
import pytest
import json
import os
from pathlib import Path
import tempfile


class TestMetrics:
    """Test benchmark metrics calculation."""
    
    def test_calculate_metrics_basic(self):
        """Test basic metrics calculation."""
        from benchmark.metrics import calculate_metrics
        
        # Create sample run output
        run_data = {
            "run_id": "test_run",
            "races_processed": 2,
            "elapsed_seconds": 10.5,
            "results": [
                {
                    "race_id": "race1",
                    "status": "success",
                    "runners_count": 8,
                    "predictions": {
                        "top_4": [
                            {"position": 1, "runner_id": "r1", "name": "Horse A", "score": 0.85},
                            {"position": 2, "runner_id": "r2", "name": "Horse B", "score": 0.75},
                            {"position": 3, "runner_id": "r3", "name": "Horse C", "score": 0.65},
                            {"position": 4, "runner_id": "r4", "name": "Horse D", "score": 0.55}
                        ]
                    }
                },
                {
                    "race_id": "race2",
                    "status": "success",
                    "runners_count": 6,
                    "predictions": {
                        "top_4": [
                            {"position": 1, "runner_id": "r5", "name": "Horse E", "score": 0.90},
                            {"position": 2, "runner_id": "r6", "name": "Horse F", "score": 0.80},
                            {"position": 3, "runner_id": "r7", "name": "Horse G", "score": 0.70},
                            {"position": 4, "runner_id": "r8", "name": "Horse H", "score": 0.60}
                        ]
                    }
                }
            ]
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(run_data, f)
            temp_path = f.name
        
        try:
            metrics = calculate_metrics(temp_path)
            
            # Verify metrics structure
            assert "coverage_pct" in metrics
            assert "total_runners" in metrics
            assert "scored_runners" in metrics
            assert "runtime" in metrics
            assert "score_distribution" in metrics
            assert "garbage_patterns" in metrics
            
            # Verify values
            assert metrics["total_runners"] == 14  # 8 + 6
            assert metrics["scored_runners"] == 8  # All 8 predictions have scores > 0
            assert metrics["races_processed"] == 2
            assert metrics["runtime"]["total_seconds"] == 10.5
            assert metrics["garbage_patterns"]["all_zero_count"] == 0
            assert metrics["garbage_patterns"]["placeholder_count"] == 0
            
        finally:
            os.unlink(temp_path)
    
    def test_calculate_hash_deterministic(self):
        """Test that hash is deterministic."""
        from benchmark.metrics import calculate_hash
        
        run_data = {
            "run_id": "test_run",
            "timestamp": "2026-01-09T12:00:00",
            "results": [
                {
                    "race_id": "race1",
                    "predictions": {"top_4": [{"score": 0.85}]}
                }
            ]
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(run_data, f)
            temp_path = f.name
        
        try:
            hash1 = calculate_hash(temp_path)
            hash2 = calculate_hash(temp_path)
            
            assert hash1 == hash2
            assert len(hash1) == 64  # SHA256 hex digest
            
        finally:
            os.unlink(temp_path)


class TestTolerances:
    """Test regression tolerance checks."""
    
    def test_check_regression_pass(self):
        """Test passing regression check."""
        from benchmark.tolerances import check_regression
        
        baseline = {
            "coverage_pct": 99.8,
            "garbage_patterns": {"all_zero_count": 0, "placeholder_count": 0},
            "runtime": {"avg_per_race": 0.100}
        }
        
        current = {
            "coverage_pct": 99.9,
            "garbage_patterns": {"all_zero_count": 0, "placeholder_count": 0},
            "runtime": {"avg_per_race": 0.095}
        }
        
        is_passing, violations = check_regression(current, baseline)
        
        assert is_passing is True
        assert len(violations) == 0
    
    def test_check_regression_coverage_fail(self):
        """Test failing coverage regression check."""
        from benchmark.tolerances import check_regression
        
        baseline = {
            "coverage_pct": 99.8,
            "garbage_patterns": {"all_zero_count": 0, "placeholder_count": 0}
        }
        
        current = {
            "coverage_pct": 98.0,  # Too low
            "garbage_patterns": {"all_zero_count": 0, "placeholder_count": 0}
        }
        
        is_passing, violations = check_regression(current, baseline)
        
        assert is_passing is False
        assert len(violations) > 0
        assert "Coverage regression" in violations[0]
    
    def test_check_regression_garbage_fail(self):
        """Test failing garbage pattern check."""
        from benchmark.tolerances import check_regression
        
        baseline = {
            "coverage_pct": 99.8,
            "garbage_patterns": {"all_zero_count": 0, "placeholder_count": 0}
        }
        
        current = {
            "coverage_pct": 99.9,
            "garbage_patterns": {"all_zero_count": 5, "placeholder_count": 2}
        }
        
        is_passing, violations = check_regression(current, baseline)
        
        assert is_passing is False
        assert len(violations) == 2
        assert any("zero" in v.lower() for v in violations)
        assert any("placeholder" in v.lower() for v in violations)
    
    def test_check_hash_match(self):
        """Test hash matching."""
        from benchmark.tolerances import check_hash_match
        
        hash1 = "abc123def456"
        hash2 = "abc123def456"
        hash3 = "xyz789"
        
        is_passing, violation = check_hash_match(hash1, hash2)
        assert is_passing is True
        assert violation is None
        
        is_passing, violation = check_hash_match(hash1, hash3)
        assert is_passing is False
        assert violation is not None
        assert "mismatch" in violation.lower()


class TestMergeShards:
    """Test shard merging."""
    
    def test_merge_shards_basic(self):
        """Test basic shard merging."""
        from benchmark.merge_shards import merge_shards
        
        shard1 = {
            "run_id": "shard_1",
            "manifest": "manifest.json",
            "as_of_date": "2026-01-09",
            "shard": 1,
            "total_shards": 2,
            "races_processed": 2,
            "successes": 2,
            "failures": 0,
            "elapsed_seconds": 5.0,
            "results": [
                {"race_id": "race1", "status": "success"},
                {"race_id": "race2", "status": "success"}
            ]
        }
        
        shard2 = {
            "run_id": "shard_2",
            "manifest": "manifest.json",
            "as_of_date": "2026-01-09",
            "shard": 2,
            "total_shards": 2,
            "races_processed": 1,
            "successes": 1,
            "failures": 0,
            "elapsed_seconds": 3.0,
            "results": [
                {"race_id": "race3", "status": "success"}
            ]
        }
        
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create shard files in subdirectories (mimicking GitHub Actions artifacts)
            shard1_dir = Path(tmpdir) / "benchmark-shard-1"
            shard1_dir.mkdir()
            with open(shard1_dir / "shard_1.json", 'w') as f:
                json.dump(shard1, f)
            
            shard2_dir = Path(tmpdir) / "benchmark-shard-2"
            shard2_dir.mkdir()
            with open(shard2_dir / "shard_2.json", 'w') as f:
                json.dump(shard2, f)
            
            output_path = Path(tmpdir) / "merged.json"
            merge_shards(tmpdir, str(output_path))
            
            # Verify merged output
            with open(output_path) as f:
                merged = json.load(f)
            
            assert merged["shards_merged"] == 2
            assert merged["races_processed"] == 3
            assert merged["successes"] == 3
            assert merged["failures"] == 0
            assert merged["elapsed_seconds"] == 8.0
            assert len(merged["results"]) == 3
            
            # Verify results are sorted by race_id
            race_ids = [r["race_id"] for r in merged["results"]]
            assert race_ids == sorted(race_ids)


class TestReport:
    """Test report generation."""
    
    def test_generate_report_pass(self):
        """Test report generation with passing check."""
        from benchmark.report import generate_report
        
        # Create sample run output with high coverage
        run_data = {
            "results": [
                {
                    "race_id": "race1",
                    "status": "success",
                    "runners_count": 4,  # All 4 runners scored (100% coverage)
                    "predictions": {
                        "top_4": [
                            {"score": 0.9, "name": "Horse A"},
                            {"score": 0.8, "name": "Horse B"},
                            {"score": 0.7, "name": "Horse C"},
                            {"score": 0.6, "name": "Horse D"}
                        ]
                    }
                }
            ],
            "races_processed": 1,
            "elapsed_seconds": 1.0
        }
        
        baseline = {
            "coverage_pct": 100.0,  # 4 out of 4 runners scored
            "garbage_patterns": {"all_zero_count": 0, "placeholder_count": 0}
        }
        
        with tempfile.TemporaryDirectory() as tmpdir:
            run_path = Path(tmpdir) / "run.json"
            baseline_path = Path(tmpdir) / "baseline.json"
            report_path = Path(tmpdir) / "report.json"
            
            with open(run_path, 'w') as f:
                json.dump(run_data, f)
            with open(baseline_path, 'w') as f:
                json.dump(baseline, f)
            
            report = generate_report(str(run_path), str(baseline_path), str(report_path))
            
            assert report["status"] == "PASS"
            assert len(report["violations"]) == 0
            assert "current_metrics" in report
            assert "baseline_metrics" in report
            assert "deltas" in report


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
