#!/usr/bin/env python3
"""
model_disagreement_audit.py
===========================
Shadow-lane evidence engine: does a challenger lane actually EARN ITS PLACE?

THE PROBLEM THIS CLOSES
-----------------------
Every nightly artifact reports each lane's headline strike rate side by side.
That number is close to useless for deciding whether a lane is worth keeping,
because lanes overlap: on 2026-09-18 MDS_HEAVY_SHADOW_V1 read as "27.8% vs
Main's 28.5%, nearly level" -- but it had picked the SAME horse as Main in 130
of 158 races (82%). Its whole independent contribution lived in 28 races, where
it went 3/28 against Main's 4/28. A lane that agrees 82% of the time cannot
diverge from the incumbent no matter how good it is; a headline SR hides that
completely, and a shadow lane can sit "nearly level" for months while adding
nothing at all.

So this audit splits every challenger against the incumbent on the EQUAL RACE
SET (races where both made a settled top pick -- comparing different race sets
is not a comparison) into:

    AGREE     -- same horse. Identical outcome by construction. Carries no
                 information about the challenger; reported only as overlap.
    DISAGREE  -- different horse. THIS is the challenger's entire independent
                 evidence, and the only cohort a keep/drop decision may use.

ROI IS REPORTED TWICE, ON PURPOSE
---------------------------------
Flat-stakes ROI over a few hundred picks is dominated by a handful of big-priced
winners. On 2026-09-15..18 both Main (+41.0%) and MDS-heavy (+21.4%) looked
strongly profitable; strip the four SP>=10 winners and they are -12.8% and
-18.5%. Every ROI here therefore ships with its `*_ex_bigprice` twin (winners at
SP >= 10.0 excluded). If the two disagree in sign, the lane has no proven edge
-- it has a lucky fortnight.

OUTPUTS (house convention, mirrors router_shadow_audit.py)
  data/model_disagreement_audit_latest.csv | .md          (overwritten)
  data/model_disagreement_audit_runs/..._<ts>.csv | .md   (immutable snapshot)
  data/model_disagreement_audit_ledger.csv                (append-only)

SOURCE
  data/reports/canonical_model_scorecard_*.csv -- the same per-date artifact
  Step 20C rebuilds results-aware and Step 20D persists. Local files only: no
  network, no credentials, no Supabase read, deterministic and rerunnable.

No live betting. No staking. No promotion. No model or router changes.
Verdicts here are EVIDENCE LABELS for the operator, never an action.

Usage:
  PYTHONPATH=. venv/bin/python scripts/ops/model_disagreement_audit.py
  PYTHONPATH=. venv/bin/python scripts/ops/model_disagreement_audit.py --window-days 30
  PYTHONPATH=. venv/bin/python scripts/ops/model_disagreement_audit.py --incumbent MAIN_VELO_PRIME
"""

from __future__ import annotations

import argparse
import csv
import glob
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

#: The daily artifact only. One-off variants (e.g. *_runtime.csv) carry a
#: different schema and are not part of the nightly series.
SCORECARD_GLOB = str(ROOT / "data" / "reports" / "canonical_model_scorecard_[0-9][0-9][0-9][0-9]_[0-9][0-9]_[0-9][0-9].csv")
AUDIT_CSV = ROOT / "data" / "model_disagreement_audit_latest.csv"
AUDIT_MD = ROOT / "data" / "model_disagreement_audit_latest.md"
RUNS_DIR = ROOT / "data" / "model_disagreement_audit_runs"
LEDGER_PATH = ROOT / "data" / "model_disagreement_audit_ledger.csv"

DEFAULT_INCUMBENT = "MAIN_VELO_PRIME"

#: Winners at or above this SP are stripped for the robustness twin. A flat-stake
#: book over a few hundred picks lives or dies on this handful of results.
BIGPRICE_SP = 10.0

#: A lane needs this many DISAGREEMENTS before its edge means anything. Below it
#: the verdict is INSUFFICIENT_EVIDENCE regardless of how good the numbers look.
MIN_DISAGREE_N = 30

