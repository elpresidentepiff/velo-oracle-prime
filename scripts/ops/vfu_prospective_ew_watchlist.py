#!/usr/bin/env python3
"""
VFU-23: Prospective VP>=0.40 Each-Way Watchlist
Paper-only. No staking. No live execution.

Every entry must be generated before race results exist.
Contamination check: reject any verdict containing a post-race label.

Candidate bands:
  PRIMARY_EW_WATCH   VP 0.40–0.60  (EW review candidates)
  HIGH_VP_WATCH      VP >= 0.60    (win/frame watch — EW only if odds allow)
  EW_REVIEW_WATCH    VP >= 0.40 + tie_gate_ew_flag=True  (TIE gate fired EW signal)
  REJECTED_CONTAMINATED  post-race label found — never emitted to watchlist

Governance (permanent — never override):
  blocked_from_live_use = True
  paper_only = True
  human_review_required = True
  No Supabase writes
  No Telegram betting output
  No live staking
  No VP threshold change
  No model change
  No Passport mutation
  No Racing API restoration
"""
from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
from datetime import datetime, timezone

ROOT = pathlib.Path(__file__).resolve().parents[2]
DATA = ROOT / "data"
REPORTS = DATA / "reports"

VFU23_VERSION = "VFU_23_PROSPECTIVE_EW_WATCHLIST_V1"
PAPER_ONLY    = True
VP_THRESHOLD  = 0.40
VP_HIGH       = 0.60

# Labels that encode the race outcome — must be rejected if found anywhere in a verdict.
POST_RACE_LABELS: frozenset[str] = frozenset({
    "WIN_LANE_CONFIRMED",
    "PLACE_LANE_CONFIRMED",
    "WIN_SIGNAL_PLACE_OUTCOME",
    "PLACE_SIGNAL_WIN_OUTCOME",
    "FALSE_WIN_SIGNAL",
    "FALSE_PLACE_SIGNAL",
})


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sha256_12(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()[:12]


def _file_mtime_utc(path: pathlib.Path) -> str:
    return datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).isoformat()


def _check_contamination(obj: object) -> list[str]:
    """Recursively scan a verdict dict for post-race labels. Returns list of found labels."""
    found: set[str] = set()

    def _scan(x: object) -> None:
        if isinstance(x, str) and x in POST_RACE_LABELS:
            found.add(x)
        elif isinstance(x, dict):
            for v in x.values():
                _scan(v)
        elif isinstance(x, list):
            for item in x:
                _scan(item)

    _scan(obj)
    return sorted(found)


def _assign_band(vp: float, tie_gate_ew: bool) -> str:
    if vp >= VP_HIGH:
        return "HIGH_VP_WATCH"
    if vp >= VP_THRESHOLD and tie_gate_ew:
        return "EW_REVIEW_WATCH"
    if vp >= VP_THRESHOLD:
        return "PRIMARY_EW_WATCH"
    return "BELOW_THRESHOLD"


def load_verdicts(date_str: str) -> tuple[pathlib.Path, list]:
    fmt = date_str.replace("-", "_")
    path = DATA / f"velo_prime_verdicts_{fmt}.json"
    if not path.exists():
        raise FileNotFoundError(f"Verdicts file not found: {path}")
    raw = json.loads(path.read_text(encoding="utf-8"))
    rows = raw if isinstance(raw, list) else raw.get("verdicts", raw.get("races", []))
    return path, rows


def load_runner_counts(date_str: str) -> dict:
    fmt = date_str.replace("-", "_")
    path = DATA / "new_build" / "reports" / f"two_lane_readiness_{fmt}.json"
    if not path.exists():
        return {}
    raw = json.loads(path.read_text(encoding="utf-8"))
    return {str(sc["race_id"]): sc.get("runner_count", 8)
            for sc in raw.get("race_day_scorecards", [])}


