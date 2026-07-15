#!/usr/bin/env python3
import csv
import json
from pathlib import Path

ROOT = Path("/mnt/c/Users/puror/velo-race-day-15-proof")
OUT = ROOT / "data" / "reports"

winners = list(csv.DictReader(open(OUT / "race_day_15_four_model_winners.csv")))
recount = json.load(open(OUT / "race_day_15_frozen_recount.json"))
s = recount["sections"]

def tbl(rows, cols, headers):
    lines = ["| " + " | ".join(headers) + " |", "|" + "|".join(["---"] * len(headers)) + "|"]
    for r in rows:
        lines.append("| " + " | ".join(str(r.get(c, "")) for c in cols) + " |")
    return "\n".join(lines)

ov = sorted([r for r in winners if r["model"] == "OLD_VELO"], key=lambda x: x["off_time"])
nr = sorted([r for r in winners if r["model"] == "NO_RPR_SHADOW"], key=lambda x: x["off_time"])
nb = sorted([r for r in winners if r["model"] == "NEW_BUILD"], key=lambda x: x["off_time"])
ci = sorted([r for r in winners if r["model"] == "CHAMPION_INTENT_SHADOW"], key=lambda x: x["off_time"])

ov_rows = [{"Time": r["off_time"], "Course": r["course"], "Horse": r["predicted_horse"],
            "Morning odds": r["morning_price"], "SP": r["final_sp"], "Tier": r["decision_tier"],
            "Product": r["product"]} for r in ov]
nr_rows = [{"Time": r["off_time"], "Course": r["course"], "Horse": r["predicted_horse"],
            "Morning odds": r["morning_price"] or "n/a", "SP": r["final_sp"],
            "Score": r["prediction_score"]} for r in nr]
nb_rows = [{"Time": r["off_time"], "Course": r["course"], "Horse": r["predicted_horse"],
            "Morning odds": r["morning_price"] or "n/a", "SP": r["final_sp"],
            "Lane": r["lane"], "Score": r["prediction_score"]} for r in nb]
ci_rows = [{"Time": r["off_time"], "Course": r["course"], "Horse": r["predicted_horse"],
            "Morning odds": r["morning_price"] or "n/a", "SP": r["final_sp"],
            "Score": r["prediction_score"]} for r in ci]

ov_names = {r["predicted_horse"] for r in ov}
nr_names = {r["predicted_horse"] for r in nr}
nb_names = {r["predicted_horse"] for r in nb}
ci_names = {r["predicted_horse"] for r in ci}
shared_all4 = ov_names & nr_names & nb_names & ci_names
unique_ov = ov_names - nr_names - nb_names - ci_names

recount_p6 = s["phase6_old_velo_honest_recount_strict_timing_proven"]
sigma_inv = s["phase6b_sigma_invalidation"]
diff = s["phase2_diff_summary"]