#: At or above this agreement rate the lane is a copy of the incumbent: it cannot
#: express an independent opinion often enough to matter, whatever its SR says.
REDUNDANT_OVERLAP = 0.90

#: A lane silent for this long has been renamed or retired. Its history is still
#: scored, but it is labelled so a dead lane cannot top the table.
STALE_DAYS = 14

LEDGER_COLS = [
    "run_ts", "window", "incumbent", "challenger",
    "n_equal", "agree_n", "overlap_pct", "agree_sr",
    "disagree_n", "inc_sr", "chal_sr", "sr_edge_pts",
    "inc_roi", "chal_roi", "roi_edge_pts",
    "inc_roi_ex_bigprice", "chal_roi_ex_bigprice", "roi_edge_ex_bigprice_pts",
    "chal_only_wins", "inc_only_wins", "first_date", "last_date", "verdict",
]


# ── loading ──────────────────────────────────────────────────────────────────

def _f(value: str) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def load_top_picks(since: str | None = None) -> list[dict]:
    """Settled rank-1 picks from every local canonical scorecard CSV.

    A row with no result_position never entered a cohort: an unsettled race is
    absent evidence, not a loss.
    """
    rows: list[dict] = []
    for path in sorted(glob.glob(SCORECARD_GLOB)):
        with open(path, newline="", encoding="utf-8") as fh:
            for r in csv.DictReader(fh):
                if r.get("rank") != "1":
                    continue
                if not (r.get("result_position") or "").strip():
                    continue
                date = (r.get("date") or r.get("run_date") or "").strip()
                if not date:
                    continue
                if since and date < since:
                    continue
                horse = (r.get("horse") or "").strip()
                if not horse:
                    continue
                rows.append({
                    "date": date,
                    "race_id": (r.get("race_id") or "").strip(),
                    "model": (r.get("model_name") or "").strip(),
                    "horse": horse,
                    "win": (r.get("win") or "").strip().lower() == "true",
                    "frame": (r.get("frame") or "").strip().lower() == "true",
                    "sp": _f(r.get("sp_dec") or ""),
                })
    return rows


# ── metrics ──────────────────────────────────────────────────────────────────

def _pnl(picks: list[dict], *, exclude_bigprice: bool = False) -> float:
    """Flat 1pt P&L. A winner with no recorded SP returns its stake only, so a
    missing price can never invent profit."""
    total = 0.0
    for p in picks:
        if not p["win"]:
            total -= 1.0
            continue
        sp = p["sp"]
        if sp is None:
            continue
        if exclude_bigprice and sp >= BIGPRICE_SP:
            continue
        total += sp - 1.0
    return total


def cohort_metrics(picks: list[dict]) -> dict:
    n = len(picks)
    if not n:
        return {"n": 0, "wins": 0, "sr": None, "frame_pct": None,
                "pnl": 0.0, "roi": None, "roi_ex_bigprice": None}
    wins = sum(1 for p in picks if p["win"])
    pnl = _pnl(picks)
    pnl_ex = _pnl(picks, exclude_bigprice=True)
    return {
        "n": n,
        "wins": wins,
        "sr": round(100.0 * wins / n, 1),
        "frame_pct": round(100.0 * sum(1 for p in picks if p["frame"]) / n, 1),
        "pnl": round(pnl, 2),
        "roi": round(100.0 * pnl / n, 1),
        "roi_ex_bigprice": round(100.0 * pnl_ex / n, 1),
    }


def verdict_for(overlap: float, dis_n: int, sr_edge: float | None,
                roi_edge: float | None, roi_edge_ex: float | None,
                *, stale: bool = False) -> str:
    """Evidence label, never an instruction. Ordered so the cheapest disqualifier
    fires first: a retired lane is retired and a redundant lane is redundant even
    if their handful of disagreements look brilliant."""
    if stale:
        return "RETIRED_OR_RENAMED"
    if overlap >= REDUNDANT_OVERLAP * 100:
        return "REDUNDANT_WITH_INCUMBENT"
    if dis_n < MIN_DISAGREE_N:
        return "INSUFFICIENT_EVIDENCE"
    if sr_edge is None:
        return "INSUFFICIENT_EVIDENCE"
    if sr_edge > 0 and (roi_edge or 0) > 0 and (roi_edge_ex or 0) > 0:
        return "ADDING_EDGE"
    if sr_edge > 0 and (roi_edge or 0) > 0:
        return "EDGE_UNPROVEN_BIGPRICE_DEPENDENT"
    if sr_edge > 0:
        return "ADDING_WINS_NOT_ROI"
    if sr_edge < 0:
        return "SUBTRACTING_VS_INCUMBENT"
    return "NEUTRAL"