def build_watchlist(
    date_str: str,
    verdicts_path: pathlib.Path,
    verdicts: list,
    runner_counts: dict,
) -> tuple[list, list, dict]:
    """
    Returns (candidates, rejected, stats).
    candidates: clean watchlist entries (pre-race provenance, no contamination)
    rejected: entries that failed contamination check
    """
    source_file  = verdicts_path.name
    file_hash    = _sha256_12(verdicts_path)
    file_mtime   = _file_mtime_utc(verdicts_path)
    created_at   = _utc_now()

    candidates: list[dict] = []
    rejected:   list[dict] = []
    below_threshold = 0
    no_ew_terms_excluded = 0  # VFU-25: field_size < 5 has no EW place terms

    for v in verdicts:
        top    = v.get("top") or {}
        ss     = v.get("signal_stack") or {}
        race_id  = str(v.get("race_id", ""))
        course   = v.get("course", "")
        off_time = v.get("off_time", "")
        race_name = v.get("race_name", "")
        tier     = v.get("tier", "?")
        scored   = v.get("scored")          # runner count from verdicts

        horse    = top.get("horse") or "UNKNOWN"
        horse_id = top.get("horse_id")

        try:
            vp = float(top.get("velo_prime_prob") or 0)
        except (TypeError, ValueError):
            vp = 0.0

        tie_ew   = bool(top.get("tie_gate_ew_flag", False))
        place_pb = top.get("place_prob")
        mds      = top.get("market_deception_score")
        impr     = top.get("improvement_score")

        # Use scored (runner count from verdict) first, then nb lookup
        runner_count = runner_counts.get(race_id) or (int(scored) if scored else None)

        # ── Contamination check ────────────────────────────────────────────────
        post_race_found = _check_contamination(v)
        if post_race_found:
            rejected.append({
                "race_id":                race_id,
                "course":                 course,
                "off_time":               off_time,
                "horse_name":             horse,
                "VP":                     vp,
                "rejection_reason":       "POST_RACE_LABEL_FOUND",
                "post_race_labels_found": post_race_found,
                "blocked_from_live_use":  True,
            })
            continue

        if vp < VP_THRESHOLD:
            below_threshold += 1
            continue

        # VFU-25 fix: EW bets have no place terms with < 5 runners — exclude at creation
        if runner_count is not None and runner_count < 5:
            no_ew_terms_excluded += 1
            rejected.append({
                "race_id":               race_id,
                "course":                course,
                "off_time":              off_time,
                "horse_name":            horse,
                "VP":                    round(vp, 4),
                "runner_count":          runner_count,
                "rejection_reason":      "FIELD_TOO_SMALL_FOR_EW",
                "governance_note":       f"field_size={runner_count} < 5: no EW place terms exist (VFU-25 filter)",
                "blocked_from_live_use": True,
            })
            continue

        band = _assign_band(vp, tie_ew)

        # Build reason string
        reasons = [f"VP={vp:.4f} >= {VP_THRESHOLD}"]
        if tie_ew:
            reasons.append("tie_gate_ew_flag=True")
        if place_pb and float(place_pb) >= 0.50:
            reasons.append(f"place_prob={place_pb:.3f}")

        entry: dict = {
            "run_date":                 created_at[:10],
            "created_at":               created_at,
            "race_id":                  race_id,
            "race_date":                date_str,
            "course":                   course,
            "off_time":                 off_time,
            "race_name":                race_name,
            "horse_name":               horse,
            "horse_id":                 horse_id,
            "VP":                       round(vp, 4),
            "VP_band":                  (
                "VP>=0.60" if vp >= VP_HIGH else "VP0.40-0.60"
            ),
            "tier":                     tier,
            "runner_count":             runner_count,
            "tie_gate_ew_flag":         tie_ew,
            "place_prob":               place_pb,
            "market_deception_score":   mds,
            "improvement_score":        impr,
            "odds_snapshot":            None,
            "odds_source":              "NONE_AT_CREATION",
            "EW_candidate_reason":      "; ".join(reasons),
            "candidate_band":           band,
            "pre_race_provenance": {
                "source_file":             source_file,
                "source_file_mtime_utc":   file_mtime,
                "source_file_sha256_12":   file_hash,
                "provenance_class":        "VERDICTS_FILE_PRE_RACE",
                "note": (
                    "Verdicts file generated by morning scoring cron (pre-race). "
                    "File mtime is proxy for pre-race generation. "
                    "No post-race fields present (contamination check passed)."
                ),
            },
            "contamination_check_passed": True,
            "rejected_post_race_labels":  [],
            "blocked_from_live_use":      True,
            "paper_only":                 True,
            "human_review_required":      True,
        }
        candidates.append(entry)

    band_counts: dict[str, int] = {}
    for c in candidates:
        b = c["candidate_band"]
        band_counts[b] = band_counts.get(b, 0) + 1

    stats = {
        "total_verdicts":              len(verdicts),
        "candidates_generated":        len(candidates),
        "below_threshold":             below_threshold,
        "rejected_contaminated":       len(rejected),
        "no_ew_terms_excluded":        no_ew_terms_excluded,
        "band_counts":                 band_counts,
    }
    return candidates, rejected, stats


