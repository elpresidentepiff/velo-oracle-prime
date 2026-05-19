"""
VÉLØ RP Claim Extractor — Regex Baseline (Phase A)

Extracts structured claims from Racing Post horse comment text.
This is Phase A (rule-based regex). Phase B (DSPy) requires separate approval.

Sources:
  horse_comments Supabase table (comment_raw field)
  data/features/rp_runner_profile_latest.parquet (horse_comment field)

Outputs:
  data/features/rp_claims_regex_latest.json
  data/features/rp_claims_regex_latest.parquet
  data/reports/rp_claims_regex_latest.md

Claim types extracted:
  improvement_claim     — horse expected to improve (ran green, first run, should strip fitter)
  handicap_claim        — handicap assessment or mark comment
  stable_intent_claim   — trainer/connections interest/intent signals
  trip_claim            — trip/distance preference stated
  ground_claim          — going/ground preference stated
  class_claim           — drop/raise in class noted
  fitness_claim         — fitness level signal (well, spot-on, needed run)
  negative_claim        — negative flag (below par, disappointing, pulled up)
  unsupported_hype_claim — vague positive filler with no structural basis

Read-only. Does not modify scoring, routing, or live state.
"""

import json
import os
import re
import warnings
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")

ROOT = Path(__file__).resolve().parents[1]
RP_PROFILE_PATH = ROOT / "data" / "features" / "rp_runner_profile_latest.parquet"
OUT_JSON = ROOT / "data" / "features" / "rp_claims_regex_latest.json"
OUT_PARQUET = ROOT / "data" / "features" / "rp_claims_regex_latest.parquet"
OUT_MD = ROOT / "data" / "reports" / "rp_claims_regex_latest.md"
OUT_MD.parent.mkdir(parents=True, exist_ok=True)


# ── Claim patterns ─────────────────────────────────────────────────────────────