def compare(rows: list[dict], incumbent: str, challenger: str) -> dict | None:
    """Split the equal race set into AGREE / DISAGREE and score both sides."""
    inc = {r["race_id"]: r for r in rows if r["model"] == incumbent}
    chal_rows = [r for r in rows if r["model"] == challenger]
    chal = {r["race_id"]: r for r in chal_rows}
    shared = sorted(set(inc) & set(chal))
    if not shared:
        return None
    first_date, last_date = min(r["date"] for r in chal_rows), max(r["date"] for r in chal_rows)
    corpus_last = max(r["date"] for r in rows)
    stale = (datetime.strptime(corpus_last, "%Y-%m-%d")
             - datetime.strptime(last_date, "%Y-%m-%d")).days > STALE_DAYS

    agree_i, dis_i, dis_c = [], [], []
    for rid in shared:
        a, b = inc[rid], chal[rid]
        if a["horse"] == b["horse"]:
            agree_i.append(a)
        else:
            dis_i.append(a)
            dis_c.append(b)

    m_ai = cohort_metrics(agree_i)
    m_di = cohort_metrics(dis_i)
    m_dc = cohort_metrics(dis_c)

    def edge(a, b):
        return None if a is None or b is None else round(a - b, 1)

    sr_edge = edge(m_dc["sr"], m_di["sr"])
    roi_edge = edge(m_dc["roi"], m_di["roi"])
    roi_edge_ex = edge(m_dc["roi_ex_bigprice"], m_di["roi_ex_bigprice"])
    overlap = round(100.0 * len(agree_i) / len(shared), 1)

    return {
        "incumbent": incumbent,
        "challenger": challenger,
        "n_equal": len(shared),
        "agree_n": len(agree_i),
        "overlap_pct": overlap,
        "agree_sr": m_ai["sr"],
        "disagree_n": len(dis_i),
        "inc": m_di,
        "chal": m_dc,
        "sr_edge_pts": sr_edge,
        "roi_edge_pts": roi_edge,
        "roi_edge_ex_bigprice_pts": roi_edge_ex,
        # The operator's real question: which winners did only one of them find?
        "chal_only_wins": sum(1 for a, b in zip(dis_i, dis_c) if b["win"] and not a["win"]),
        "inc_only_wins": sum(1 for a, b in zip(dis_i, dis_c) if a["win"] and not b["win"]),
        "first_date": first_date,
        "last_date": last_date,
        "verdict": verdict_for(overlap, len(dis_i), sr_edge, roi_edge, roi_edge_ex, stale=stale),
    }


# ── rendering ────────────────────────────────────────────────────────────────

def _n(v, suffix="") -> str:
    return "—" if v is None else f"{v}{suffix}"


