"""
RPDC Tag Value Audit — scripts/audit_rpdc_tag_value.py

Joins RPDC historical JSONL tags with sigma_audits outcomes to measure per-tag
predictive value. Compares RPDC-tagged runners against the full population to
identify which tags add signal (VALUE_POSITIVE), which are noise (NOISE), and
which may be anti-signals (TRAP_WARNING).

Data sources:
  - data/rpdc_backfill/rpdc_tags_historical.jsonl (local, 18,554 rows)
  - Supabase sigma_audits table (2237 rows, 72 dates)

Join strategy:
  - sigma_audits is race-level (one row per race). Top pick horse name is
    extracted from notes.summary "pred=..." field.
  - RPDC JSONL is horse-level. Match by normalised horse name + race_date.
  - Overlap period: 2026-03-17 to 2026-05-23 (44 RPDC-covered dates).

Hard constraints:
  - Read-only. No Supabase writes. No scoring changes.
  - Outputs: data/reports/rpdc_tag_value_latest.json + .md

Usage:
  PYTHONPATH=. python scripts/audit_rpdc_tag_value.py
"""
from __future__ import annotations

import json
import os
import re
import sys
import urllib.request
from collections import defaultdict
from datetime import date
from pathlib import Path

# ── constants ─────────────────────────────────────────────────────────────────

RPDC_JSONL = Path("data/rpdc_backfill/rpdc_tags_historical.jsonl")
REPORT_JSON = Path("data/reports/rpdc_tag_value_latest.json")
REPORT_MD = Path("data/reports/rpdc_tag_value_latest.md")
RPDC_OVERLAP_START = "2026-03-17"
RPDC_OVERLAP_END = "2026-05-23"
MIN_SAMPLE = 15  # minimum n for a classification verdict

SB_URL = os.getenv("SUPABASE_URL", "")
SB_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_SERVICE_KEY", "")
SB_HEADERS = {
    "apikey": SB_KEY,
    "Authorization": f"Bearer {SB_KEY}",
    "Content-Type": "application/json",
    "Accept": "application/json",
}


# ── Supabase helpers ───────────────────────────────────────────────────────────


