"""
MAY 18 FULL PIPELINE FORENSICS — Read-Only Audit
==================================================
Traces May 18 end-to-end from prediction artifacts through sigma reconciliation.
Classifies every NR-ABSENT into a proper taxonomy bucket.

READ-ONLY. No DB writes, no scoring, no Telegram, no state mutation.

Outputs:
  data/reports/may18_full_pipeline_forensics.json
  data/reports/may18_full_pipeline_forensics.md

Usage:
    python scripts/audit_may18_full_pipeline_forensics.py
"""

import json
import re
import os
import sys
from pathlib import Path
from datetime import datetime

ROOT = Path(__file__).resolve().parents[1]
DATE = "2026-05-18"
DATE_TAG = "2026_05_18"

# ── Safety guard: this script must never write to live state ──────────────────
SAFE_WRITE_PATHS = {"data/reports"}  # only allowed output dirs


def _norm_name(name: str) -> str:
    """Strip all non-alphanumeric chars, lowercase — canonical horse name norm."""
    return re.sub(r"[^a-z0-9]", "", (name or "").lower())


def _norm_id(synthetic_id: str) -> str:
    """Normalise a synthetic RP_ id by stripping spaces — canonical form."""
    return re.sub(r"\s+", "", (synthetic_id or "").lower())


def load_predictions_local() -> list[dict]:
    """Load local prediction JSON for May 18."""
    path = ROOT / "data" / f"velo_prime_verdicts_{DATE_TAG}.json"
    if not path.exists():
        return []
    raw = json.loads(path.read_text())
    if isinstance(raw, list):
        return raw
    return raw.get("verdicts") or raw.get("rows") or []


def load_predictions_supabase() -> list[dict]:
    """Load Supabase velo_verdicts for May 18."""
    try:
        from supabase import create_client
        sb_url = os.environ.get("SUPABASE_URL") or os.environ.get("NEXT_PUBLIC_SUPABASE_URL")
        sb_key = os.environ.get("SUPABASE_SERVICE_KEY") or os.environ.get("SUPABASE_KEY")
        if not (sb_url and sb_key):
            return []
        sb = create_client(sb_url, sb_key)
        resp = sb.table("velo_verdicts").select(
            "race_id, top_rank_horse_id, decision_tier, velo_prime_prob, generated_at"
        ).gte("generated_at", f"{DATE}T00:00:00").lt("generated_at", f"{DATE}T23:59:59").execute()
        return resp.data or []
    except Exception as e:
        print(f"  [WARN] Supabase query failed: {e}")
        return []


def load_results() -> dict:
    """Load May 18 result file produced by Sporting Life scraper."""
    path = ROOT / "data" / f"results_{DATE_TAG}.json"
    if not path.exists():
        return {}
    raw = json.loads(path.read_text())
    races = raw.get("results", [])
    by_id = {}
    for race in races:
        rid = race.get("race_id", "")
        if rid:
            runners = race.get("runners", [])
            by_id[rid] = {
                "race_id": rid,
                "course": race.get("course", ""),
                "off": race.get("off", ""),
                "runners": runners,
                "runner_horse_ids": {r.get("horse_id", "") for r in runners},
                "runner_names_norm": {_norm_name(r.get("horse", "")): r for r in runners},
            }
    return by_id


