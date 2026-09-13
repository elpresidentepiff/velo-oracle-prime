#!/usr/bin/env python3
"""
run_mds_heavy_shadow_today.py -- MDS-heavy blend shadow lane (operator-approved 2026-09-13).

Re-ranks every runner of the day's already-scored races with a different blend of
the SAME live components, and writes a paper packet. Nothing live changes: no
velo_verdicts write, no weight change, no staking, no Telegram.

  live   : sqpe_v17 0.45 · improvement_score 0.12 · market_deception_score 0.10
  shadow : sqpe_v17 0.10 · improvement_score 0.00 · market_deception_score 0.90

Evidence: docs/research/WEIGHT_STUDY_2026_09_13.md -- rolling out-of-sample
(Jun-Sep, 1,714 races) +0.9 pts win SR, 95% CI [+0.1, +1.8]; ROI not better;
improvement_score took zero weight in every fold. MDS encodes pre-race market
information, so this lane leans toward favourites -- that is the thing to watch.

Blend rules mirror VeloPrimePrediction.compute(): weighted average over the
components present for a runner, a component dropped for the whole race when it
is constant across the field (sqpe never dropped). Macro adjustments and the
per-race renormalisation do not change order and are not reproduced; the
favourite-trap penalty (which can) is not applied, so this is a pure re-weighting.

Promotion gate: >= 300 forward races with results, then an operator decision.
Track with public.canonical_model_scorecards model_name='MDS_HEAVY_SHADOW_V1'.

Usage:
  PYTHONPATH=. python scripts/ops/run_mds_heavy_shadow_today.py --date 2026-09-14
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.velo.verdict_loader import load_verdicts  # noqa: E402

MODEL_VERSION = "MDS_HEAVY_SHADOW_V1"
WEIGHTS = {"sqpe_v17_prob": 0.10, "improvement_score": 0.00, "market_deception_score": 0.90}
LIVE_WEIGHTS = {"sqpe_v17_prob": 0.45, "improvement_score": 0.12, "market_deception_score": 0.10}
NEVER_DROPPED = {"sqpe_v17_prob"}


def _num(v):
    try:
        return float(v) if v is not None else None
    except (TypeError, ValueError):
        return None


def blend(preds: list[dict], weights: dict[str, float]) -> list[float | None]:
    constant = set()
    for k in weights:
        if k in NEVER_DROPPED:
            continue
        vals = [_num(p.get(k)) for p in preds if _num(p.get(k)) is not None]
        if len(vals) >= 2 and max(vals) - min(vals) < 1e-6:
            constant.add(k)
    scores = []
    for p in preds:
        num = den = 0.0
        for k, w in weights.items():
            x = _num(p.get(k))
            if w == 0 or x is None or k in constant:
                continue
            num += w * x
            den += w
        scores.append(num / den if den > 0 else None)
    return scores


def _rank(scores: list[float | None]) -> list[int | None]:
    order = sorted((i for i, s in enumerate(scores) if s is not None), key=lambda i: -scores[i])
    ranks: list[int | None] = [None] * len(scores)
    for r, i in enumerate(order, start=1):
        ranks[i] = r
    return ranks


def main() -> int:
    ap = argparse.ArgumentParser(description="MDS-heavy blend shadow lane (paper only).")
    ap.add_argument("--date", required=True)
    args = ap.parse_args()
    tag = args.date.replace("-", "_")

    try:
        from dotenv import load_dotenv
        load_dotenv(str(ROOT / ".env"))
    except Exception:
        pass

    verdicts, method = load_verdicts(args.date, select="race_id,generated_at,full_analysis")
    # The generated_at fallback returns verdicts WRITTEN that day, which after any
    # rescore includes other days' races (2026-09-13: 12 backfill dates polluted
    # with up to 971 foreign races). A shadow lane built on that is fiction.
    if method != "race_id":
        print(f"[REFUSED] verdict_loader method={method} for {args.date} -- need race_id membership, "
              f"not writing a packet built from the wrong day's verdicts.")
        return 2

    races = []
    agree = 0
    for v in sorted(verdicts, key=lambda r: str(r.get("race_id"))):
        fa = v.get("full_analysis")
        if isinstance(fa, str):
            fa = json.loads(fa)
        preds = [p for p in ((fa or {}).get("predictions") or []) if isinstance(p, dict)]
        if not preds:
            continue
        shadow = blend(preds, WEIGHTS)
        live_vp = [_num(p.get("velo_prime_prob")) for p in preds]
        s_rank, l_rank = _rank(shadow), _rank(live_vp)
        all_scored = sorted(
            ({"horse": p.get("horse"), "horse_id": p.get("horse_id"), "score": None if shadow[i] is None else round(shadow[i], 6),
              "rank": s_rank[i], "live_vp": live_vp[i], "live_rank": l_rank[i],
              "sqpe_v17_prob": _num(p.get("sqpe_v17_prob")), "market_deception_score": _num(p.get("market_deception_score")),
              "improvement_score": _num(p.get("improvement_score")), "odds_decimal": _num(p.get("sp_dec"))}
             for i, p in enumerate(preds)),
            key=lambda r: (r["rank"] is None, r["rank"] or 0),
        )
        top = all_scored[0] if all_scored and all_scored[0]["rank"] == 1 else None
        tied = sum(1 for r in all_scored if r["score"] is not None and top and abs(r["score"] - top["score"]) < 1e-9)
        same = bool(top and top["live_rank"] == 1)
        agree += same
        races.append({
            "race_id": str(v.get("race_id")), "verdict_generated_at": v.get("generated_at"),
            "runners_scored": sum(1 for r in all_scored if r["score"] is not None),
            "top_pick": top, "tie_count_at_top": tied, "agrees_with_live_top_pick": same,
            "all_scored": all_scored,
        })

    packet = {
        "date": args.date,
        "generated_at": datetime.now(UTC).isoformat(),
        "model_version": MODEL_VERSION,
        "weights": WEIGHTS, "live_weights": LIVE_WEIGHTS,
        "trust_policy": "ARCHIVE_CONTEXT_ONLY_NOT_SCORING",
        "velo_scoring_allowed": False, "stake_authorised": False,
        "source": "Supabase velo_verdicts.full_analysis.predictions[]",
        "verdict_load_method": method,
        "evidence": "docs/research/WEIGHT_STUDY_2026_09_13.md",
        "promotion_gate": ">=300 forward races with results in canonical_model_scorecards, then operator decision",
        "race_count": len(races),
        "agrees_with_live_top_pick": agree,
        "races": races,
    }
    out = ROOT / "data" / "reports" / f"mds_heavy_shadow_{tag}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(packet, indent=2), encoding="utf-8")
    print(f"MDS_HEAVY_SHADOW {args.date}: races={len(races)} same_top_pick_as_live={agree} -> {out}")
    return 0 if races else 1


if __name__ == "__main__":
    sys.exit(main())
