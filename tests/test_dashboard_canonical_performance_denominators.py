from __future__ import annotations

import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INDEX = ROOT / "app" / "static" / "dashboard" / "index.html"


def _summarize(rows: list[dict]) -> dict:
    source = INDEX.read_text(encoding="utf-8")
    start = source.index("function summarizeCanonicalPerformanceRows(rows)")
    end = source.index("\n\n// Canonical model performance", start)
    function_source = source[start:end]
    program = f"{function_source}\nconsole.log(JSON.stringify(summarizeCanonicalPerformanceRows({json.dumps(rows)})));"
    completed = subprocess.run(
        ["node", "-e", program], cwd=ROOT, check=True, capture_output=True, text=True
    )
    return json.loads(completed.stdout)


def test_dashboard_fails_closed_and_keeps_settled_void_denominators_separate():
    rows = [
        {"rank": 1, "model_name": "CAPTAIN", "dashboard_metrics_eligible": True,
         "settlement_status": "SETTLED", "win": True, "frame": True},
        {"rank": 1, "model_name": "CAPTAIN", "dashboard_metrics_eligible": True,
         "settlement_status": "SETTLED", "win": False, "frame": True},
        {"rank": 1, "model_name": "CAPTAIN", "dashboard_metrics_eligible": True,
         "settlement_status": "VOID", "win": None, "frame": None},
        {"rank": 1, "model_name": "CAPTAIN", "dashboard_metrics_eligible": False,
         "settlement_status": "SETTLED", "win": True, "frame": True},
        {"rank": 1, "model_name": "CAPTAIN", "settlement_status": "SETTLED",
         "win": True, "frame": True},
        {"rank": 2, "model_name": "CAPTAIN", "dashboard_metrics_eligible": True,
         "settlement_status": "SETTLED", "win": True, "frame": True},
    ]
    assert _summarize(rows) == {
        "CAPTAIN": {"selections": 3, "settled": 2, "voids": 1, "wins": 1, "frames": 2}
    }