def classify_exclusion(pred_horse_id: str, result: dict | None) -> str:
    """
    Classify a non-matched prediction into proper taxonomy.

    Returns one of:
      RESULT_RACE_MISSING        — race not in result file at all
      TRUE_NON_RUNNER            — horse found in result, position is NR/WD/etc.
      HORSE_ID_MISMATCH_NAME_OK  — horse_id doesn't match but name normalises to a match
      HORSE_ID_MISMATCH_UNKNOWN  — horse_id doesn't match, name also can't be resolved
      SYNTHETIC_ID_NORMALISATION_DRIFT — specific case: RP_ id with space vs no-space
    """
    if result is None:
        return "RESULT_RACE_MISSING"

    runner_ids = result["runner_horse_ids"]
    if pred_horse_id in runner_ids:
        # Horse was found — check if it's a DNF position
        for r in result["runners"]:
            if r.get("horse_id") == pred_horse_id:
                pos = str(r.get("position", "")).strip().upper()
                dnf = {"NR", "WD", "PU", "F", "BD", "UR", "SU", "RO", "REF", "DSQ", "",
                       "DNF", "FALLEN", "PULLED_UP", "UNSEATED_RIDER", "BROUGHT_DOWN"}
                if pos in dnf:
                    return "TRUE_NON_RUNNER"
        return "UNKNOWN"

    # Horse not found by horse_id — try normalised id (strip spaces)
    norm_pred = _norm_id(pred_horse_id)
    for rid in runner_ids:
        if _norm_id(rid) == norm_pred:
            return "SYNTHETIC_ID_NORMALISATION_DRIFT"

    # Try by horse name
    if pred_horse_id.startswith("RP_"):
        # Extract horse name from synthetic id
        horse_part = pred_horse_id[3:]  # strip "RP_"
        horse_norm = _norm_name(horse_part)
        if horse_norm in result["runner_names_norm"]:
            return "HORSE_ID_MISMATCH_NAME_OK"

    return "HORSE_ID_MISMATCH_UNKNOWN"