PATTERNS = {
    "improvement_claim": [
        r"\bshould\s+improve\b",
        r"\bcan\s+improve\b",
        r"\bexpect(?:ed)?\s+(?:to\s+)?improve\b",
        r"\bimprovement\s+(?:likely|expected|to\s+come)\b",
        r"\bran\s+green\b",
        r"\bfirst[\s-](?:time|run)\b",
        r"\bstrip(?:ped?)?\s+fitter\b",
        r"\bsecond[\s-](?:time|run)\b",
        r"\bcome\s+on\s+for\b",
        r"\bbetter\s+(?:for\s+)?(?:the\s+)?run\b",
        r"\bneeded\s+(?:the\s+)?run\b(?!.*spot.on)",  # fitness negative → covered there
        r"\bwill\s+(?:be\s+)?(?:surely\s+)?(?:come\s+on|improve)\b",
        r"\bmore\s+to\s+offer\b",
        r"\bwinless\s+but\b.*\bimprove\b",
    ],
    "handicap_claim": [
        r"\bhandicapper\b",
        r"\bofficial\s+rating\b",
        r"\b(?:current|present)\s+(?:mark|rating|OR)\b",
        r"\bwell[- ]handicapped\b",
        r"\bcompetitively\s+(?:rated|weighted|handicapped)\b",
        r"\bon\s+a\s+workable\s+(?:mark|rating)\b",
        r"\bhandicap\s+(?:mark|rating|debut|bow)\b",
        r"\brated\s+\d+\b",
        r"\brating\s+of\s+\d+\b",
        r"\bOR\s+\d+\b",
    ],
    "stable_intent_claim": [
        r"\bconnections\s+(?:are\s+|keen\s+|hopeful\b)",
        r"\btrainer\s+(?:reports|says|believes|hopeful)\b",
        r"\binterest(?:ed)?\s+(?:in|from)\s+connections\b",
        r"\bwell[\s-]supported\b",
        r"\bsent\s+off\b.*\bfavourite\b",
        r"\bbacked\s+(?:into|heavily)\b",
        r"\bsteam(?:ed|ing)?\s+in\b",
        r"\bcourse\s+specialist\b",
        r"\bgood\s+(?:course|track)\s+record\b",
        r"\bfancied\b",
        r"\bstrongly\s+fancied\b",
        r"\bwell[\s-]fancied\b",
    ],
    "trip_claim": [
        r"\b(?:trip|distance|journey)\s+(?:should\s+)?suit\b",
        r"\bshort(?:er)?\s+(?:trip|distance)\b",
        r"\blong(?:er)?\s+(?:trip|distance)\b",
        r"\bstep\s+(?:up|down)\s+in\s+(?:trip|distance)\b",
        r"\bmore\s+(?:of\s+a\s+)?(?:stayer|sprinter)\b",
        r"\bone[\s-]mile(?:r)?\b",
        r"\bover\s+(?:six|7f|eight|a[\s-]mile|ten|twelve)\b",
        r"\b(?:suited|stays)\s+(?:the\s+)?(?:trip|distance|course)\b",
        r"\bprefer(?:s|red)?\s+(?:further|shorter|this\s+trip)\b",
        r"\bhas\s+(?:won|placed)\s+at\s+this\s+trip\b",
    ],
    "ground_claim": [
        r"\b(?:good|soft|heavy|firm|yielding|all-weather|fibresand|tapeta|polytrack)\s+ground\b",
        r"\bground\s+(?:conditions?\s+)?(?:suit|should\s+suit|to\s+suit)\b",
        r"\bprefer(?:s|red)?\s+(?:good|soft|heavy|firm|yielding|faster|slower)\b",
        r"\bgoes\s+well\s+on\b",
        r"\b(?:acts|ran\s+well)\s+on\s+(?:this|any|good|soft)\b",
        r"\bground\s+(?:won't|may\s+not)\s+be\s+ideal\b",
        r"\bdoesn't\s+(?:handle|act\s+on)\b.*\bground\b",
        r"\bneeds?\s+(?:better|faster|slower|softer|firmer)\s+ground\b",
    ],
    "class_claim": [
        r"\bdrop(?:ped|ping)?\s+(?:back\s+)?in\s+class\b",
        r"\bstep(?:ping)?\s+(?:back\s+)?down\s+in\s+class\b",
        r"\brise\s+in\s+class\b",
        r"\bstep(?:ping)?\s+up\s+in\s+class\b",
        r"\bclass\s+(?:drop|raise|edge)\b",
        r"\bbelieved\s+to\s+be\s+better\s+than\b",
        r"\bgrade\s+(?:down|drop|down)\b",
        r"\bfrom\s+(?:group|grade|listed)\b",
        r"\bGroup\s+(?:1|2|3|One|Two|Three)\s+(?:performer|winner)\b",
        r"\bclaiming\s+(?:the\s+)?race\b",
    ],
    "fitness_claim": [
        r"\bspot[-\s]on\b",
        r"\bfully\s+(?:fit|wound\s+up)\b",
        r"\bright[\s-](?:to\s+go|on[\s-]song)\b",
        r"\bin\s+(?:good|great|fine|top)\s+(?:nick|form|condition|shape|order)\b",
        r"\bwell[\s-](?:prepared|tuned|wound)\b",
        r"\bworkout\b.*\bpleased\b",
        r"\bpleased\b.*\bworkout\b",
        r"\bfresh\b(?:.*\brun\b)?",
        r"\bfirst[\s-]run\s+of\s+(?:the\s+)?season\b",
        r"\bseasonal\s+debut\b",
        r"\bshould\s+(?:be\s+)?spot[-\s]on\b",
        r"\bcomes\s+to\s+this\s+(?:fully|in\s+great)\b",
    ],
    "negative_claim": [
        r"\bdisappoint(?:ed|ing)?\b",
        r"\bbelow\s+(?:par|expectations?|form)\b",
        r"\bstruggled?\b",
        r"\bpulled\s+up\b",
        r"\bfell\b",
        r"\bunseated\b",
        r"\bbehind(?:hand)?\b",
        r"\bno[\s-]show\b",
        r"\bflattered\s+(?:to\s+)?deceive\b",
        r"\blimitations?\s+(?:exposed|clear)\b",
        r"\bmay\s+find\s+(?:this|it)\s+(?:too|tough|hard)\b",
        r"\bout\s+of\s+(?:form|sorts)\b",
        r"\bhard\s+to\s+win\s+with\b",
        r"\bquestion\s+marks?\s+(?:over|about)\b",
        r"\bdoubt(?:ful|s)?\b",
    ],
    "unsupported_hype_claim": [
        r"\btalented\b(?!.*\bshown\b)",
        r"\bexciting\s+prospect\b",
        r"\bone\s+to\s+follow\b",
        r"\bcould\s+be\s+(?:very\s+)?special\b",
        r"\bwatching\s+brief\b",
        r"\bhas\s+ability\b(?!.*shown|.*demonstrated)",
        r"\bshould\s+(?:go\s+)?well\b(?!.*specific|.*reason)",
        r"\bworth\s+noting\b(?!.*because|.*as\s+)",
        r"\bkeep\s+in\s+mind\b",
        r"\bpotential\b(?!.*shown|.*demonstrated|.*injury)",
    ],
}