def render_md(reports: dict[str, list[dict]], incumbent: str, run_ts: str,
              date_span: tuple[str, str]) -> str:
    lines = [
        "# VÉLØ Model Disagreement Audit",
        f"Generated: {run_ts}",
        f"Incumbent: **{incumbent}** · Source dates: {date_span[0]} → {date_span[1]}",
        "",
        "**No live betting. No staking. No promotion. Evidence labels only.**",
        "",
        "A challenger's headline strike rate is not evidence — it is mostly the",
        "incumbent's picks reported back. Only the DISAGREE cohort carries the",
        "challenger's own opinion, so only that cohort may inform a keep/drop call.",
        f"Every ROI ships with an `ex-bigprice` twin (winners at SP ≥ {BIGPRICE_SP:g} removed);",
        "when the two disagree in sign, the lane has a lucky run, not an edge.",
        "",
    ]
    for window, reps in reports.items():
        lines += [f"## Window: {window}", ""]
        if not reps:
            lines += ["_No overlapping settled races in this window._", ""]
            continue
        lines += [
            "| Challenger | Active | Equal n | Overlap | Disagree n | Inc SR | Chal SR | SR edge | Inc ROI | Chal ROI | ROI edge (ex-big) | Only-chal wins | Verdict |",
            "|---|---|---|---|---|---|---|---|---|---|---|---|---|",
        ]
        for r in reps:
            lines.append(
                f"| {r['challenger']} | {r['first_date']}→{r['last_date']} | {r['n_equal']} | "
                f"{r['overlap_pct']}% | {r['disagree_n']} | "
                f"{_n(r['inc']['sr'], '%')} | {_n(r['chal']['sr'], '%')} | {_n(r['sr_edge_pts'])} | "
                f"{_n(r['inc']['roi'], '%')} | {_n(r['chal']['roi'], '%')} | "
                f"{_n(r['roi_edge_ex_bigprice_pts'])} | {r['chal_only_wins']} | **{r['verdict']}** |"
            )
        lines.append("")
        for r in reps:
            lines += [
                f"### {r['challenger']} — {r['verdict']}",
                "",
                f"- Active {r['first_date']} → {r['last_date']}.",
                f"- Agrees with {incumbent} in **{r['agree_n']}/{r['n_equal']}** races "
                f"(**{r['overlap_pct']}%**, agree-cohort SR {_n(r['agree_sr'], '%')}). "
                "That cohort is shared and carries no independent evidence.",
                f"- Independent evidence: **{r['disagree_n']} races**. "
                f"{incumbent} {r['inc']['wins']}/{r['disagree_n']} ({_n(r['inc']['sr'], '%')}) · "
                f"{r['challenger']} {r['chal']['wins']}/{r['disagree_n']} ({_n(r['chal']['sr'], '%')}).",
                f"- Winners found only by the challenger: **{r['chal_only_wins']}** · "
                f"only by the incumbent: **{r['inc_only_wins']}**.",
                f"- Flat 1pt on disagreements: incumbent {_n(r['inc']['roi'], '%')} "
                f"(ex-bigprice {_n(r['inc']['roi_ex_bigprice'], '%')}) · "
                f"challenger {_n(r['chal']['roi'], '%')} "
                f"(ex-bigprice {_n(r['chal']['roi_ex_bigprice'], '%')}).",
                "",
            ]
    lines += [
        "## Verdict vocabulary",
        "",
        f"- `REDUNDANT_WITH_INCUMBENT` — agrees ≥ {REDUNDANT_OVERLAP:.0%}; too few independent opinions to matter.",
        f"- `INSUFFICIENT_EVIDENCE` — fewer than {MIN_DISAGREE_N} disagreements.",
        "- `ADDING_EDGE` — beats the incumbent on its own picks by SR **and** ROI **and** ex-bigprice ROI.",
        "- `EDGE_UNPROVEN_BIGPRICE_DEPENDENT` — the ROI edge vanishes once big-priced winners are removed.",
        "- `ADDING_WINS_NOT_ROI` — finds more winners, loses money doing it.",
        "- `SUBTRACTING_VS_INCUMBENT` — worse than the incumbent where it differs.",
        "",
    ]
    return "\n".join(lines)