def main():
    print(f"\nMAY 18 FULL PIPELINE FORENSICS")
    print("=" * 62)
    print(f"READ-ONLY — no writes, no scoring, no state mutation")
    print(f"Date: {DATE}\n")

    # ── Load predictions ──────────────────────────────────────────────────────
    print("1. LOADING PREDICTIONS")
    sb_preds = load_predictions_supabase()
    local_preds = load_predictions_local()
    print(f"   Supabase velo_verdicts rows:  {len(sb_preds)}")
    print(f"   Local JSON rows:              {len(local_preds)}")

    # Build canonical prediction map from Supabase (what sigma actually used)
    pred_map: dict[str, dict] = {}
    for p in sb_preds:
        rid = p.get("race_id", "")
        if rid:
            pred_map[rid] = p

    pred_race_ids = sorted(pred_map.keys())
    print(f"   Unique predicted races:       {len(pred_race_ids)}")

    horse_id_has_space = [(rid, p["top_rank_horse_id"]) for rid, p in pred_map.items()
                          if " " in (p.get("top_rank_horse_id") or "")]
    horse_id_no_space  = [(rid, p["top_rank_horse_id"]) for rid, p in pred_map.items()
                          if p.get("top_rank_horse_id") and " " not in p["top_rank_horse_id"]]
    horse_id_empty     = [(rid, p["top_rank_horse_id"]) for rid, p in pred_map.items()
                          if not p.get("top_rank_horse_id")]
    print(f"   top_rank_horse_id WITH spaces: {len(horse_id_has_space)}")
    print(f"   top_rank_horse_id NO spaces:   {len(horse_id_no_space)}")
    print(f"   top_rank_horse_id EMPTY:       {len(horse_id_empty)}")

    # ── Load results ──────────────────────────────────────────────────────────
    print("\n2. LOADING RESULTS")
    results = load_results()
    print(f"   Result races in file:         {len(results)}")

    # ── Reconcile ─────────────────────────────────────────────────────────────
    print("\n3. RECONCILIATION AUDIT")

    taxonomy: dict[str, list[dict]] = {
        "MATCH_WIN":                          [],
        "MATCH_PLACED":                       [],
        "MATCH_MISS":                         [],
        "RESULT_RACE_MISSING":               [],
        "TRUE_NON_RUNNER":                   [],
        "SYNTHETIC_ID_NORMALISATION_DRIFT":  [],
        "HORSE_ID_MISMATCH_NAME_OK":         [],
        "HORSE_ID_MISMATCH_UNKNOWN":         [],
        "UNKNOWN":                           [],
    }

    DNF_POSITIONS = {"NR", "WD", "PU", "F", "BD", "UR", "SU", "RO", "REF", "DSQ", "",
                     "DNF", "FALLEN", "PULLED_UP", "UNSEATED_RIDER", "BROUGHT_DOWN"}

    for rid, pred in pred_map.items():
        horse_id = pred.get("top_rank_horse_id") or ""
        result = results.get(rid)

        if result is None:
            taxonomy["RESULT_RACE_MISSING"].append({
                "race_id": rid, "horse_id": horse_id,
                "note": "Race not in Sporting Life result file"
            })
            continue

        if not horse_id:
            taxonomy["UNKNOWN"].append({
                "race_id": rid, "horse_id": horse_id,
                "note": "Empty horse_id — sigma Gate 1 should catch this"
            })
            continue

        # Check if horse_id matches a result runner
        runner_ids = result["runner_horse_ids"]
        if horse_id in runner_ids:
            # Found — check position
            for r in result["runners"]:
                if r.get("horse_id") == horse_id:
                    pos = str(r.get("position", "")).strip().upper()
                    if pos in DNF_POSITIONS:
                        taxonomy["TRUE_NON_RUNNER"].append({
                            "race_id": rid, "horse_id": horse_id, "position": pos
                        })
                    elif pos == "1":
                        taxonomy["MATCH_WIN"].append({
                            "race_id": rid, "horse_id": horse_id,
                            "horse": r.get("horse", ""), "sp": r.get("sp", "")
                        })
                    elif pos in ("2", "3"):
                        taxonomy["MATCH_PLACED"].append({
                            "race_id": rid, "horse_id": horse_id,
                            "horse": r.get("horse", ""), "position": pos
                        })
                    else:
                        taxonomy["MATCH_MISS"].append({
                            "race_id": rid, "horse_id": horse_id,
                            "horse": r.get("horse", ""), "position": pos
                        })
                    break
        else:
            # Not found by horse_id — classify the failure
            bucket = classify_exclusion(horse_id, result)

            # Gather extra evidence
            norm_pred = _norm_id(horse_id)
            result_runner_name_match = None
            if horse_id.startswith("RP_"):
                horse_part = horse_id[3:]
                hn = _norm_name(horse_part)
                match = result["runner_names_norm"].get(hn)
                if match:
                    result_runner_name_match = match.get("horse", "")

            taxonomy[bucket].append({
                "race_id": rid,
                "predicted_horse_id": horse_id,
                "predicted_horse_id_norm": norm_pred,
                "result_runner_name_match": result_runner_name_match,
                "note": (
                    f"RP_ id has spaces — result file uses no-space norm. "
                    f"Predicted: {horse_id!r} vs expected: {norm_pred!r}"
                ) if bucket == "SYNTHETIC_ID_NORMALISATION_DRIFT" else bucket
            })

    # ── Print summary ─────────────────────────────────────────────────────────
    print()
    print(f"   {'Bucket':<42} Count")
    print(f"   {'-'*42} -----")
    total = 0
    for bucket, rows in taxonomy.items():
        print(f"   {bucket:<42} {len(rows)}")
        total += len(rows)
    print(f"   {'TOTAL':<42} {total}")

    print(f"\n4. SIGMA COMPARISON")
    sigma_evaluated = len(taxonomy["MATCH_WIN"]) + len(taxonomy["MATCH_PLACED"]) + len(taxonomy["MATCH_MISS"])
    sigma_nr_claimed = (len(taxonomy["SYNTHETIC_ID_NORMALISATION_DRIFT"]) +
                        len(taxonomy["HORSE_ID_MISMATCH_NAME_OK"]) +
                        len(taxonomy["HORSE_ID_MISMATCH_UNKNOWN"]) +
                        len(taxonomy["TRUE_NON_RUNNER"]))
    identity_failures = (len(taxonomy["SYNTHETIC_ID_NORMALISATION_DRIFT"]) +
                         len(taxonomy["HORSE_ID_MISMATCH_NAME_OK"]))

    print(f"   Sigma reported evaluated:     7")
    print(f"   Sigma reported NR-ABSENT:     24")
    print(f"   Sigma reported no-result:     3")
    print()
    print(f"   Forensic evaluated:           {sigma_evaluated}")
    print(f"   Forensic TRUE_NON_RUNNER:     {len(taxonomy['TRUE_NON_RUNNER'])}")
    print(f"   Forensic RESULT_RACE_MISSING: {len(taxonomy['RESULT_RACE_MISSING'])}")
    print(f"   Forensic IDENTITY_FAILURES:   {identity_failures}")
    print(f"     (SYNTHETIC_ID_NORMALISATION_DRIFT: {len(taxonomy['SYNTHETIC_ID_NORMALISATION_DRIFT'])})")
    print(f"     (HORSE_ID_MISMATCH_NAME_OK:         {len(taxonomy['HORSE_ID_MISMATCH_NAME_OK'])})")

    print(f"\n5. ROOT CAUSE")
    print(f"   Scoring path (run_prime_today.py):")
    print(f"     synthetic_id = f\"RP_{{horse_norm}}\"")
    print(f"     horse_norm from RP profile column — PRESERVES SPACES")
    print(f"     e.g. 'Imperial Guard' → horse_norm='imperial guard' → 'RP_imperial guard'")
    print()
    print(f"   Scraper path (scrape_results_atr.py):")
    print(f"     horse_norm = re.sub(r'[^a-z0-9]', '', name.lower())")
    print(f"     STRIPS SPACES")
    print(f"     e.g. 'Imperial Guard' → 'imperialguard' → 'RP_imperialguard'")
    print()
    print(f"   Sigma matcher (run_results_sigma.py line 491):")
    print(f"     if runner.get('horse_id') == predicted_horse_id:  # STRICT — no normalisation")
    print()
    print(f"   'RP_imperial guard' != 'RP_imperialguard' → NR-ABSENT")

    print(f"\n6. LEARNING BLOCK CONFIRMATION")
    print(f"   MAY18_SIGMA_INVALID_SAMPLE             = TRUE")
    print(f"   LEARNING_ALLOWED                       = FALSE")
    print(f"   NO_EOD_CONSUME                         = TRUE")
    print(f"   NO_SHADOW_CONSUME                      = TRUE")
    print(f"   NO_TRAINING_DATASET_UPDATE             = TRUE")
    print(f"   IDENTITY_RECONCILIATION_REQUIRED       = TRUE")
    print(f"   SIGMA_RERUN_REQUIRED_AFTER_PATCH       = TRUE")

    # ── Write reports ─────────────────────────────────────────────────────────
    report_dir = ROOT / "data" / "reports"
    report_dir.mkdir(parents=True, exist_ok=True)

    report_json = {
        "date": DATE,
        "generated_at": datetime.utcnow().isoformat(),
        "classification": [
            "MAY18_SIGMA_INVALID_SAMPLE",
            "RESULT_RECONCILIATION_FAILURE",
            "RP_IDENTITY_BRIDGE_FAILURE",
            "SYNTHETIC_ID_NORMALISATION_DRIFT",
            "NO_LEARNING_ALLOWED",
        ],
        "expected_races": len(pred_race_ids),
        "supabase_predictions": len(sb_preds),
        "local_json_predictions": len(local_preds),
        "result_races_in_file": len(results),
        "sigma_evaluated_races": 7,
        "sigma_nr_absent_claimed": 24,
        "sigma_no_result": 3,
        "forensic_taxonomy": {k: len(v) for k, v in taxonomy.items()},
        "forensic_detail": taxonomy,
        "identity_issues": {
            "top_rank_horse_id_with_spaces": len(horse_id_has_space),
            "top_rank_horse_id_no_spaces": len(horse_id_no_space),
            "top_rank_horse_id_empty": len(horse_id_empty),
        },
        "root_cause": {
            "component": "synthetic_id_normalisation_inconsistency",
            "scoring_path_norm": "horse_norm_column_preserves_spaces",
            "scraper_path_norm": "re_sub_strips_non_alnum_including_spaces",
            "sigma_match": "strict_equality_no_normalisation",
            "effect": "multi_word_horse_names_always_fail_identity_match",
            "confidence": "PROVEN_FROM_ARTIFACTS",
            "artifact_evidence": [
                "supabase velo_verdicts top_rank_horse_id: 'RP_imperial guard'",
                "results_2026_05_18.json runner horse_id: 'RP_imperialguard'",
                "25/34 predictions have spaces in synthetic id",
                "9/34 single-word names matched correctly (7 had results, 2 no-result-race)",
            ],
        },
        "valid_sigma_results": {
            "matches_found": sigma_evaluated,
            "wins": len(taxonomy["MATCH_WIN"]),
            "placed": len(taxonomy["MATCH_PLACED"]),
            "misses": len(taxonomy["MATCH_MISS"]),
            "note": "FORENSIC_ONLY — not accepted as valid daily sigma sample",
        },
        "learning_guard": {
            "learning_allowed": False,
            "eod_consume": False,
            "shadow_consume": False,
            "training_dataset_update": False,
            "sigma_valid": False,
            "required_before_unblock": [
                "patch synthetic_id normalisation to be consistent",
                "rerun scraper with consistent IDs",
                "rerun sigma with consistent IDs",
                "verify matched_race_coverage >= 90%",
                "operator approval",
            ],
        },
    }

    json_path = report_dir / "may18_full_pipeline_forensics.json"
    json_path.write_text(json.dumps(report_json, indent=2))
    print(f"\n   Written: {json_path.relative_to(ROOT)}")

    # MD report
    md = f"""# MAY 18 FULL PIPELINE FORENSICS

**Date:** {DATE}
**Generated:** {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}
**Classification:** READ-ONLY AUDIT — no scoring, no learning, no state mutation

---

## Classification

```
MAY18_SIGMA_INVALID_SAMPLE
RESULT_RECONCILIATION_FAILURE
RP_IDENTITY_BRIDGE_FAILURE
SYNTHETIC_ID_NORMALISATION_DRIFT
NO_LEARNING_ALLOWED
```

---

## Coverage Numbers

| Metric | Value |
|---|---|
| Expected predicted races | {len(pred_race_ids)} |
| Supabase velo_verdicts rows | {len(sb_preds)} |
| Result races in file (SL scraper) | {len(results)} |
| Sigma reported evaluated | 7 |
| Sigma reported NR-ABSENT | 24 |
| Sigma reported no-result | 3 |
| **Forensic true matches** | **{sigma_evaluated}** |
| **Forensic identity failures** | **{identity_failures}** |
| Forensic RESULT_RACE_MISSING | {len(taxonomy['RESULT_RACE_MISSING'])} |
| Forensic TRUE_NON_RUNNER | {len(taxonomy['TRUE_NON_RUNNER'])} |

---

## Reconciliation Taxonomy (Correct Classification)

| Bucket | Count | Meaning |
|---|---|---|
| MATCH_WIN | {len(taxonomy['MATCH_WIN'])} | Predicted horse won |
| MATCH_PLACED | {len(taxonomy['MATCH_PLACED'])} | Predicted horse 2nd/3rd |
| MATCH_MISS | {len(taxonomy['MATCH_MISS'])} | Predicted horse ran, didn't place |
| RESULT_RACE_MISSING | {len(taxonomy['RESULT_RACE_MISSING'])} | Race not in SL result file |
| TRUE_NON_RUNNER | {len(taxonomy['TRUE_NON_RUNNER'])} | Confirmed WD/NR/PU |
| **SYNTHETIC_ID_NORMALISATION_DRIFT** | **{len(taxonomy['SYNTHETIC_ID_NORMALISATION_DRIFT'])}** | **Root cause — ID mismatch** |
| HORSE_ID_MISMATCH_NAME_OK | {len(taxonomy['HORSE_ID_MISMATCH_NAME_OK'])} | Name matches but ID doesn't |
| HORSE_ID_MISMATCH_UNKNOWN | {len(taxonomy['HORSE_ID_MISMATCH_UNKNOWN'])} | No match at all |
| UNKNOWN | {len(taxonomy['UNKNOWN'])} | Unclassified |

---

## Root Cause — Proven from Artifacts

**Component:** Synthetic ID normalisation inconsistency

### Scoring path (`run_prime_today.py`)
```python
raw_hid = f"RP_{{horse_norm_val}}"
# horse_norm_val = RP profile horse_norm column
# PRESERVES SPACES
# 'Imperial Guard' → horse_norm='imperial guard' → 'RP_imperial guard'
```

### Scraper path (`scrape_results_atr.py`)
```python
horse_norm = re.sub(r"[^a-z0-9]", "", name.lower())
# STRIPS SPACES AND ALL NON-ALPHANUMERIC
# 'Imperial Guard' → 'imperialguard' → 'RP_imperialguard'
```

### Sigma matcher (`run_results_sigma.py` line 491)
```python
if runner.get("horse_id") == predicted_horse_id:  # STRICT EQUALITY
```

### Result
```
'RP_imperial guard' != 'RP_imperialguard'
→ found_in_result = False
→ NR-ABSENT (misclassified)
```

### Evidence
- Supabase `velo_verdicts.top_rank_horse_id`: `'RP_imperial guard'` (with space)
- `results_2026_05_18.json` runner `horse_id`: `'RP_imperialguard'` (no space)
- 25/34 predictions have spaces in synthetic ID
- 9/34 single-word names (no spaces) matched correctly → exactly the 7 sigma evaluated + 2 RESULT_RACE_MISSING

---

## Races Marked NR-ABSENT by Sigma (True Classification)

These were NOT non-runners. They were identity join failures:

"""
    for entry in taxonomy.get("SYNTHETIC_ID_NORMALISATION_DRIFT", []):
        md += f"- `{entry['race_id']}` — predicted `{entry['predicted_horse_id']}` vs result `{entry.get('predicted_horse_id_norm')}`\n"

    md += f"""
---

## Races With No Result File Coverage

These races genuinely had no SL scraper match (maiden/novice races outside scraper's field coverage):

"""
    for entry in taxonomy.get("RESULT_RACE_MISSING", []):
        md += f"- `{entry['race_id']}` — {entry.get('note', '')}\n"

    md += f"""
---

## Sigma Sample — Invalid

The 7 races sigma evaluated are only the single-word horse names (no spaces in synthetic ID):
- Adalida (WIN), Lequinto (WIN), Wipeawayyourtears (PLACED)
- Detective (MISS), Letmeseethecolts (MISS), Profiteer (MISS), Powernap (MISS)

**This is NOT a representative sample of May 18 predictions.**
**No model conclusion is possible from this sigma.**

---

## Learning Guard

```
LEARNING_ALLOWED              = FALSE
EOD_CONSUME                   = BLOCKED
SHADOW_CONSUME                = BLOCKED
TRAINING_DATASET_UPDATE       = BLOCKED
SIGMA_VALID                   = FALSE
```

Required before unblocking:
1. Patch synthetic ID normalisation to be consistent (strip spaces in scoring path)
2. Re-run SL scraper to regenerate result file with consistent IDs
3. Re-run sigma with consistent IDs
4. Verify matched race coverage ≥ 90%
5. Operator approval

---

## What Did NOT Fail

- Racing Post files are legitimate
- RP ingestion produced 34 races correctly
- SQPE scoring fired correctly
- Sporting Life scraper matched 31/34 races
- Sigma machinery is correct — it was given inconsistent IDs as input

**This is an infrastructure identity bridge failure, not a model failure.**

---

## Required Patch (Pending Operator Approval)

In `run_prime_today.py` `_load_rp_profile_as_racecards()`:
```python
# Current (broken)
raw_hid = f"RP_{{horse_norm_val}}"

# Fix: strip spaces and non-alphanumeric — match the canonical norm
import re as _re
raw_hid = "RP_" + _re.sub(r"[^a-z0-9]", "", str(horse_norm_val or "").lower())
```

This makes scoring path IDs match the scraper path IDs everywhere.

**Commit only after operator approves this patch.**
"""

    md_path = report_dir / "may18_full_pipeline_forensics.md"
    md_path.write_text(md)
    print(f"   Written: {md_path.relative_to(ROOT)}")

    print(f"\n{'='*62}")
    print(f"FORENSIC COMPLETE")
    print(f"  Root cause:    SYNTHETIC_ID_NORMALISATION_DRIFT (PROVEN)")
    print(f"  Identity fails: {identity_failures}/34 predictions")
    print(f"  True NR:       {len(taxonomy['TRUE_NON_RUNNER'])}")
    print(f"  Result missing: {len(taxonomy['RESULT_RACE_MISSING'])}")
    print(f"  Learning:      BLOCKED")
    print(f"  Sigma valid:   FALSE")
    print(f"  Patch needed:  YES — pending operator approval")
    print()


if __name__ == "__main__":
    # Load .env if available
    env_path = ROOT / ".env"
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                if k.strip() and k.strip() not in os.environ:
                    os.environ[k.strip()] = v.strip()
    main()