# ── Helpers ────────────────────────────────────────────────────────────────────

def _extract_claims(text: str) -> dict:
    if not text or not isinstance(text, str):
        return {k: False for k in PATTERNS}
    text_lower = text.lower()
    result = {}
    for claim_type, pats in PATTERNS.items():
        matched = any(re.search(p, text_lower) for p in pats)
        result[claim_type] = matched
    return result


def _count_claims(claims: dict) -> int:
    return sum(1 for v in claims.values() if v)


# ── Load sources ───────────────────────────────────────────────────────────────

def load_horse_comments_from_supabase() -> list[dict]:
    """Try to load horse_comments from Supabase via REST."""
    import requests
    url = os.getenv("SUPABASE_URL", "")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "") or os.getenv("SUPABASE_KEY", "")
    if not url or not key:
        return []
    try:
        resp = requests.get(
            f"{url}/rest/v1/horse_comments",
            headers={"apikey": key, "Authorization": f"Bearer {key}"},
            params={"select": "id,horse_id,horse_name,race_id,race_date,comment_raw",
                    "limit": "10000"},
            timeout=15,
        )
        if resp.status_code == 200:
            data = resp.json()
            print(f"  horse_comments from Supabase: {len(data)} rows")
            return data
        else:
            print(f"  horse_comments Supabase: {resp.status_code} — skipping")
    except Exception as e:
        print(f"  horse_comments Supabase error: {e}")
    return []


def load_rp_profile_comments() -> list[dict]:
    """Load horse_comment field from rp_runner_profile_latest.parquet if populated."""
    if not RP_PROFILE_PATH.exists():
        return []
    try:
        df = pd.read_parquet(RP_PROFILE_PATH)
        if "horse_comment" not in df.columns:
            return []
        has_comment = df[df["horse_comment"].notna() & (df["horse_comment"] != "")]
        if len(has_comment) == 0:
            print(f"  RP profile: {len(df)} rows loaded, horse_comment field empty")
            return []
        print(f"  RP profile: {len(has_comment)} rows with comments")
        rows = []
        for _, row in has_comment.iterrows():
            rows.append({
                "horse_id": str(row.get("horse_id", "")),
                "horse_name": str(row.get("horse_norm", row.get("horse", ""))),
                "race_id": None,
                "race_date": None,
                "comment_raw": str(row["horse_comment"]),
                "source": "rp_profile",
            })
        return rows
    except Exception as e:
        print(f"  RP profile comments error: {e}")
        return []


# ── Main ──────────────────────────────────────────────────────────────────────

