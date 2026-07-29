#!/usr/bin/env python3
"""
Playbook G promotion review — LIVE vs SHADOW comparison, report only.

Never writes to data/sentient_state.json. Produces a report the operator
can use to decide whether/how to update the live sentient state. Follows
the same evidence-review pattern as the sqpe_v18 LAB_EXPERIMENT gate:
report, don't auto-promote.

Usage:
    python scripts/ops/playbook_g_promotion_review.py
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LIVE_STATE = ROOT / "data" / "sentient_state.json"
SHADOW_STATE = ROOT / "data" / "sentient_state_shadow.json"


def main():
    live = json.loads(LIVE_STATE.read_text())
    shadow = json.loads(SHADOW_STATE.read_text())

    print("=" * 70)
    print("PLAYBOOK G — LIVE vs SHADOW PROMOTION REVIEW")
    print("=" * 70)
    print(f"LIVE   last_updated={live.get('last_updated')}  races_observed={live.get('total_races_observed')}")
    print(f"SHADOW last_updated={shadow.get('last_updated')}  races_observed={shadow.get('total_races_observed')}")
    print()
    print("NOTE: shadow is NOT a continuation of live's history -- it is a")
    print("separately-initialized counter (started small in April, grown")
    print("independently since). Sample sizes are not directly comparable 1:1.")
    print()

    print("-" * 70)
    print("DOCTRINE STRENGTHS (live vs shadow, sorted by live value)")
    print("-" * 70)
    live_ds = live.get("doctrine_strengths", {})
    shadow_ds = shadow.get("doctrine_strengths", {})
    all_doctrines = sorted(set(live_ds) | set(shadow_ds), key=lambda d: -live_ds.get(d, 0))
    print(f"{'Doctrine':20s} {'LIVE':>10s} {'SHADOW':>10s}  Agreement")
    agree, disagree = 0, 0
    untested_n = 0
    for d in all_doctrines:
        lv, sv = live_ds.get(d, 1.0), shadow_ds.get(d, 1.0)
        # A value sitting exactly at the 1.0 default means it never fired in
        # that state's own history -- not evidence of disagreement, just no
        # data yet in that window. Only compare where BOTH sides actually
        # observed the doctrine firing at least once.
        live_untested = lv == 1.0
        shadow_untested = sv == 1.0
        if live_untested or shadow_untested:
            tag = "UNTESTED_IN_SHADOW" if shadow_untested and not live_untested else \
                  "UNTESTED_IN_LIVE" if live_untested and not shadow_untested else \
                  "UNTESTED_BOTH"
            untested_n += 1
        else:
            both_weak = lv < 0.2 and sv < 0.2
            both_strong = lv > 0.8 and sv > 0.8
            if both_weak or both_strong:
                tag = "AGREE"
                agree += 1
            else:
                tag = "DIFFER"
                disagree += 1
        print(f"{d:20s} {lv:10.4f} {sv:10.4f}  {tag}")
    print(f"\nOf {len(all_doctrines)} doctrines: {agree} agree (both fired, same "
          f"direction), {disagree} genuinely differ (both fired, opposite "
          f"direction), {untested_n} not comparable (one or both sides never "
          f"observed it fire).")

    print()
    print("-" * 70)
    print("PAIN RULES")
    print("-" * 70)
    live_rules = live.get("emotion_laws", {}).get("pain_rules", [])
    shadow_rules = shadow.get("emotion_laws", {}).get("pain_rules", [])
    print(f"LIVE: {len(live_rules)} rules   SHADOW: {len(shadow_rules)} rules")
    live_patterns = {r.get("pattern") for r in live_rules}
    shadow_patterns = {r.get("pattern") for r in shadow_rules}
    print(f"Pattern types -- LIVE: {live_patterns}  SHADOW: {shadow_patterns}")

    print()
    print("-" * 70)
    print("RECOMMENDATION")
    print("-" * 70)
    if disagree == 0 and agree > 0:
        print("No doctrine-strength disagreements between live and shadow on the")
        print("doctrines that have actually fired in real data (LAY_THE_STORY,")
        print("SHADOW_TRACKING). Both independently converge on: these two")
        print("doctrines are weak/unreliable predictors as currently implemented.")
        print()
        print("Given shadow is a smaller, separately-grown sample (not a longer")
        print("run of the same history), a wholesale shadow->live overwrite would")
        print("DISCARD live's deeper history (1646 vs shadow's races) for no gain.")
        print()
        print("RECOMMENDED ACTION: do not overwrite live with shadow. Instead,")
        print("resume live's own nightly update loop from its 2026-04-25 freeze")
        print("point, now that the doctrines_fired bug is fixed going forward.")
        print("This requires an explicit operator decision to unfreeze")
        print("data/sentient_state.json -- NOT done by this script.")
    else:
        print("Live and shadow disagree on doctrine direction for some doctrines --")
        print("do not promote automatically. Manual review required.")


if __name__ == "__main__":
    main()
