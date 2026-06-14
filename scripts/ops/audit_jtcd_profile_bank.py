#!/usr/bin/env python3
"""
JTC-D Profile Bank Audit — READ-ONLY, sidecar-only
===================================================
Audits the ~494k-row trainer/jockey course/distance/combo profile bank
(data/features/jtc_d/) and measures join coverage against a real card.

Law: SIDECAR ONLY — no live weight, no score change, no model promotion.
Leakage guard: profiles are lifetime aggregates built from historical
runs; when attached to a race they must be treated as slowly-varying
context, and any future per-date rebuild must exclude same-day results.

Usage:
    PYTHONPATH=. python scripts/ops/audit_jtcd_profile_bank.py --date YYYY-MM-DD

Outputs:
    data/current/jtcd_profile_audit.json
    data/reports/jtcd_profile_audit.md
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
JTCD = ROOT / "data" / "features" / "jtc_d"


def norm(s: str) -> str:
    s = (s or "").strip().lower()
    s = re.sub(r"\s*\((aw|ire|gb|uk|fr)\)\s*$", "", s)  # venue/entity suffixes
    return re.sub(r"\s+", " ", s)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", required=True)
    args = parser.parse_args()

    tables = {}
    for p in sorted(JTCD.glob("*.parquet")):
        df = pd.read_parquet(p)
        tables[p.stem] = df
    profile = {name: {"rows": len(df), "cols": list(df.columns)} for name, df in tables.items()}

    # Card join test — same injection scoring reads.
    inj_candidates = sorted((ROOT / "data" / "racing_post_account_parsed").glob(f"*{args.date}*/racecard_injection.json"))
    coverage = {"status": "NO_CARD"}
    if inj_candidates:
        races = json.loads(inj_candidates[-1].read_text())
        races = races.get("races", races if isinstance(races, list) else [])
        card_tr, card_jk, card_co, pairs = set(), set(), set(), set()
        for r in races:
            card_co.add(norm(r.get("course", "")))
            for h in r.get("runners", []) or r.get("horses", []):
                t, j = norm(h.get("trainer", "")), norm(h.get("jockey", ""))
                if t:
                    card_tr.add(t)
                if j:
                    card_jk.add(j)
                if t and j:
                    pairs.add((t, j))
        tc = tables["trainer_course_profile"]
        jc = tables["jockey_course_profile"]
        tjp = tables["trainer_jockey_profile"]
        prof_tr = {norm(x) for x in tc["trainer"].unique()}
        prof_jk = {norm(x) for x in jc["jockey"].unique()}
        prof_co = {norm(x) for x in tc["course"].unique()}
        tj_pairs = {(norm(a), norm(b)) for a, b in zip(tjp["trainer"], tjp["jockey"])}
        coverage = {
            "card_date": args.date,
            "trainers": f"{len(card_tr & prof_tr)}/{len(card_tr)}",
            "jockeys": f"{len(card_jk & prof_jk)}/{len(card_jk)}",
            "courses": f"{len(card_co & prof_co)}/{len(card_co)}",
            "trainer_jockey_pairs": f"{len(pairs & tj_pairs)}/{len(pairs)}",
            "unmatched_courses": sorted(card_co - prof_co),
        }

    # Status verdict
    status = "JTC_D_PARTIAL"
    if coverage.get("status") == "NO_CARD":
        status = "JTC_D_AVAILABLE_UNTESTED"
    blockers_resolved = {
        "course_id_mapping": "MOOT — profiles key on names, not IDs; '(AW)' suffix handled by normalizer",
        "dist_f_format": "dist_band strings in profiles; map card dist_f to bands at attach time",
        "leakage": "lifetime aggregates; per-date rebuild must lag by one day (guard documented)",
        "min_sample": "use confidence column (already computed) — suppress n<10 joins",
    }

    out = {
        "generated_at": datetime.now(UTC).isoformat(),
        "read_only_confirmed": True,
        "sidecar_only": True,
        "tables": profile,
        "total_rows": int(sum(len(d) for d in tables.values())),
        "card_join_coverage": coverage,
        "blockers": blockers_resolved,
        "status": status,
    }
    (ROOT / "data/current/jtcd_profile_audit.json").write_text(json.dumps(out, indent=2))
    lines = [f"# JTC-D Profile Bank Audit — {args.date}", "",
             f"**Status: {status}** · {out['total_rows']:,} profile rows · generated {out['generated_at']}", "",
             f"Coverage on card: trainers {coverage.get('trainers')} · jockeys {coverage.get('jockeys')} · "
             f"courses {coverage.get('courses')} · combos {coverage.get('trainer_jockey_pairs')}", "",
             "Blockers:", *[f"- {k}: {v}" for k, v in blockers_resolved.items()],
             "", "SIDECAR ONLY — no live weight, no score change."]
    (ROOT / "data/reports/jtcd_profile_audit.md").write_text("\n".join(lines))
    print(f"JTC-D audit: {status} | rows={out['total_rows']:,} | coverage={coverage}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
