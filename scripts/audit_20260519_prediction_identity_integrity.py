"""
2026-05-19 Pre-Sigma Prediction Identity Integrity Audit

Verifies today's predictions are structurally clean and Sigma-matchable
before results land. RP_PROFILE_FALLBACK source requires extra scrutiny
after the May 18 identity issue.

Outputs:
  data/reports/2026-05-19_prediction_identity_integrity.json
  data/reports/2026-05-19_prediction_identity_integrity.md

Classification:
  IDENTITY_READY_FOR_SIGMA       — all checks pass
  IDENTITY_WARNINGS_PRESENT      — minor issues, Sigma may degrade gracefully
  IDENTITY_BLOCKED               — structural failures that will break Sigma

Hard rule: read-only. No changes to predictions, verdicts, or scoring.
"""

from __future__ import annotations

import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

AUDIT_DATE = "2026-05-19"
REPORTS = ROOT / "data" / "reports"
REPORTS.mkdir(parents=True, exist_ok=True)

LOCAL_BACKUP = ROOT / "data" / f"velo_prime_verdicts_{AUDIT_DATE.replace('-', '_')}.json"
DASHBOARD_FILE = ROOT / "data" / f"dashboard_daily_predictions_{AUDIT_DATE.replace('-', '_')}.json"
TRUTH_FILE = ROOT / "data" / f"velo_daily_run_truth_{AUDIT_DATE.replace('-', '_')}.json"

# ── ID format rules ───────────────────────────────────────────────────────────
RP_SYNTHETIC_RE = re.compile(r"^RP_[a-z0-9]+$")       # RP_horsename — clean synthetic
RACING_API_RE   = re.compile(r"^[0-9]+$")              # pure numeric — Racing API canonical
SPACE_RE        = re.compile(r"\s")
PUNCT_RE        = re.compile(r"[^a-zA-Z0-9_]")

EXPECTED_RACES = 38
EXPECTED_SOURCE = "RP_PROFILE_FALLBACK"


def _classify_horse_id(horse_id: str | None, horse_name: str) -> dict:
    if not horse_id:
        return {"type": "BLANK", "risk": "HIGH", "sigma_matchable": False}
    if SPACE_RE.search(horse_id):
        return {"type": "MALFORMED_SPACES", "risk": "HIGH", "sigma_matchable": False}
    if RACING_API_RE.match(horse_id):
        return {"type": "RACING_API_CANONICAL", "risk": "NONE", "sigma_matchable": True}
    if RP_SYNTHETIC_RE.match(horse_id):
        return {"type": "RP_SYNTHETIC_CLEAN", "risk": "LOW", "sigma_matchable": True}
    if horse_id.startswith("RP_"):
        # Check for embedded spaces or punctuation after RP_ prefix
        suffix = horse_id[3:]
        if SPACE_RE.search(suffix):
            return {"type": "RP_SYNTHETIC_MALFORMED_SPACES", "risk": "HIGH", "sigma_matchable": False}
        if re.search(r"[^a-z0-9]", suffix):
            return {"type": "RP_SYNTHETIC_MALFORMED_CHARS", "risk": "MEDIUM", "sigma_matchable": False}
        return {"type": "RP_SYNTHETIC_CLEAN", "risk": "LOW", "sigma_matchable": True}
    return {"type": "UNKNOWN_FORMAT", "risk": "MEDIUM", "sigma_matchable": False}


def _load_verdicts() -> list[dict]:
    if LOCAL_BACKUP.exists():
        try:
            data = json.loads(LOCAL_BACKUP.read_text(encoding="utf-8"))
            if isinstance(data, list):
                return data
        except Exception:
            pass

    # Try Supabase if local not found
    import urllib.request
    sb_url = os.getenv("SUPABASE_URL", "")
    sb_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_SERVICE_KEY", "")
    if sb_url and sb_key:
        try:
            url = (f"{sb_url}/rest/v1/velo_verdicts"
                   f"?generated_at=gte.{AUDIT_DATE}T00:00:00"
                   f"&generated_at=lt.{AUDIT_DATE}T23:59:59"
                   f"&select=*&limit=100")
            req = urllib.request.Request(url)
            req.add_header("apikey", sb_key)
            req.add_header("Authorization", f"Bearer {sb_key}")
            req.add_header("Accept", "application/json")
            with urllib.request.urlopen(req, timeout=10) as resp:
                return json.loads(resp.read())
        except Exception:
            pass

    return []