def run():
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")

    print("\nRP CLAIM EXTRACTOR — REGEX BASELINE")
    print("=" * 60)

    # Load sources
    supabase_rows = load_horse_comments_from_supabase()
    rp_rows = load_rp_profile_comments()

    # Merge — horse_comments table takes priority (richer metadata)
    combined = []
    seen_ids = set()

    for row in supabase_rows:
        hid = str(row.get("horse_id", "")) or ""
        combined.append({
            "horse_id": hid,
            "horse_name": str(row.get("horse_name", "")),
            "race_id": str(row.get("race_id", "") or ""),
            "race_date": str(row.get("race_date", "") or ""),
            "comment_raw": str(row.get("comment_raw", "") or ""),
            "source": "supabase_horse_comments",
        })
        if hid:
            seen_ids.add(hid)

    for row in rp_rows:
        if row["horse_id"] not in seen_ids:
            combined.append(row)

    print(f"Total comment records: {len(combined)}")

    if len(combined) == 0:
        print("No comment data available. Outputting empty baseline.")

    # Extract claims for each record
    records = []
    for row in combined:
        claims = _extract_claims(row["comment_raw"])
        n_claims = _count_claims(claims)
        rec = {
            "horse_id": row["horse_id"],
            "horse_name": row["horse_name"],
            "race_id": row.get("race_id"),
            "race_date": row.get("race_date"),
            "comment_raw": row["comment_raw"],
            "source": row.get("source", "unknown"),
            "n_claims_detected": n_claims,
            **{f"claim_{k}": v for k, v in claims.items()},
            "extracted_at": datetime.now(timezone.utc).isoformat(),
        }
        records.append(rec)

    df = pd.DataFrame(records) if records else pd.DataFrame(columns=[
        "horse_id", "horse_name", "race_id", "race_date", "comment_raw",
        "source", "n_claims_detected",
        *[f"claim_{k}" for k in PATTERNS],
        "extracted_at",
    ])

    # Claim coverage stats
    print("\nClaim coverage (of records with non-empty comments):")
    non_empty = df[df["comment_raw"].str.len() > 0] if len(df) > 0 else df
    for k in PATTERNS:
        col = f"claim_{k}"
        if col in df.columns and len(non_empty) > 0:
            pct = non_empty[col].sum() / len(non_empty) * 100
            print(f"  {k:<30} {non_empty[col].sum():>4} / {len(non_empty)} ({pct:.1f}%)")

    # Save outputs
    df.to_parquet(OUT_PARQUET, index=False)
    print(f"\nParquet: {OUT_PARQUET}")

    # JSON summary (not full row dump — just the claims per horse)
    summary = {
        "run_at": datetime.now(timezone.utc).isoformat(),
        "total_records": len(df),
        "sources": {
            "supabase_horse_comments": len(supabase_rows),
            "rp_profile": len(rp_rows),
        },
        "claim_coverage": {},
        "sample_extractions": [],
        "governance": {
            "phase": "A_REGEX_BASELINE",
            "no_scoring_change": True,
            "no_live_state_mutation": True,
            "phase_b_dspy_pending_approval": True,
        },
    }
    if len(non_empty) > 0:
        for k in PATTERNS:
            col = f"claim_{k}"
            if col in df.columns:
                summary["claim_coverage"][k] = {
                    "n": int(non_empty[col].sum()),
                    "pct": round(float(non_empty[col].sum() / len(non_empty) * 100), 1),
                }

    # Sample: top 5 highest-claim rows
    if len(df) > 0 and "n_claims_detected" in df.columns:
        top = df.nlargest(5, "n_claims_detected")
        for _, r in top.iterrows():
            claims_detected = [k for k in PATTERNS if r.get(f"claim_{k}", False)]
            summary["sample_extractions"].append({
                "horse_name": r["horse_name"],
                "n_claims": int(r["n_claims_detected"]),
                "claims": claims_detected,
                "comment_snippet": r["comment_raw"][:150] if r["comment_raw"] else "",
            })

    OUT_JSON.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(f"JSON:    {OUT_JSON}")

    _write_md(summary, df)
    print(f"MD:      {OUT_MD}")
    print("=" * 60)


def _write_md(summary: dict, df: pd.DataFrame) -> None:
    cov = summary.get("claim_coverage", {})
    lines = [
        "# VÉLØ RP CLAIM EXTRACTOR — REGEX BASELINE",
        "",
        f"**Run at:** {summary['run_at']}  ",
        f"**Total records processed:** {summary['total_records']}  ",
        f"**Sources:** Supabase horse_comments={summary['sources']['supabase_horse_comments']}, "
        f"RP profile={summary['sources']['rp_profile']}",
        "",
        "---",
        "",
        "## Claim Coverage",
        "",
        "| Claim Type | Count | Coverage % |",
        "|---|---|---|",
    ]
    for k, v in cov.items():
        lines.append(f"| {k} | {v['n']} | {v['pct']}% |")

    lines += ["", "---", "", "## Sample High-Claim Records", ""]
    for s in summary.get("sample_extractions", []):
        lines.append(f"**{s['horse_name']}** — {s['n_claims']} claims detected")
        lines.append(f"Claims: {', '.join(s['claims'])}")
        lines.append(f"> {s['comment_snippet']}")
        lines.append("")

    lines += [
        "---",
        "",
        "## Claim Type Definitions",
        "",
        "| Type | Description |",
        "|---|---|",
        "| improvement_claim | Horse expected to improve (green, first run, strip fitter) |",
        "| handicap_claim | Handicap mark or rating assessment |",
        "| stable_intent_claim | Trainer/connections interest or intent signals |",
        "| trip_claim | Trip/distance preference stated |",
        "| ground_claim | Going/ground preference stated |",
        "| class_claim | Drop or rise in class noted |",
        "| fitness_claim | Fitness level signal (well, spot-on, needed run) |",
        "| negative_claim | Negative flag (disappointing, below par, pulled up) |",
        "| unsupported_hype_claim | Vague positive filler with no structural basis |",
        "",
        "---",
        "",
        "## Governance",
        "",
        "```",
        "Phase A — regex baseline. Read-only.",
        "Does not modify scoring, routing, or live state.",
        "Phase B (DSPy pipeline) requires operator approval.",
        "Phase C (fine-tuned SLM) requires GPU + separate approval.",
        "```",
    ]
    OUT_MD.write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    run()
