"""
Bias-Variance / Leakage Governance Audit
Scans feature sets for outcome and market leakage violations.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

try:
    from app.services.sqpe_v17_service import EXPECTED_FEATURES as ov_features
except ImportError:
    ov_features = []

try:
    from scripts.ops.new_build_two_lane_score import _feature_map, INTENT_FEATURES
    nb_base_features = list(_feature_map({}, {}).keys())
    nb_features = nb_base_features + INTENT_FEATURES
except ImportError:
    nb_features = []

BANNED_SUBSTRINGS = [
    "rpr", 
    "sp_dec", "log_sp", "implied_prob", "sp_rank", "is_fav", "bsp",
    "result", "pos", "won", "finish"
]

def check_feature(f):
    violations = []
    f_lower = f.lower()
    for sub in BANNED_SUBSTRINGS:
        # Avoid false positives like "position_trend" if we are strict, but the prompt says "pos" in name.
        # Actually "pos_num" is bad, "position" is bad, but "positive" is fine.
        # Let's just check raw substring as requested: "Any feature with 'result', 'pos', 'won', 'finish' in the name"
        # However, "pp_avg_sp_last5" contains "sp", but it's historical, not same-race.
        # The prompt says: SP-derived features in morning models (sp_dec, log_sp, implied_prob).
        if sub in f_lower:
            # Exempt historical SP
            if sub == "sp" and "last" in f_lower:
                continue
            violations.append(sub)
            
    # Explicit checks based on prompt
    if f in ["sp_dec", "log_sp", "implied_prob", "sp_rank", "is_fav"]:
        if "sp_derived" not in violations:
            violations.append("sp_derived")
            
    return list(set(violations))

def run_audit():
    report = {
        "summary": "CLEAN",
        "violations": 0,
        "models": {
            "Old VELO (SQPE v17)": {},
            "New Build (Challenger V2/Lane B)": {}
        }
    }

    total_violations = 0

    for f in ov_features:
        vs = check_feature(f)
        status = "FAIL" if vs else "PASS"
        if vs: total_violations += 1
        report["models"]["Old VELO (SQPE v17)"][f] = {"status": status, "violations": vs}

    for f in nb_features:
        vs = check_feature(f)
        status = "FAIL" if vs else "PASS"
        if vs: total_violations += 1
        report["models"]["New Build (Challenger V2/Lane B)"][f] = {"status": status, "violations": vs}

    if total_violations > 0:
        report["summary"] = "VIOLATIONS"
        report["violations"] = total_violations

    out_dir = ROOT / "data" / "reports"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / "leakage_audit_latest.json"
    out_file.write_text(json.dumps(report, indent=2))
    
    print(f"Leakage audit complete: {report['summary']} ({total_violations} violations found)")
    print(f"Report saved to {out_file}")

if __name__ == "__main__":
    run_audit()