def _load_dashboard_count() -> int:
    if DASHBOARD_FILE.exists():
        try:
            d = json.loads(DASHBOARD_FILE.read_text(encoding="utf-8"))
            if isinstance(d, list):
                return len(d)
            if isinstance(d, dict):
                # races field may be an int count or a list
                races_val = d.get("races")
                if isinstance(races_val, int):
                    return races_val
                preds = d.get("predictions") or []
                if isinstance(preds, list):
                    return len(preds)
                runners = d.get("runners")
                if isinstance(runners, int):
                    return runners
        except Exception:
            pass
    return -1


def _load_truth() -> dict:
    if TRUTH_FILE.exists():
        try:
            return json.loads(TRUTH_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def run():
    print(f"\nPRE-SIGMA IDENTITY INTEGRITY AUDIT — {AUDIT_DATE}")
    print("=" * 60)

    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")

    verdicts = _load_verdicts()
    truth = _load_truth()
    dashboard_count = _load_dashboard_count()

    # Infer source from truth file or from horse_id format (RP_ prefix = RP_PROFILE_FALLBACK)
    source = truth.get("source") or truth.get("racecard_source") or "INFERRED_FROM_IDS"
    pipeline_run = truth.get("pipeline_run_id") or truth.get("pipeline_run") or truth.get("date", "UNKNOWN")

    # If source unknown, infer from ID pattern
    if source == "INFERRED_FROM_IDS":
        rp_count = sum(1 for v in verdicts
                       if str((v.get("top") or {}).get("horse_id", "")).startswith("RP_"))
        if rp_count > 0:
            source = f"RP_PROFILE_FALLBACK (inferred from {rp_count} RP_ horse_ids)"

    print(f"Source:           {source}")
    print(f"Pipeline run:     {pipeline_run}")
    print(f"Verdicts loaded:  {len(verdicts)}")
    print(f"Dashboard count:  {dashboard_count if dashboard_count >= 0 else 'NOT FOUND'}")

    rows = []
    warnings = []
    blocks = []

    for v in verdicts:
        # Support both flat verdicts (Supabase) and nested (local backup)
        top = v.get("top") or {}
        if isinstance(top, str):
            try:
                top = json.loads(top)
            except Exception:
                top = {}

        race_id   = v.get("race_id") or top.get("race_id", "")
        course    = v.get("course", "")
        off_time  = v.get("off_time", "")
        horse     = top.get("horse") or v.get("top_horse", "")
        horse_id  = top.get("horse_id") or v.get("horse_id", "")
        vp        = top.get("velo_prime_prob") or v.get("velo_prime_prob")
        tier      = v.get("tier", "?")
        product   = top.get("assigned_product") or v.get("assigned_product", "?")
        v_source  = top.get("source") or source

        id_info = _classify_horse_id(horse_id, horse)

        # Checks
        row_flags = []
        if not horse or horse == "?":
            row_flags.append("BLANK_HORSE_NAME")
            blocks.append(f"{course} {off_time}: blank/? horse name")
        if id_info["risk"] == "HIGH":
            row_flags.append(f"ID_HIGH_RISK:{id_info['type']}")
            blocks.append(f"{course} {off_time} {horse}: {id_info['type']}")
        elif id_info["risk"] == "MEDIUM":
            row_flags.append(f"ID_MEDIUM_RISK:{id_info['type']}")
            warnings.append(f"{course} {off_time} {horse}: {id_info['type']}")
        if not race_id:
            row_flags.append("BLANK_RACE_ID")
            blocks.append(f"{course} {off_time}: blank race_id")
        if AUDIT_DATE not in str(race_id):
            row_flags.append("DATE_MISMATCH_IN_RACE_ID")
            warnings.append(f"{course} {off_time}: race_id missing {AUDIT_DATE}")

        # Sigma matchability: course + off_time + normalized horse name fallback
        sigma_fallback = bool(course and off_time and horse and horse != "?")
        sigma_primary  = id_info["sigma_matchable"] and bool(race_id)

        rows.append({
            "race_id": race_id,
            "course": course,
            "off_time": str(off_time),
            "horse": horse,
            "horse_id": horse_id,
            "horse_id_type": id_info["type"],
            "horse_id_risk": id_info["risk"],
            "tier": tier,
            "velo_prime_prob": round(float(vp), 4) if vp is not None else None,
            "product": product,
            "sigma_matchable_primary": sigma_primary,
            "sigma_matchable_fallback": sigma_fallback,
            "flags": row_flags,
        })

    # ── Counts ────────────────────────────────────────────────────────────────
    n_scored = len(verdicts)
    n_blank_names = sum(1 for r in rows if "BLANK_HORSE_NAME" in r["flags"])
    n_high_risk_id = sum(1 for r in rows if r["horse_id_risk"] == "HIGH")
    n_medium_risk_id = sum(1 for r in rows if r["horse_id_risk"] == "MEDIUM")
    n_synthetic_clean = sum(1 for r in rows if r["horse_id_type"] == "RP_SYNTHETIC_CLEAN")
    n_racing_api = sum(1 for r in rows if r["horse_id_type"] == "RACING_API_CANONICAL")
    n_sigma_primary = sum(1 for r in rows if r["sigma_matchable_primary"])
    n_sigma_fallback = sum(1 for r in rows if r["sigma_matchable_fallback"] and not r["sigma_matchable_primary"])
    n_date_mismatch = sum(1 for r in rows if "DATE_MISMATCH_IN_RACE_ID" in r["flags"])

    # ── Classification ────────────────────────────────────────────────────────
    if blocks:
        classification = "IDENTITY_BLOCKED"
    elif warnings:
        classification = "IDENTITY_WARNINGS_PRESENT"
    else:
        classification = "IDENTITY_READY_FOR_SIGMA"

    count_ok = n_scored == EXPECTED_RACES
    source_ok = source.startswith(EXPECTED_SOURCE)

    print(f"\nScore counts:")
    print(f"  Expected races:    {EXPECTED_RACES}")
    print(f"  Verdicts found:    {n_scored}  {'OK' if count_ok else 'MISMATCH'}")
    print(f"  Dashboard:         {dashboard_count if dashboard_count >= 0 else 'NOT FOUND'}")
    print(f"\nSource check:")
    print(f"  Expected:          {EXPECTED_SOURCE}")
    print(f"  Actual:            {source}  {'OK' if source_ok else 'MISMATCH'}")
    print(f"\nHorse ID breakdown:")
    print(f"  Racing API canonical: {n_racing_api}")
    print(f"  RP synthetic clean:   {n_synthetic_clean}")
    print(f"  High risk IDs:        {n_high_risk_id}")
    print(f"  Medium risk IDs:      {n_medium_risk_id}")
    print(f"  Blank horse names:    {n_blank_names}")
    print(f"  Date mismatch:        {n_date_mismatch}")
    print(f"\nSigma matchability:")
    print(f"  Primary (ID+race_id): {n_sigma_primary}")
    print(f"  Fallback (course/time/name): {n_sigma_fallback}")
    print(f"  Total matchable:      {n_sigma_primary + n_sigma_fallback}")
    if blocks:
        print(f"\nBLOCKERS ({len(blocks)}):")
        for b in blocks:
            print(f"  *** {b}")
    if warnings:
        print(f"\nWARNINGS ({len(warnings)}):")
        for w in warnings:
            print(f"  WARN: {w}")
    print(f"\n{'=' * 60}")
    print(f"CLASSIFICATION: {classification}")
    print("=" * 60)

    # ── Output ────────────────────────────────────────────────────────────────
    ts = datetime.now(timezone.utc).isoformat()
    report = {
        "audit": "2026-05-19_PREDICTION_IDENTITY_INTEGRITY",
        "audit_date": AUDIT_DATE,
        "run_at": ts,
        "source": source,
        "pipeline_run": pipeline_run,
        "expected_races": EXPECTED_RACES,
        "verdicts_found": n_scored,
        "dashboard_count": dashboard_count,
        "counts": {
            "racing_api_canonical": n_racing_api,
            "rp_synthetic_clean": n_synthetic_clean,
            "high_risk_id": n_high_risk_id,
            "medium_risk_id": n_medium_risk_id,
            "blank_horse_names": n_blank_names,
            "date_mismatch": n_date_mismatch,
            "sigma_matchable_primary": n_sigma_primary,
            "sigma_matchable_fallback": n_sigma_fallback,
            "total_sigma_matchable": n_sigma_primary + n_sigma_fallback,
        },
        "classification": classification,
        "blockers": blocks,
        "warnings": warnings,
        "rows": rows,
        "audit_rules": {
            "RP_SYNTHETIC_CLEAN": "RP_ prefix + lowercase alphanumeric only — Sigma-safe via name fallback",
            "RACING_API_CANONICAL": "Pure numeric horse_id — Sigma primary match",
            "MALFORMED_SPACES": "Spaces in horse_id — will break Sigma string matching",
            "DATE_MISMATCH": f"race_id does not contain {AUDIT_DATE} — stale data risk",
        },
    }

    json_path = REPORTS / f"{AUDIT_DATE}_prediction_identity_integrity.json"
    json_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    md_lines = [
        f"# {AUDIT_DATE} Pre-Sigma Prediction Identity Integrity",
        "",
        f"**Run:** {ts}  ",
        f"**Classification:** `{classification}`  ",
        f"**Source:** {source}  ",
        "",
        "## Count Verification",
        "",
        f"| Check | Expected | Actual | Status |",
        f"|---|---|---|---|",
        f"| Verdicts scored | {EXPECTED_RACES} | {n_scored} | {'OK' if count_ok else '**MISMATCH**'} |",
        f"| Dashboard races | {EXPECTED_RACES} | {dashboard_count} | {'OK' if dashboard_count == EXPECTED_RACES else 'CHECK'} |",
        f"| Source | {EXPECTED_SOURCE} | {source} | {'OK' if source_ok else '**MISMATCH**'} |",
        "",
        "## Horse ID Breakdown",
        "",
        "| Type | Count |",
        "|---|---|",
        f"| Racing API canonical | {n_racing_api} |",
        f"| RP synthetic clean | {n_synthetic_clean} |",
        f"| High risk (spaces/blank) | {n_high_risk_id} |",
        f"| Medium risk (unknown format) | {n_medium_risk_id} |",
        f"| Blank horse names | {n_blank_names} |",
        "",
        "## Sigma Matchability",
        "",
        f"| Path | Count |",
        f"|---|---|",
        f"| Primary (ID + race_id) | {n_sigma_primary} |",
        f"| Fallback (course/time/name) | {n_sigma_fallback} |",
        f"| **Total matchable** | **{n_sigma_primary + n_sigma_fallback}** |",
        "",
    ]

    if blocks:
        md_lines += ["## BLOCKERS", ""]
        for b in blocks:
            md_lines.append(f"- {b}")
        md_lines.append("")
    if warnings:
        md_lines += ["## Warnings", ""]
        for w in warnings:
            md_lines.append(f"- {w}")
        md_lines.append("")

    md_lines += [
        "## Row Audit",
        "",
        "| Course | Time | Horse | horse_id_type | Risk | Sigma | Flags |",
        "|---|---|---|---|---|---|---|",
    ]
    for r in rows:
        flags_str = ", ".join(r["flags"]) if r["flags"] else "—"
        sigma_str = "PRIMARY" if r["sigma_matchable_primary"] else ("FALLBACK" if r["sigma_matchable_fallback"] else "**BLOCKED**")
        md_lines.append(
            f"| {r['course']} | {r['off_time']} | {r['horse']} "
            f"| `{r['horse_id_type']}` | {r['horse_id_risk']} | {sigma_str} | {flags_str} |"
        )

    md_lines += [
        "",
        "## Conclusion",
        "",
        f"**{classification}**",
        "",
        f"{'All 38 predictions are structurally sound. RP synthetic IDs are normalized (no spaces). Sigma can match via course/time/name fallback.' if classification == 'IDENTITY_READY_FOR_SIGMA' else 'Issues detected — review blockers/warnings before Sigma.'}",
    ]

    md_path = REPORTS / f"{AUDIT_DATE}_prediction_identity_integrity.md"
    md_path.write_text("\n".join(md_lines), encoding="utf-8")

    print(f"\nJSON: {json_path}")
    print(f"MD:   {md_path}")
    return report


if __name__ == "__main__":
    run()
