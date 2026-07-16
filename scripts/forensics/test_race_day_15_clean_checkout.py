#!/usr/bin/env python3
"""
Clean-checkout regression test for RACE-DAY-15-FROZEN-MODEL-RECOUNT-AND-CONTROL-PLANE-01.

Proves the forensic scripts regenerate identical headline numbers when run
against ONLY the committed evidence bundle, with NO reference to the original
primary repo path, from an arbitrary working directory (P0-24). Run with:

    python3 scripts/forensics/test_race_day_15_clean_checkout.py --repo-root <this-worktree-root>

or with no --repo-root from anywhere, relying on the script's own
self-location (parents[1] of scripts/forensics/).
"""
import argparse
import json
import subprocess
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent


def resolve_root(cli_root):
    return Path(cli_root).resolve() if cli_root else SCRIPT_DIR.parents[1]


def check(name, cond):
    status = "PASS" if cond else "FAIL"
    print(f"[{status}] {name}")
    return cond


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo-root", default=None)
    args = ap.parse_args()
    ROOT = resolve_root(args.repo_root)

    failures = 0

    # 1. No absolute /mnt/c paths anywhere in the forensic scripts themselves.
    for py in (SCRIPT_DIR).glob("race_day_15_*.py"):
        text = py.read_text()
        if not check(f"no hardcoded /mnt/c path in {py.name}", "/mnt/c/" not in text):
            failures += 1

    # 2. Regenerate the recount from the committed evidence bundle only.
    result = subprocess.run(
        [sys.executable, str(SCRIPT_DIR / "race_day_15_frozen_recount.py"), "--repo-root", str(ROOT)],
        capture_output=True, text=True,
    )
    if not check("frozen_recount.py exits 0", result.returncode == 0):
        print(result.stdout, result.stderr)
        failures += 1

    recount_path = ROOT / "data" / "reports" / "race_day_15_frozen_recount.json"
    if not check("race_day_15_frozen_recount.json exists after regeneration", recount_path.exists()):
        failures += 1
        print("Aborting further checks -- no output to validate.")
        sys.exit(1)

    d = json.loads(recount_path.read_text())
    s = d["sections"]

    # 3. 47 immutable morning races.
    failures += 0 if check("47 immutable morning races", s["phase1_morning_manifest"]["race_count"] == 47) else 1

    # 4. Nine Happy Valley post-race exclusions in Old VELO strict view.
    ov = s["phase6_old_velo"]
    ov_excluded = ov["FULL_SNAPSHOT_REPLAY"]["eligible"] + 1 - ov["STRICT_PRE_RACE"]["eligible"]  # +1 for the non-runner counted in FULL but not STRICT denominators differently; verify via direct count instead
    # Direct check: 47 morning races - 38 strict-eligible-or-excluded... use explicit counts.
    failures += 0 if check(
        "Old VELO STRICT_PRE_RACE eligible == 38 (47 - 9 Happy Valley post-race)",
        ov["STRICT_PRE_RACE"]["eligible"] == 38,
    ) else 1

    # 5. Strict Old VELO denominator and result.
    failures += 0 if check(
        "Old VELO STRICT_PRE_RACE == 12/38 (31.6%)",
        ov["STRICT_PRE_RACE"]["wins"] == 12 and ov["STRICT_PRE_RACE"]["eligible"] == 38,
    ) else 1

    # 6. Genuine No-RPR derivation present and distinct from Radical Shadow.
    nr = s["phase6_no_rpr_genuine"]
    failures += 0 if check(
        "No-RPR genuine STRICT_PRE_RACE == 8/33",
        nr["STRICT_PRE_RACE"]["wins"] == 8 and nr["STRICT_PRE_RACE"]["eligible"] == 33,
    ) else 1
    failures += 0 if check("No-RPR tie ledger has 5 entries", len(nr["tie_ledger"]) == 5) else 1

    radical = s["radical_shadow_separate_signal"]
    failures += 0 if check("Radical Shadow labelled RADICAL_SHADOW, not NO_RPR_SHADOW", radical["label"] == "RADICAL_SHADOW") else 1

    # 7. Transcript -> Kalir diff.
    anchor = s["phase2_diff_summary"]["killarney_924613_anchor"]
    failures += 0 if check(
        "924613 anchor: Transcript -> Kalir, Kalir final SP 4.0",
        anchor["morning_pick"] == "Transcript" and anchor["afternoon_pick"] == "Kalir" and anchor["kalir_final_sp_from_results_file"] == 4.0,
    ) else 1

    # 8. New Build / Champion Intent per-race timing present.
    nb = s["phase7_new_build_per_race_timing"]["timing_breakdown"]
    ci = s["phase7_champion_intent_per_race_timing"]["timing_breakdown"]
    failures += 0 if check("New Build has per-race timing breakdown with both statuses present", "POST_RACE_GENERATED" in nb and "AFTERNOON_PRE_RACE_PROVEN" in nb) else 1
    failures += 0 if check("Champion Intent has per-race timing breakdown with both statuses present", "POST_RACE_GENERATED" in ci and "AFTERNOON_PRE_RACE_PROVEN" in ci) else 1

    # 9. Manifest fallback reconstruction proof.
    manifest = s["phase9_manifest_recurrence_v2"]
    failures += 0 if check(
        "Manifest classification is MANIFEST_TRUNCATION_CONFIRMED_RECURRING_ROOT_CAUSE_LOCATED",
        manifest["classification"] == "MANIFEST_TRUNCATION_CONFIRMED_RECURRING_ROOT_CAUSE_LOCATED",
    ) else 1
    failures += 0 if check(
        "Manifest raw HTML total == 49 (40 non-HV + 9 HV) despite 9-entry manifest",
        manifest["raw_html_files_on_disk"]["total"] == 49 and manifest["final_racecard_manifest_final_state"]["captures"] == 9,
    ) else 1

    # 10. Trigger origin classifications.
    trig = s["phase8_trigger_origin_v2"]
    failures += 0 if check(
        "Both trigger origins classified UNPROVEN, not overclaimed",
        trig["morning_run_08_45"]["classification"] == "MORNING_TRIGGER_ORIGIN_UNPROVEN"
        and trig["afternoon_run_14_08"]["classification"] == "AFTERNOON_TRIGGER_ORIGIN_UNPROVEN",
    ) else 1

    print()
    if failures:
        print(f"{failures} check(s) FAILED")
        sys.exit(1)
    print("All checks PASSED.")


if __name__ == "__main__":
    main()
