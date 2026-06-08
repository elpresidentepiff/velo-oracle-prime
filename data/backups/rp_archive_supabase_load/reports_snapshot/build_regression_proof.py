import re, json
from pathlib import Path

def old_norm(horse_norm_col):
    return str(horse_norm_col or "").lower()

def new_norm(name):
    return re.sub(r"[^a-z0-9]+", "", str(name or "").lower())

test_cases = [
    ("Imperial Guard",     "IMPERIAL GUARD"),
    ("Ride The Thunder",   "RIDE THE THUNDER"),
    ("Trojan Soldier",     "TROJAN SOLDIER"),
    ("Cooley's Mist",      "COOLEY'S MIST"),
    ("Billy No Mates",     "BILLY NO MATES"),
    ("Dontwaste A Moment", "DONTWASTE A MOMENT"),
    ("Plaid",              "PLAID"),
    ("Adalida",            "ADALIDA"),
    ("Letmeseethecolts",   "LETMESEETHECOLTS"),
]

print(f"{'horse_name':25} | {'prediction_id (BAD)':32} | {'result_id (CORRECT)':25} | match")
print("-" * 100)
results = []
for horse_name, horse_norm_col in test_cases:
    pred_id   = f"RP_{old_norm(horse_norm_col)}"
    result_id = f"RP_{new_norm(horse_name)}"
    match = pred_id == result_id
    status = "PASS" if match else "FAIL"
    print(f"{horse_name:25} | {pred_id:32} | {result_id:25} | {status}")
    results.append({
        "horse_name": horse_name,
        "horse_norm_column_value": horse_norm_col,
        "prediction_side_id": pred_id,
        "result_side_id": result_id,
        "match": match,
        "status": status,
        "multi_word": " " in horse_name,
    })

Path("data/reports").mkdir(parents=True, exist_ok=True)
Path("data/reports/may18_synthetic_id_regression_proof.json").write_text(
    json.dumps({
        "root_cause_commit": "1dc8d5b",
        "bad_line": 'horse_norm_val = str(row.get("horse_norm") or row.get("horse") or "").lower()',
        "fixed_line": 'horse_norm_val = _norm_horse_name(row.get("horse_norm") or row.get("horse") or "")',
        "test_cases": results,
    }, indent=2)
)

fails = sum(1 for r in results if not r["match"])
passes = sum(1 for r in results if r["match"])
print(f"\nPASS: {passes}  FAIL: {fails}")
print("Written: data/reports/may18_synthetic_id_regression_proof.json")