def write_outputs(reports: dict[str, list[dict]], incumbent: str, run_ts: str,
                  date_span: tuple[str, str]) -> None:
    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")

    ledger_rows = []
    for window, reps in reports.items():
        for r in reps:
            ledger_rows.append({
                "run_ts": run_ts, "window": window,
                "incumbent": incumbent, "challenger": r["challenger"],
                "n_equal": r["n_equal"], "agree_n": r["agree_n"],
                "overlap_pct": r["overlap_pct"], "agree_sr": r["agree_sr"],
                "disagree_n": r["disagree_n"],
                "inc_sr": r["inc"]["sr"], "chal_sr": r["chal"]["sr"],
                "sr_edge_pts": r["sr_edge_pts"],
                "inc_roi": r["inc"]["roi"], "chal_roi": r["chal"]["roi"],
                "roi_edge_pts": r["roi_edge_pts"],
                "inc_roi_ex_bigprice": r["inc"]["roi_ex_bigprice"],
                "chal_roi_ex_bigprice": r["chal"]["roi_ex_bigprice"],
                "roi_edge_ex_bigprice_pts": r["roi_edge_ex_bigprice_pts"],
                "chal_only_wins": r["chal_only_wins"], "inc_only_wins": r["inc_only_wins"],
                "first_date": r["first_date"], "last_date": r["last_date"],
                "verdict": r["verdict"],
            })

    for path in (AUDIT_CSV, RUNS_DIR / f"model_disagreement_audit_{stamp}.csv"):
        with open(path, "w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=LEDGER_COLS)
            w.writeheader()
            w.writerows(ledger_rows)

    md = render_md(reports, incumbent, run_ts, date_span)
    for path in (AUDIT_MD, RUNS_DIR / f"model_disagreement_audit_{stamp}.md"):
        path.write_text(md, encoding="utf-8")

    exists = LEDGER_PATH.exists()
    with open(LEDGER_PATH, "a", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=LEDGER_COLS)
        if not exists:
            w.writeheader()
        w.writerows(ledger_rows)


# ── entrypoint ───────────────────────────────────────────────────────────────

def build_reports(rows: list[dict], incumbent: str, window_days: int) -> dict[str, list[dict]]:
    challengers = sorted({r["model"] for r in rows} - {incumbent})
    windows: dict[str, list[dict]] = {}

    def add(label: str, subset: list[dict]) -> None:
        reps = [c for c in (compare(subset, incumbent, ch) for ch in challengers) if c]
        # Live lanes first: a retired lane must never head the table on old form.
        reps.sort(key=lambda r: (r["verdict"] == "RETIRED_OR_RENAMED",
                                 r["sr_edge_pts"] is None, -(r["sr_edge_pts"] or 0)))
        windows[label] = reps

    add("all-time", rows)
    if window_days > 0 and rows:
        cutoff = (datetime.strptime(max(r["date"] for r in rows), "%Y-%m-%d")
                  - timedelta(days=window_days)).strftime("%Y-%m-%d")
        add(f"last-{window_days}-days (from {cutoff})", [r for r in rows if r["date"] >= cutoff])
    return windows


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--incumbent", default=DEFAULT_INCUMBENT,
                    help=f"Lane every challenger is measured against (default {DEFAULT_INCUMBENT}).")
    ap.add_argument("--window-days", type=int, default=30,
                    help="Also report a trailing window of this many days (0 to disable).")
    ap.add_argument("--since", default=None, help="Ignore scorecard dates before YYYY-MM-DD.")
    args = ap.parse_args()

    rows = load_top_picks(since=args.since)
    if not rows:
        print("[BLOCKED] No settled rank-1 rows found in data/reports/canonical_model_scorecard_*.csv")
        return 1
    if not any(r["model"] == args.incumbent for r in rows):
        print(f"[BLOCKED] Incumbent {args.incumbent} has no settled picks in the loaded scorecards.")
        return 1

    run_ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    span = (min(r["date"] for r in rows), max(r["date"] for r in rows))
    reports = build_reports(rows, args.incumbent, args.window_days)
    write_outputs(reports, args.incumbent, run_ts, span)

    print(f"MODEL_DISAGREEMENT_AUDIT — incumbent {args.incumbent} — {span[0]} → {span[1]}")
    for window, reps in reports.items():
        print(f"\n  [{window}]")
        for r in reps:
            print(f"    {r['challenger']:<32} last {r['last_date']}  "
                  f"overlap {r['overlap_pct']:>5}%  disagree n={r['disagree_n']:<4} "
                  f"SR {_n(r['inc']['sr'])}→{_n(r['chal']['sr'])} "
                  f"(edge {_n(r['sr_edge_pts'])})  {r['verdict']}")
    print(f"\n  Latest: {AUDIT_MD}\n  Ledger: {LEDGER_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
