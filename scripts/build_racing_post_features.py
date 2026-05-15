"""
Build Racing Post structured features for a given date.
Read-only. No scoring changes. No DB writes.
Output: data/racing_post_features/YYYY-MM-DD.json
"""
import argparse
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.services.racing_post_adapter import build_racing_post_features


def main() -> None:
    parser = argparse.ArgumentParser(description="Build Racing Post structured features")
    parser.add_argument("--date", default=str(date.today()), help="YYYY-MM-DD")
    args = parser.parse_args()

    payload = build_racing_post_features(args.date)
    cov = payload["coverage"]
    print(f"RacingPostAdapter V1 — {args.date}")
    print(f"  Venues:            {cov['venues']}")
    print(f"  Races:             {cov['races']}")
    print(f"  Runners:           {cov['runners']}")
    print(f"  Spotlight present: {cov['spotlight_present']}/{cov['races']}")
    print(f"  Postdata present:  {cov['postdata_present']}/{cov['races']}")
    print(f"  Output:            data/racing_post_features/{args.date}.json")

    # Print high-claim races
    high_claim = [
        r for r in payload["races"]
        if len(r["rp_race_features"]["top_claim_tags"]) >= 2
    ]
    if high_claim:
        print(f"\n  High-claim races ({len(high_claim)}):")
        for r in high_claim[:8]:
            tags = ", ".join(r["rp_race_features"]["top_claim_tags"])
            print(f"    {r['venue']} {r['off_time']} — {tags}")

    # Print consensus picks (postdata + topspeed agree on same horse)
    consensus_picks = []
    for r in payload["races"]:
        pd = (r.get("postdata_pick") or "").strip()
        ts = (r.get("topspeed_pick") or "").strip()
        if pd and ts and pd.upper() == ts.upper():
            consensus_picks.append((r["venue"], r["off_time"], pd))
    if consensus_picks:
        print(f"\n  Postdata+Topspeed consensus ({len(consensus_picks)}):")
        for venue, t, horse in consensus_picks[:10]:
            print(f"    {venue} {t} — {horse}")


if __name__ == "__main__":
    main()
