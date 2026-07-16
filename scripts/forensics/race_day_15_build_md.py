#!/usr/bin/env python3
import argparse
import csv
import json
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent


def resolve_root(cli_root):
    return Path(cli_root).resolve() if cli_root else SCRIPT_DIR.parents[1]


def tbl(rows, cols, headers):
    lines = ["| " + " | ".join(headers) + " |", "|" + "|".join(["---"] * len(headers)) + "|"]
    for r in rows:
        lines.append("| " + " | ".join(str(r.get(c, "")) for c in cols) + " |")
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo-root", default=None)
    args = ap.parse_args()
    ROOT = resolve_root(args.repo_root)
    OUT = ROOT / "data" / "reports"

    winners = list(csv.DictReader(open(OUT / "race_day_15_four_model_winners.csv")))
    recount = json.load(open(OUT / "race_day_15_frozen_recount.json"))
    s = recount["sections"]

    ov = sorted([r for r in winners if r["model"] == "OLD_VELO"], key=lambda x: x["off_time"])
    nr = sorted([r for r in winners if r["model"] == "NO_RPR_GENUINE"], key=lambda x: x["off_time"])
    nb = sorted([r for r in winners if r["model"] == "NEW_BUILD"], key=lambda x: x["off_time"])
    ci = sorted([r for r in winners if r["model"] == "CHAMPION_INTENT_SHADOW"], key=lambda x: x["off_time"])

    ov_rows = [{"Time": r["off_time"], "Course": r["course"], "Horse": r["predicted_horse"],
                "SP": r["final_sp"], "Tier": r["decision_tier"], "Product": r["product"]} for r in ov]
    nr_rows = [{"Time": r["off_time"], "Course": r["course"], "Horse": r["predicted_horse"],
                "SP": r["final_sp"], "Score": r["prediction_score"]} for r in nr]
    nb_rows_ = [{"Time": r["off_time"], "Course": r["course"], "Horse": r["predicted_horse"],
                 "SP": r["final_sp"], "Lane": r["lane"], "Score": r["prediction_score"]} for r in nb]
    ci_rows_ = [{"Time": r["off_time"], "Course": r["course"], "Horse": r["predicted_horse"],
                 "SP": r["final_sp"], "Score": r["prediction_score"]} for r in ci]

    ov_names = {r["predicted_horse"] for r in ov}
    nr_names = {r["predicted_horse"] for r in nr}
    nb_names = {r["predicted_horse"] for r in nb}
    ci_names = {r["predicted_horse"] for r in ci}
    shared_all4 = ov_names & nr_names & nb_names & ci_names
    unique_ov = ov_names - nr_names - nb_names - ci_names

    ov_strict = s["phase6_old_velo"]["STRICT_PRE_RACE"]
    ov_full = s["phase6_old_velo"]["FULL_SNAPSHOT_REPLAY"]
    nr_strict = s["phase6_no_rpr_genuine"]["STRICT_PRE_RACE"]
    nb_perf = s["phase7_new_build_per_race_timing"]["AFTERNOON_PRE_RACE_PROVEN_performance"]
    ci_perf = s["phase7_champion_intent_per_race_timing"]["AFTERNOON_PRE_RACE_PROVEN_performance"]

    md = f"""# Race Day 15 (2026-07-15) — Four-Model Winners Report (v2, corrected)

**Mission**: RACE-DAY-15-FROZEN-MODEL-RECOUNT-AND-CONTROL-PLANE-01. **Revision v2** — issued after operator REQUEST CHANGES on PR #151 v1. See `race_day_15_frozen_recount.md` for the full correction log (P0-19..P0-24).

**TRUTH LAW APPLIED, CORRECTED**: v1 of this report over-counted Old VÉLØ by including 2 post-race Happy Valley "wins" inside a figure it mislabelled timing-proven, and mislabelled `radical_shadow_2026_07_15.json` as the No-RPR model when it is a distinct decision layer built around Old VÉLØ's own pick. Both defects are fixed in this revision.

## Headline (first page)

| View | Model | Wins | Eligible | Strike rate | Status |
|---|---|---|---|---|---|
| **Strict pre-race** | Old VÉLØ | **{ov_strict['wins']}** | **{ov_strict['eligible']}** | **{ov_strict['strike_rate']*100:.1f}%** | `STRICT_PRE_RACE_PROVEN` — canonical `off_dt_utc` after 08:46:03Z snapshot generation, excludes all 9 Happy Valley races (already run 03:30-07:50 UTC) |
| Full replay (informational only, NOT predictive) | Old VÉLØ | {ov_full['wins']} | {ov_full['eligible']} | {ov_full['strike_rate']*100:.1f}% | `FULL_SNAPSHOT_REPLAY_INCLUDING_POST_RACE` — includes the 9 Happy Valley races; never quote this as a strike rate |
| **Strict pre-race** | No-RPR (genuine, `sqpe_no_rpr_shadow_prob`) | **{nr_strict['wins']}** | **{nr_strict['eligible']}** | **{nr_strict['strike_rate']*100:.1f}%** | `STRICT_PRE_RACE_PROVEN`, 5 races excluded on tied top score (fail-closed) |
| Afternoon pre-race | New Build (Lane A) | {nb_perf['wins']} | {nb_perf['eligible']} | {nb_perf['strike_rate']*100:.1f}% | `AFTERNOON_PRE_RACE_PROVEN` only — generated 14:09:30Z, valid solely for races whose off-time was still ahead of that instant |
| Afternoon pre-race shadow | Champion Intent Shadow | {ci_perf['wins']} | {ci_perf['eligible']} | {ci_perf['strike_rate']*100:.1f}% | `AFTERNOON_PRE_RACE_PROVEN` shadow-only, `velo_scoring_allowed=False` for every row regardless of timing |

Sigma's previously reported 15/46 (32.6%) and this mission's own v1 report's 14/47 remain **both invalid** as Old VÉLØ performance claims — see `race_day_15_frozen_recount.md` Section "Phase 6b" for the Sigma contamination finding (unchanged) and the corrected Phase 6/6b text for why 14/47 was also wrong.

---

## Old VÉLØ winners — STRICT_PRE_RACE_PROVEN (n={len(ov_rows)})

{tbl(ov_rows, ["Time","Course","Horse","SP","Tier","Product"], ["Time","Course","Horse","SP","Tier","Product"])}

## No-RPR winners — genuine, from `sqpe_no_rpr_shadow_prob`, STRICT_PRE_RACE_PROVEN (n={len(nr_rows)})

{tbl(nr_rows, ["Time","Course","Horse","SP","Score"], ["Time","Course","Horse","SP","Score"])}

## New Build winners — Lane A, AFTERNOON_PRE_RACE_PROVEN only (n={len(nb_rows_)})

{tbl(nb_rows_, ["Time","Course","Horse","SP","Lane","Score"], ["Time","Course","Horse","SP","Lane","Score"])}

## Champion Intent winners — shadow, AFTERNOON_PRE_RACE_PROVEN only, velo_scoring_allowed=False (n={len(ci_rows_)})

{tbl(ci_rows_, ["Time","Course","Horse","SP","Score"], ["Time","Course","Horse","SP","Score"])}

---

## Shared and unique winners (compared strictly within each model's own timing-proven population — NOT a like-for-like race-universe comparison, since the four models have different proven denominators: Old VÉLØ/No-RPR = 38/33 pre-race races at 08:46Z; New Build/Champion Intent = 32 pre-race races at ~14:09Z)

- Shared by all four: {', '.join(sorted(shared_all4)) if shared_all4 else 'None'}
- Unique to Old VÉLØ: {', '.join(sorted(unique_ov)) if unique_ov else 'None'}
- Unique to No-RPR: {', '.join(sorted(nr_names - ov_names - nb_names - ci_names)) if (nr_names - ov_names - nb_names - ci_names) else 'None'}
- Unique to New Build: {', '.join(sorted(nb_names - ov_names - nr_names - ci_names)) if (nb_names - ov_names - nr_names - ci_names) else 'None'}
- Unique to Champion Intent: {', '.join(sorted(ci_names - ov_names - nr_names - nb_names)) if (ci_names - ov_names - nr_names - nb_names) else 'None'}

## Excluded / timing-unproven races

See `race_day_15_timing_excluded_races.csv` for the full per-race exclusion ledger (40 rows: 9 Old VÉLØ Happy Valley post-race exclusions + 15 New Build post-race exclusions + 16 Champion Intent post-race exclusions). Old VÉLØ additionally has 0 non-runners in the strict population; No-RPR has 5 races excluded on fail-closed tied top score (`race_day_15_frozen_recount.json`, `phase6_no_rpr_genuine.tie_ledger`).

Full breakdown: `race_day_15_four_model_winners.csv`, `race_day_15_four_model_placed_only.csv`, `race_day_15_four_model_misses.csv`, `race_day_15_non_runners_exclusions.csv`, `race_day_15_timing_excluded_races.csv`, `race_day_15_frozen_recount.json`.
"""
    (OUT / "race_day_15_four_model_winners.md").write_text(md)
    print("wrote", OUT / "race_day_15_four_model_winners.md")


if __name__ == "__main__":
    main()