md = f"""# Race Day 15 (2026-07-15) — Four-Model Winners Report

**Mission**: RACE-DAY-15-FROZEN-MODEL-RECOUNT-AND-CONTROL-PLANE-01 (read-only forensic proof, evidence-only)

**TRUTH LAW APPLIED**: every row below is sourced from a genuine pre-race scorecard artifact, cross-checked against the canonical results file (`rp_results_2026_07_15.json`). Old VÉLØ rows are sourced from the immutable, run-scoped morning snapshot (`runner_snapshots_..._1784105122721.jsonl`, created_at 2026-07-15T08:46:03Z) and are classified `MORNING_RUN_PROVEN`. **No-RPR, New Build and Champion Intent have NO run-scoped immutable morning artifact** — they exist only as single mutable files last written in the 14:08-14:09 UTC window, and are therefore classified `MORNING_RUN_UNPROVEN` for every race whose off-time preceded that window. Do not read these three models' rows as proven pre-race predictions without checking the timing-safety column in the full CSV export.

---

## Old VÉLØ winners (MORNING_RUN_PROVEN, n={len(ov_rows)})

{tbl(ov_rows, ["Time","Course","Horse","Morning odds","SP","Tier","Product"], ["Time","Course","Horse","Morning odds","SP","Tier","Product"])}

## No-RPR winners (MORNING_RUN_UNPROVEN — single mutable file, n={len(nr_rows)})

{tbl(nr_rows, ["Time","Course","Horse","Morning odds","SP","Score"], ["Time","Course","Horse","Morning odds","SP","Score"])}

## New Build winners (MORNING_RUN_UNPROVEN — single mutable file, n={len(nb_rows)})

{tbl(nb_rows, ["Time","Course","Horse","Morning odds","SP","Lane","Score"], ["Time","Course","Horse","Morning odds","SP","Lane","Score"])}

## Champion Intent winners (MORNING_RUN_UNPROVEN — single mutable file, n={len(ci_rows)})

{tbl(ci_rows, ["Time","Course","Horse","Morning odds","SP","Score"], ["Time","Course","Horse","Morning odds","SP","Score"])}

---

## Shared winners (found by all four models)

{', '.join(sorted(shared_all4)) if shared_all4 else 'None'}

## Unique winners

- Unique to Old VÉLØ: {', '.join(sorted(unique_ov)) if unique_ov else 'None'}
- Unique to No-RPR: {', '.join(sorted(nr_names - ov_names - nb_names - ci_names)) if (nr_names - ov_names - nb_names - ci_names) else 'None'}
- Unique to New Build: {', '.join(sorted(nb_names - ov_names - nr_names - ci_names)) if (nb_names - ov_names - nr_names - ci_names) else 'None'}
- Unique to Champion Intent: {', '.join(sorted(ci_names - ov_names - nr_names - nb_names)) if (ci_names - ov_names - nr_names - nb_names) else 'None'}

## Total performance (timing-proven basis for Old VÉLØ; operational basis for the other three)

| Model | Winners | Eligible races | Strike rate | Timing-safety basis |
|---|---|---|---|---|
| Old VÉLØ | {recount_p6['wins']} | {recount_p6['eligible_races_scored_pre_race']} | {recount_p6['strike_rate']*100:.1f}% | MORNING_RUN_PROVEN |
| No-RPR Shadow | {len(nr_rows)} | 46 | {len(nr_rows)/46*100:.1f}% | MORNING_RUN_UNPROVEN (single mutable file) |
| New Build | {len(nb_rows)} | 46 | {len(nb_rows)/46*100:.1f}% | MORNING_RUN_UNPROVEN (single mutable file; many picks are `SUPPRESS`/`LOW_DATA`, not live picks) |
| Champion Intent Shadow | {len(ci_rows)} | 45 | {len(ci_rows)/45*100:.1f}% | MORNING_RUN_UNPROVEN (display-only shadow signal, `velo_scoring_allowed=False`) |

**The reported operator figure of Old VÉLØ 15/46 (32.6%) is INVALIDATED.** It was produced by Sigma reading the live, mutable `velo_verdicts` table at 22:28 UTC, over 8 hours after the undocumented 14:08 afternoon rescore silently overwrote every row for all 54 of today's races (upsert-by-`race_id`, no run-scoped key — independently confirmed: 100% of matching rows carry a 14:08 `generated_at`, zero carry 08:46). The Sigma row schema itself contains no `verdict_id`, `doctrine_event_id`, or `pick_sp` field at all, so it cannot even in principle prove which prediction run it evaluated.

**The honest, timing-proven Old VÉLØ result, computed directly from the immutable 08:46 morning snapshot and independently reconciled against the canonical results file, is {recount_p6['honest_figure_string']}.**

The single point of divergence between the honest 14 and the reported 15 is exactly the mandatory regression anchor: race 924613, Killarney 6.30. Morning sealed pick was **Transcript** (VP=0.4087, scoring-time price 1.75) — did not win. The 14:08 afternoon rescore silently changed the pick to **Kalir** (VP=0.4442), which went on to win at SP 4.0. Sigma, reading the overwritten live table at 22:28, credited this as a win for "Old VÉLØ" even though the sealed 08:46 morning prediction was Transcript, not Kalir. This is a manufactured hit, not a genuine morning-run result.

## Excluded / unproven races

- Old VÉLØ: {recount_p6['non_runners']} non-runner, {recount_p6['timing_unproven_or_result_missing']} timing-unproven or result-missing out of 47 morning-scored races.
- No-RPR / New Build / Champion Intent: all {len(nr_rows)+len(nb_rows)+len(ci_rows)} winner-rows above are MORNING_RUN_UNPROVEN by construction — no run-scoped morning artifact exists for these three models on 2026-07-15. Roughly half of today's races (Happy Valley, off-times 11:30-13:30 UTC) had ALREADY RUN before the single surviving 14:09 UTC file for these three models was even generated.

Full breakdown: see `race_day_15_four_model_winners.csv`, `race_day_15_four_model_placed_only.csv`, `race_day_15_four_model_misses.csv`, `race_day_15_non_runners_exclusions.csv`, `race_day_15_frozen_recount.json`.
"""

(OUT / "race_day_15_four_model_winners.md").write_text(md)
print("wrote", OUT / "race_day_15_four_model_winners.md")
