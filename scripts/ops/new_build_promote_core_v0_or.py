#!/usr/bin/env python3
"""
new_build_promote_core_v0_or.py
Promote Core V0_OR from challenger to champion.
Reads existing V0_OR metadata, writes champion registry + promotion report.
"""
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

MODEL_DIR    = ROOT / "data" / "new_build" / "models"
RPT_DIR      = ROOT / "data" / "new_build" / "reports"
CHAMPION_DIR = MODEL_DIR / "champion"

V0_OR_DIR  = MODEL_DIR / "core_v0_or"
V0_OR_META = V0_OR_DIR / "core_v0_or_metadata.json"
V0_OR_PKL  = V0_OR_DIR / "core_v0_or_model.pkl"

V0_DIR     = MODEL_DIR / "core_v0"
V0_META    = V0_DIR / "core_v0_metadata.json"


def run():
    print("=== Promote Core V0_OR → Champion ===")

    # Load V0_OR metadata
    meta = json.loads(V0_OR_META.read_text())
    prev_meta = json.loads(V0_META.read_text()) if V0_META.exists() else {}

    # Verify decision
    decision = meta.get("decision", "")
    if decision != "OR_FIX_CONFIRMED_AND_IMPROVES":
        print(f"  WARNING: decision is '{decision}' — expected OR_FIX_CONFIRMED_AND_IMPROVES")
        print("  Proceeding anyway as operator override.")

    champ_metrics = meta["challenger_metrics"]
    prev_metrics  = meta.get("champion_metrics", {})

    print(f"  Previous champion (Core V0): AUC={prev_metrics.get('auc')}  SR={prev_metrics.get('sr'):.1%}  Frame={prev_metrics.get('frame'):.1%}")
    print(f"  New champion (Core V0_OR):   AUC={champ_metrics['auc']}  SR={champ_metrics['sr']:.1%}  Frame={champ_metrics['frame']:.1%}")

    # Build champion registry
    now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    champion = {
        "generated_at": now,
        "champion_name": "core_v0_or",
        "champion_version": "Core_V0_OR",
        "promoted_at": now,
        "promoted_from": "challenger",
        "dethroned_champion": "core_v0",
        "promotion_reason": decision,
        "trust_policy": "ARCHIVE_CONTEXT_ONLY_NOT_SCORING",
        "velo_scoring_allowed": False,
        "rpr_violation": False,
        "sp_violation": False,
        "model_type": meta.get("model_type"),
        "features": meta["features"],
        "metrics": champ_metrics,
        "prior_champion_metrics": prev_metrics,
        "auc_delta": meta.get("auc_delta_vs_champion"),
        "sr_delta": meta.get("sr_delta_vs_champion"),
        "model_pkl": str(V0_OR_PKL.relative_to(ROOT)),
    }

    # Write champion registry
    CHAMPION_DIR.mkdir(parents=True, exist_ok=True)
    registry_path = CHAMPION_DIR / "champion_registry.json"
    registry_path.write_text(json.dumps(champion, indent=2))
    print(f"  Champion registry → {registry_path.relative_to(ROOT)}")

    # Copy pkl to champion dir for convenience
    dst_pkl = CHAMPION_DIR / "champion_model.pkl"
    shutil.copy2(V0_OR_PKL, dst_pkl)
    print(f"  Model copied → {dst_pkl.relative_to(ROOT)}")

    # Write promotion report
    lines = [
        "# Core V0_OR — Promotion Report",
        f"Generated: {now}",
        "",
        "## Decision",
        f"**Core V0_OR is now the champion model.** Promoted from challenger status.",
        "",
        "## Evidence",
        f"| Metric | Previous Champion (Core V0) | New Champion (Core V0_OR) | Delta |",
        f"|---|---|---|---|",
        f"| AUC   | {prev_metrics.get('auc', 'n/a')} | {champ_metrics['auc']} | {meta.get('auc_delta_vs_champion', 0):+.4f} |",
        f"| Brier | {prev_metrics.get('brier', 'n/a')} | {champ_metrics['brier']} | {champ_metrics['brier'] - prev_metrics.get('brier', champ_metrics['brier']):+.4f} |",
        f"| SR    | {prev_metrics.get('sr', 0):.1%} | {champ_metrics['sr']:.1%} | {meta.get('sr_delta_vs_champion', 0):+.1%} |",
        f"| Frame | {prev_metrics.get('frame', 0):.1%} | {champ_metrics['frame']:.1%} | {champ_metrics['frame'] - prev_metrics.get('frame', champ_metrics['frame']):+.1%} |",
        "",
        "## Features Added",
        "- `official_rating` — numeric OR (0 for unrated horses)",
        "- `is_rated` — binary flag (1 if horse has a handicap mark)",
        "",
        "## Rollback",
        "Champion pkl: `data/new_build/models/core_v0/core_v0_model.pkl`",
        "Previous champion features: see `data/new_build/models/core_v0/core_v0_metadata.json`",
        "",
        "## Next",
        "→ Horse Passport challenge (ablation: V0 / V0_OR / Passport-only / V0_OR+Passport)",
    ]
    rpt_path = RPT_DIR / "champion_promotion_latest.md"
    rpt_path.write_text("\n".join(lines))
    print(f"  Promotion report → {rpt_path.relative_to(ROOT)}")

    reg_rpt_path = RPT_DIR / "champion_promotion_latest.json"
    reg_rpt_path.write_text(json.dumps(champion, indent=2))

    print("\n  CHAMPION = Core V0_OR")
    print(f"  AUC={champ_metrics['auc']}  SR={champ_metrics['sr']:.1%}  Frame={champ_metrics['frame']:.1%}  Races={champ_metrics['races']:,}")


if __name__ == "__main__":
    run()
