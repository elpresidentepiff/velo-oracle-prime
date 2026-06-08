import sys
import unittest
import json
import pandas as pd
from pathlib import Path

# Add src to path
sys.path.append(str(Path(__file__).resolve().parents[1] / "src"))

from feature_health_detector import check_quality_failures

class TestHarnessGuard(unittest.TestCase):
    def test_null_detector(self):
        ref = pd.DataFrame({"col1": [1, 2, 3]})
        cur = pd.DataFrame({"col1": [None, None, None]})
        failures = check_quality_failures(ref, cur)
        self.assertTrue(any(f['issue'] == "TOTAL_NULL_COLUMN" for f in failures))

    def test_flatline_detector(self):
        ref = pd.DataFrame({"col1": [1, 2, 3]})
        cur = pd.DataFrame({"col1": [0.5, 0.5, 0.5]})
        failures = check_quality_failures(ref, cur)
        self.assertTrue(any(f['issue'] == "CONSTANT_VALUE_FLATLINE" for f in failures))

    def test_leakage_detector(self):
        ref = pd.DataFrame({"horse": ["A", "B"]})
        cur = pd.DataFrame({
            "horse": ["A", "B"], 
            "leakage_status": ["RETROSPECTIVE_SIGNAL_TEST_WITH_LEAKAGE_RISK", "SAFE"]
        })
        failures = check_quality_failures(ref, cur)
        self.assertTrue(any(f['issue'] == "TEMPORAL_LEAKAGE" for f in failures))

    def test_no_live_imports(self):
        # Scan src files for 'src.velo' or 'app.'
        src_dir = Path(__file__).resolve().parents[1] / "src"
        for py_file in src_dir.glob("*.py"):
            with open(py_file, "r") as f:
                content = f.read()
                self.assertNotIn("import src.velo", content)
                self.assertNotIn("from src.velo", content)
                self.assertNotIn("import app.", content)

if __name__ == "__main__":
    unittest.main()