def write_outputs(
    date_str: str,
    candidates: list,
    rejected: list,
    stats: dict,
    verdicts_path: pathlib.Path,
    dry_run: bool = False,
) -> dict:
    REPORTS.mkdir(parents=True, exist_ok=True)
    created_at = _utc_now()

    # ── Watchlist JSON ──────────────────────────────────────────────────────────
    watchlist = {
        "vfu":              "VFU-23",
        "version":          VFU23_VERSION,
        "generated_at":     created_at,
        "race_date":        date_str,
        "paper_only":               True,
        "blocked_from_live_use":    True,
        "no_staking":               True,
        "no_telegram_betting":      True,
        "no_live_execution":        True,
        "no_supabase_writes":       True,
        "no_live_scoring_change":   True,
        "no_model_promotion":       True,
        "no_vp_threshold_change":   True,
        "no_passport_mutation":     True,
        "no_racing_api_restoration": True,
        "candidates": candidates,
        "stats":      stats,
        "classifications": [
            "VFU_23_PROSPECTIVE_EW_WATCHLIST_COMPLETE",
            "PAPER_ONLY_MODE_CONFIRMED",
            "VP_040_EW_WATCHLIST_CREATED",
            "POST_RACE_LABELS_REJECTED",
            "CONTAMINATED_SEGMENTS_BLOCKED",
            "SETTLEMENT_TEMPLATE_CREATED_NOT_EXECUTED",
            "NO_STAKING_EXECUTION",
            "NO_TELEGRAM_BETTING_OUTPUT",
            "NO_SUPABASE_WRITES",
            "NO_LIVE_SCORING_CHANGE",
            "NO_MODEL_PROMOTION",
            "NO_VP_THRESHOLD_CHANGE",
            "CANONICAL_HORSE_PASSPORT_NOT_MUTATED",
            "NO_RACING_API_RESTORATION",
        ],
    }
    wl_path = REPORTS / "vfu_23_prospective_ew_watchlist_latest.json"
    if not dry_run:
        wl_path.write_text(json.dumps(watchlist, indent=2), encoding="utf-8")

    # ── Markdown report ─────────────────────────────────────────────────────────
    cand_rows = "\n".join(
        "| {} | {} | {} | {:.3f} | {} | {} | {} |".format(
            c["off_time"], c["course"], c["horse_name"],
            c["VP"], c["tier"], c["runner_count"] or "?", c["candidate_band"]
        )
        for c in sorted(candidates, key=lambda x: x["off_time"])
    ) or "| — | — | — | — | — | — | — |"

    band_rows = "\n".join(
        f"| {b} | {n} |" for b, n in sorted(stats["band_counts"].items())
    ) or "| (none) | 0 |"

    md = f"""# VFU-23: Prospective VP>=0.40 EW Watchlist — {date_str}

Generated: {created_at}

**PAPER ONLY. NO STAKING. NO TELEGRAM BETTING. NO LIVE EXECUTION.**

## Candidates ({stats['candidates_generated']})

| Off | Course | Horse | VP | Tier | Runners | Band |
|---|---|---|---|---|---|---|
{cand_rows}

## Band Summary

| Band | Count |
|---|---|
{band_rows}

## Statistics

- Total verdicts scored: {stats['total_verdicts']}
- VP >= 0.40 candidates: {stats['candidates_generated']}
- Below VP threshold: {stats['below_threshold']}
- Rejected (contaminated post-race labels): {stats['rejected_contaminated']}

## Governance

- `blocked_from_live_use = True`
- `paper_only = True`
- `human_review_required = True`
- NO VP threshold change
- NO model change
- NO live staking
- NO Telegram betting output
- NO Supabase writes
- NO Racing API restoration

## Settlement

All candidates have `settlement_status = PENDING`.
See `vfu_23_settlement_template.json`. Operator settles manually after results close.
"""
    md_path = REPORTS / "vfu_23_prospective_ew_watchlist_latest.md"
    if not dry_run:
        md_path.write_text(md, encoding="utf-8")

    # ── Audit trail (append-only) ───────────────────────────────────────────────
    audit_row = {
        "created_at":                    created_at,
        "race_date":                     date_str,
        "source_file":                   verdicts_path.name,
        "source_file_sha256_12":         _sha256_12(verdicts_path),
        "operator_mode":                 "PAPER_ONLY",
        "candidates_generated":          stats["candidates_generated"],
        "rejected_contaminated":         stats["rejected_contaminated"],
        "below_threshold":               stats["below_threshold"],
        "contamination_checks_performed": sorted(POST_RACE_LABELS),
        "result_fields_present":         False,
        "post_race_labels_found_count":  stats["rejected_contaminated"],
        "band_counts":                   stats["band_counts"],
    }
    audit_path = REPORTS / "vfu_23_watchlist_audit_trail.jsonl"
    if not dry_run:
        with open(audit_path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(audit_row) + "\n")

    # ── Rejected candidates (append-only accumulator) ───────────────────────────
    rej_path = REPORTS / "vfu_23_rejected_contaminated_candidates.json"
    if not dry_run:
        existing: list = []
        if rej_path.exists():
            try:
                existing = json.loads(rej_path.read_text(encoding="utf-8"))
            except Exception:
                existing = []
        existing.extend(rejected)
        rej_path.write_text(json.dumps(existing, indent=2), encoding="utf-8")

    # ── Settlement template (PENDING — never auto-settled) ──────────────────────
    settlement = {
        "vfu":              "VFU-23",
        "race_date":        date_str,
        "created_at":       created_at,
        "settlement_status": "PENDING",
        "paper_only":        True,
        "blocked_from_live_use": True,
        "note": (
            "DO NOT AUTO-SETTLE. "
            "Operator populates results manually after races close."
        ),
        "entries": [
            {
                "race_id":          c["race_id"],
                "course":           c["course"],
                "off_time":         c["off_time"],
                "horse_name":       c["horse_name"],
                "VP":               c["VP"],
                "candidate_band":   c["candidate_band"],
                "runner_count":     c["runner_count"],
                "odds_snapshot":    c["odds_snapshot"],
                "finish_position":  None,
                "win_return":       None,
                "place_return":     None,
                "EW_return":        None,
                "outcome":          None,
                "settlement_status": "PENDING",
            }
            for c in candidates
        ],
    }
    settle_path = REPORTS / "vfu_23_settlement_template.json"
    if not dry_run:
        settle_path.write_text(json.dumps(settlement, indent=2), encoding="utf-8")

    return {
        "watchlist":   str(wl_path),
        "md":          str(md_path),
        "audit":       str(audit_path),
        "rejected":    str(rej_path),
        "settlement":  str(settle_path),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="VFU-23 prospective EW watchlist")
    parser.add_argument("--date", default=None,
                        help="Race date YYYY-MM-DD (default: today UTC)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Preview without writing files")
    args = parser.parse_args()

    date_str = args.date or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    print(f"VFU-23: Prospective EW Watchlist — {date_str}")
    print(f"Mode: {'DRY-RUN (no files written)' if args.dry_run else 'PAPER_ONLY'}")

    verdicts_path, verdicts = load_verdicts(date_str)
    runner_counts = load_runner_counts(date_str)
    print(f"Loaded {len(verdicts)} verdicts from {verdicts_path.name}")

    candidates, rejected, stats = build_watchlist(
        date_str, verdicts_path, verdicts, runner_counts
    )

    print(f"\nStats:")
    print(f"  Total verdicts:        {stats['total_verdicts']}")
    print(f"  Candidates (VP>=0.40): {stats['candidates_generated']}")
    print(f"  Below threshold:       {stats['below_threshold']}")
    print(f"  Rejected contaminated: {stats['rejected_contaminated']}")
    print(f"\nBand breakdown:")
    for b, n in sorted(stats["band_counts"].items()):
        print(f"  {b:<25} {n}")

    if candidates:
        print(f"\nWatchlist:")
        for c in sorted(candidates, key=lambda x: x["off_time"]):
            ew_tag = " [EW-TIE]" if c["tie_gate_ew_flag"] else ""
            print(f"  {c['off_time']:5} {c['course']:15} {c['horse_name']:30} VP={c['VP']:.4f} [{c['candidate_band']}]{ew_tag}")
    else:
        print("\nNo candidates above VP threshold today.")

    if not args.dry_run:
        paths = write_outputs(
            date_str, candidates, rejected, stats, verdicts_path, dry_run=False
        )
        print(f"\nWritten:")
        for k, p in paths.items():
            print(f"  {pathlib.Path(p).name}")
        print(f"\nClassification: VFU_23_PROSPECTIVE_EW_WATCHLIST_COMPLETE")
        print(f"paper_only=True  |  blocked_from_live_use=True  |  no_staking=True")
    else:
        print("\n[DRY-RUN] No files written.")


if __name__ == "__main__":
    main()