def _sb_get(path: str) -> list[dict]:
    if not SB_URL or not SB_KEY:
        return []
    req = urllib.request.Request(
        f"{SB_URL}/rest/v1{path}",
        headers={**SB_HEADERS, "Prefer": ""},
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return json.loads(r.read())
    except Exception as e:
        print(f"  [SB GET FAIL] {path}: {e}")
        return []


def _sb_get_all(table: str, columns: str, filters: str = "") -> list[dict]:
    """Paginate Supabase table (max 1000 per page)."""
    rows: list[dict] = []
    offset = 0
    page_size = 1000
    while True:
        path = f"/{table}?select={columns}{filters}&limit={page_size}&offset={offset}"
        batch = _sb_get(path)
        if not batch:
            break
        rows.extend(batch)
        if len(batch) < page_size:
            break
        offset += page_size
    return rows


# ── name normalisation ─────────────────────────────────────────────────────────


def _norm_name(name: str) -> str:
    if not name:
        return ""
    n = name.lower()
    n = re.sub(r"\s*\([a-z]{2,3}\)\s*$", "", n)
    n = re.sub(r"\s+", " ", n).strip()
    return n


def _name_from_rp_slug(horse_id: str) -> str:
    """rp_CUR_sun_goddess → sun goddess"""
    parts = horse_id.split("_", 2)
    if len(parts) >= 3:
        return parts[2].replace("_", " ")
    return ""


# ── RPDC JSONL loader ──────────────────────────────────────────────────────────


def _load_rpdc_index(path: Path) -> dict[tuple[str, str], dict]:
    """
    Returns {(normalised_name, race_date): row} for all RPDC rows in the overlap period.
    race_date is YYYY-MM-DD string.
    """
    if not path.exists():
        print(f"  [RPDC] JSONL not found: {path}")
        return {}

    index: dict[tuple[str, str], dict] = {}
    total = 0
    in_range = 0
    no_tag = 0
    for line in path.read_text().splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        total += 1
        race_date = str(row.get("race_date", ""))[:10]
        if race_date < RPDC_OVERLAP_START or race_date > RPDC_OVERLAP_END:
            continue
        in_range += 1
        # field is "horse" in the JSONL schema
        name = _norm_name(row.get("horse") or row.get("horse_name") or "")
        if not name:
            continue
        if not row.get("rpdc_primary_tag"):
            no_tag += 1
        key = (name, race_date)
        if key not in index:
            index[key] = row
    print(f"  [RPDC] Loaded {total} rows total, {in_range} in overlap, {len(index)} unique (name, date) pairs, {no_tag} without primary tag")
    return index


# ── sigma_audits loader ────────────────────────────────────────────────────────


def _parse_pred_name(notes_str: str) -> str:
    """Extract predicted horse name from notes.summary 'pred=...' field."""
    if not notes_str:
        return ""
    try:
        notes = json.loads(notes_str)
        summary = notes.get("summary", "")
    except (json.JSONDecodeError, AttributeError):
        summary = str(notes_str)
    m = re.search(r"pred=([^\s|]+)", summary)
    if m:
        return m.group(1).strip()
    return ""


def _load_sigma_audits(start_date: str, end_date: str) -> list[dict]:
    """Pull sigma_audits rows in the overlap date range."""
    print(f"  [SIGMA] Fetching sigma_audits {start_date} → {end_date} from Supabase...")
    filters = f"&date=gte.{start_date}&date=lte.{end_date}"
    rows = _sb_get_all(
        "sigma_audits",
        "race_id,date,track,outcome,decision_tier,top_pick_position,actual_winner_name,actual_winner_sp,notes",
        filters=filters,
    )
    print(f"  [SIGMA] Fetched {len(rows)} sigma_audits rows")
    return rows


# ── tag classification ─────────────────────────────────────────────────────────


def _classify_tag(tag_stats: dict) -> str:
    n = tag_stats["n"]
    sr = tag_stats["sr"]
    frame = tag_stats["frame_rate"]

    if n < MIN_SAMPLE:
        return "INSUFFICIENT_SAMPLE"
    if sr >= 0.30 and frame >= 0.60:
        return "VALUE_POSITIVE"
    if frame >= 0.60:
        return "FRAME_POSITIVE"
    if sr <= 0.12 and n >= MIN_SAMPLE * 2:
        return "TRAP_WARNING"
    if sr < 0.18 and frame < 0.45:
        return "NOISE"
    return "WATCHLIST"


# ── main ───────────────────────────────────────────────────────────────────────


def main() -> None:
    print("=" * 60)
    print("RPDC Tag Value Audit")
    print("=" * 60)

    # Load RPDC index
    print("\nStep 1: Load RPDC JSONL")
    rpdc_index = _load_rpdc_index(RPDC_JSONL)
    if not rpdc_index:
        print("  ERROR: No RPDC data available. Aborting.")
        sys.exit(1)

    # Load sigma_audits
    print("\nStep 2: Load sigma_audits from Supabase")
    sigma_rows = _load_sigma_audits(RPDC_OVERLAP_START, RPDC_OVERLAP_END)
    if not sigma_rows:
        print("  ERROR: No sigma_audits rows found. Check Supabase connectivity.")
        sys.exit(1)

    # Join
    print("\nStep 3: Join RPDC tags to sigma outcomes")
    tag_outcomes: dict[str, list[dict]] = defaultdict(list)
    no_tag_outcomes: list[dict] = []
    matched = 0
    unmatched = 0

    for row in sigma_rows:
        race_date = str(row.get("date", ""))[:10]
        outcome = row.get("outcome", "MISS")

        # Extract predicted horse name from notes
        notes_raw = row.get("notes") or ""
        pred_name = _parse_pred_name(notes_raw)
        if not pred_name:
            unmatched += 1
            continue

        norm = _norm_name(pred_name)
        key = (norm, race_date)

        rpdc_row = rpdc_index.get(key)
        if rpdc_row is None:
            no_tag_outcomes.append({"outcome": outcome, "date": race_date})
            unmatched += 1
            continue

        matched += 1
        primary_tag = rpdc_row.get("rpdc_primary_tag") or "UNKNOWN"
        tags_raw = rpdc_row.get("rpdc_tags", [])
        if isinstance(tags_raw, str):
            try:
                tags_raw = json.loads(tags_raw)
            except Exception:
                tags_raw = [tags_raw] if tags_raw else []

        record = {
            "outcome": outcome,
            "date": race_date,
            "horse_name": pred_name,
            "release_score": rpdc_row.get("rpdc_release_score", rpdc_row.get("release_score", 0.0)),
            "cash_window": rpdc_row.get("rpdc_cash_window_flag", rpdc_row.get("cash_window_flag", False)),
            "decision_tier": row.get("decision_tier"),
            "sp": row.get("actual_winner_sp"),
        }

        tag_outcomes[primary_tag].append(record)
        for tag in tags_raw:
            if tag != primary_tag:
                tag_outcomes[f"_secondary_{tag}"].append(record)

    total = len(sigma_rows)
    print(f"  Total sigma rows: {total}")
    print(f"  Matched to RPDC: {matched} ({matched/total*100:.1f}%)")
    print(f"  No RPDC tag (unmatched): {unmatched} ({unmatched/total*100:.1f}%)")

    # Global baseline from unmatched (no RPDC history)
    global_sr = sum(1 for r in sigma_rows if r.get("outcome") == "WIN") / max(len(sigma_rows), 1)
    global_frame = sum(1 for r in sigma_rows if r.get("outcome") in ("WIN", "PLACED")) / max(len(sigma_rows), 1)

    # Per-tag stats
    print("\nStep 4: Compute per-tag statistics")
    tag_stats_list: list[dict] = []

    for tag, records in sorted(tag_outcomes.items()):
        if tag.startswith("_secondary_"):
            continue  # primary tags only in main table
        n = len(records)
        wins = sum(1 for r in records if r["outcome"] == "WIN")
        frames = sum(1 for r in records if r["outcome"] in ("WIN", "PLACED"))
        cash_n = sum(1 for r in records if r.get("cash_window"))
        sr = wins / n if n > 0 else 0.0
        frame_rate = frames / n if n > 0 else 0.0
        sr_lift = sr - global_sr
        frame_lift = frame_rate - global_frame

        stats = {
            "tag": tag,
            "n": n,
            "wins": wins,
            "frames": frames,
            "sr": round(sr, 4),
            "frame_rate": round(frame_rate, 4),
            "sr_lift": round(sr_lift, 4),
            "frame_lift": round(frame_lift, 4),
            "cash_window_n": cash_n,
            "cash_window_rate": round(cash_n / n, 4) if n > 0 else 0.0,
        }
        stats["classification"] = _classify_tag(stats)
        tag_stats_list.append(stats)

    # No-RPDC baseline
    nr_n = len(no_tag_outcomes)
    nr_wins = sum(1 for r in no_tag_outcomes if r["outcome"] == "WIN")
    nr_frames = sum(1 for r in no_tag_outcomes if r["outcome"] in ("WIN", "PLACED"))
    no_rpdc_stats = {
        "tag": "NO_RPDC_HISTORY",
        "n": nr_n,
        "wins": nr_wins,
        "frames": nr_frames,
        "sr": round(nr_wins / nr_n, 4) if nr_n > 0 else 0.0,
        "frame_rate": round(nr_frames / nr_n, 4) if nr_n > 0 else 0.0,
        "sr_lift": 0.0,
        "frame_lift": 0.0,
        "cash_window_n": 0,
        "cash_window_rate": 0.0,
        "classification": "BASELINE_UNMATCHED",
    }
    tag_stats_list.sort(key=lambda x: x["sr"], reverse=True)

    # Build output
    output = {
        "generated_at": str(date.today()),
        "rpdc_source": str(RPDC_JSONL),
        "overlap_start": RPDC_OVERLAP_START,
        "overlap_end": RPDC_OVERLAP_END,
        "total_sigma_rows": total,
        "matched_to_rpdc": matched,
        "unmatched": unmatched,
        "match_rate": round(matched / total, 4) if total > 0 else 0.0,
        "global_baseline_sr": round(global_sr, 4),
        "global_baseline_frame": round(global_frame, 4),
        "min_sample_threshold": MIN_SAMPLE,
        "tag_stats": tag_stats_list,
        "no_rpdc_baseline": no_rpdc_stats,
        "supabase_mutated": False,
    }

    # Write JSON
    REPORT_JSON.parent.mkdir(parents=True, exist_ok=True)
    REPORT_JSON.write_text(json.dumps(output, indent=2))
    print(f"\n  Written: {REPORT_JSON}")

    # Write markdown
    _write_md(output)
    print(f"  Written: {REPORT_MD}")

    # Print summary
    print("\n" + "=" * 60)
    print("RPDC TAG VALUE AUDIT — RESULTS")
    print("=" * 60)
    print(f"Overlap period: {RPDC_OVERLAP_START} → {RPDC_OVERLAP_END}")
    print(f"Sigma rows:     {total}  (matched: {matched} = {matched/total*100:.1f}%)")
    print(f"Global SR:      {global_sr*100:.1f}%  Frame: {global_frame*100:.1f}%")
    print()
    print(f"{'Tag':<28} {'n':>5} {'SR':>7} {'Frame':>7} {'Lift SR':>8} {'Classification'}")
    print("-" * 75)
    for s in tag_stats_list:
        print(
            f"{s['tag']:<28} {s['n']:>5} {s['sr']*100:>6.1f}%"
            f" {s['frame_rate']*100:>6.1f}% {s['sr_lift']*100:>+7.1f}pp  {s['classification']}"
        )
    print("-" * 75)
    s = no_rpdc_stats
    print(
        f"{s['tag']:<28} {s['n']:>5} {s['sr']*100:>6.1f}%"
        f" {s['frame_rate']*100:>6.1f}%   (no RPDC match)"
    )


def _write_md(output: dict) -> None:
    lines = [
        "# RPDC Tag Value Audit",
        "",
        f"**Generated:** {output['generated_at']}  ",
        f"**Overlap period:** {output['overlap_start']} → {output['overlap_end']}  ",
        f"**Total sigma rows:** {output['total_sigma_rows']}  ",
        f"**Matched to RPDC:** {output['matched_to_rpdc']} ({output['match_rate']*100:.1f}%)  ",
        f"**Global SR baseline:** {output['global_baseline_sr']*100:.1f}%  ",
        f"**Global Frame baseline:** {output['global_baseline_frame']*100:.1f}%  ",
        "",
        "---",
        "",
        "## Per-Tag Results (primary tag, sorted by SR)",
        "",
        f"| Tag | n | SR | Frame | SR Lift | Frame Lift | Cash Window | Classification |",
        f"|---|---|---|---|---|---|---|---|",
    ]
    for s in output["tag_stats"]:
        lines.append(
            f"| {s['tag']} | {s['n']} | {s['sr']*100:.1f}% | {s['frame_rate']*100:.1f}%"
            f" | {s['sr_lift']*100:+.1f}pp | {s['frame_lift']*100:+.1f}pp"
            f" | {s['cash_window_n']} ({s['cash_window_rate']*100:.0f}%)"
            f" | **{s['classification']}** |"
        )

    nr = output["no_rpdc_baseline"]
    lines += [
        f"| {nr['tag']} | {nr['n']} | {nr['sr']*100:.1f}% | {nr['frame_rate']*100:.1f}%"
        f" | — | — | — | BASELINE_UNMATCHED |",
        "",
        "---",
        "",
        "## Classification Guide",
        "",
        "| Class | Criteria |",
        "|---|---|",
        "| VALUE_POSITIVE | SR ≥ 30%, Frame ≥ 60% |",
        "| FRAME_POSITIVE | Frame ≥ 60% (SR below threshold) |",
        "| WATCHLIST | Between NOISE and VALUE_POSITIVE |",
        "| NOISE | SR < 18%, Frame < 45% |",
        "| TRAP_WARNING | SR ≤ 12%, n ≥ 30 |",
        "| INSUFFICIENT_SAMPLE | n < 15 |",
        "| BASELINE_UNMATCHED | No RPDC history (no tag) |",
        "",
        "---",
        "",
        "## Immutability",
        "",
        "```",
        "SUPABASE_MUTATED:    FALSE",
        "SCORING_CHANGE:      NONE",
        "MODEL_CHANGE:        NONE",
        "```",
    ]
    REPORT_MD.write_text("\n".join(lines))


if __name__ == "__main__":
    main()
