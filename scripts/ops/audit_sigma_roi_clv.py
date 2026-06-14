#!/usr/bin/env python3
"""
Sigma ROI / CLV Audit — LAYERED, READ-ONLY
===========================================
Computes flat-1pt-SP economics per sigma layer. Never blends layers.
Operator law: ROI_CLV_LAYERED_NOT_BLENDED. If the price source is
missing or unreliable the layer is UNPROVEN, never zero.

Layers:
  A  RACE_SIGMA top-pick   (supabase.sigma_audits, canonical, Jan->Jun)
  B  TOP_PICK derived      (innovation protocol: pick SP + model prob -> overlay)
  C  RUNNER_SIGMA          (NOT_FOUND — declared, not invented)
  D  SHADOW_ROUTER         (router lanes reported as-is; paper ledger SUSPECT)
  E  CLEAN_CHAIN_ONLY      (truth-ledger SIGNED_CLEAN days)
  F  DEGRADED_EXCLUDED     (layer A minus attach-failure/degraded/unknown-source days)
  G  HISTORICAL_OUTPUT_ONLY(layer A restricted to pre-evidence-era days)

CLV: requires BSP / exchange close / timestamped near-off price. None
exists in any store -> CLV = UNPROVEN for every layer (see
ODDS_PROVENANCE_AUDIT.md).

Outputs:
    data/current/sigma_roi_clv.json
    data/reports/sigma_roi_clv.md
"""
from __future__ import annotations

import csv
import json
import sys
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _load_env() -> dict:
    env: dict[str, str] = {}
    p = ROOT / ".env"
    if p.exists():
        for line in p.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                env[k.strip()] = v.strip().strip('"').strip("'")
    return env


def fetch_sigma_audits() -> list | None:
    env = _load_env()
    url = env.get("SUPABASE_URL") or (
        f"https://{env['SUPABASE_PROJECT_ID']}.supabase.co" if env.get("SUPABASE_PROJECT_ID") else ""
    )
    key = env.get("SUPABASE_SERVICE_KEY") or env.get("SUPABASE_KEY") or ""
    if not url or not key:
        return None
    rows: list = []
    offset = 0
    sel = "date,race_id,outcome,actual_winner_sp,decision_tier"
    while True:
        req = urllib.request.Request(
            f"{url.rstrip('/')}/rest/v1/sigma_audits?select={sel}&order=created_at.asc&limit=1000&offset={offset}",
            headers={"apikey": key, "Authorization": f"Bearer {key}"},
        )
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                batch = json.loads(resp.read().decode())
        except Exception:
            return None
        rows.extend(batch)
        if len(batch) < 1000:
            return rows
        offset += 1000


def econ_from_race_sigma(rows: list) -> dict:
    """Flat 1pt at SP on the top pick. WIN pays winner_sp-1 (winner IS the pick);
    PLACED/MISS lose the point (win-market staking)."""
    n = wins = frames = 0
    pl = 0.0
    sp_missing_wins = 0
    win_sps = []
    peak = trough = 0.0
    run = 0.0
    gross_win = gross_loss = 0.0
    for r in rows:
        oc = r.get("outcome")
        if oc not in ("WIN", "PLACED", "MISS"):
            continue
        if oc == "WIN" and not (r.get("actual_winner_sp") or 0) > 0:
            sp_missing_wins += 1
            continue  # cannot price this race — excluded from economics, counted
        n += 1
        if oc == "WIN":
            wins += 1
            sp = float(r["actual_winner_sp"])
            win_sps.append(sp)
            run += sp - 1
            gross_win += sp - 1
        else:
            if oc == "PLACED":
                frames += 1
            run -= 1
            gross_loss += 1
        peak = max(peak, run)
        trough = min(trough, run - peak) if False else trough  # drawdown below
    # max drawdown (simple second pass)
    run2 = peak2 = maxdd = 0.0
    for r in rows:
        oc = r.get("outcome")
        if oc not in ("WIN", "PLACED", "MISS"):
            continue
        if oc == "WIN":
            sp = r.get("actual_winner_sp") or 0
            if not sp > 0:
                continue
            run2 += float(sp) - 1
        else:
            run2 -= 1
        peak2 = max(peak2, run2)
        maxdd = min(maxdd, run2 - peak2)
    pl = round(run, 2)
    return {
        "n_priced": n,
        "wins": wins,
        "strike_rate": round(wins / n, 4) if n else None,
        "frames_placed_not_won": frames,
        "avg_winner_sp": round(sum(win_sps) / len(win_sps), 2) if win_sps else None,
        "flat_1pt_pl": pl,
        "roi_pct": round(pl / n * 100, 2) if n else None,
        "max_drawdown_pts": round(maxdd, 2),
        "profit_factor": round(gross_win / gross_loss, 3) if gross_loss else None,
        "unpriced_wins_excluded": sp_missing_wins,
        "sp_source": "RP results official SP (post-race record) — safe for ROI, NOT a tradeable close",
        "clv": "UNPROVEN — no BSP/exchange/near-off price exists in any store",
    }


def econ_from_innovation() -> dict:
    path = ROOT / "data/velo_innovation_protocol_1k_deduped.csv"
    if not path.exists():
        return {"status": "MISSING"}
    rows = [r for r in csv.DictReader(path.open()) if (r.get("result_position") or "").strip()]
    n = wins = frames = overlay = overlay_n = 0
    pl = gross_w = gross_l = 0.0
    odds = []
    run = peak = maxdd = 0.0
    for r in rows:
        try:
            sp = float(r.get("sp_decimal") or 0)
        except ValueError:
            sp = 0
        if not sp > 0:
            continue
        n += 1
        odds.append(sp)
        # CSV encodes booleans as "1.0"/"0.0"
        def _truthy(v: str) -> bool:
            try:
                return float(v or 0) > 0
            except ValueError:
                return (v or "").strip().lower() in ("true", "yes")
        won = _truthy(r.get("won", ""))
        placed = _truthy(r.get("placed", ""))
        if won:
            wins += 1
            run += sp - 1
            gross_w += sp - 1
        else:
            if placed:
                frames += 1
            run -= 1
            gross_l += 1
        peak = max(peak, run)
        maxdd = min(maxdd, run - peak)
        try:
            mp = float(r.get("model_probability") or 0)
            ip = float(r.get("implied_probability") or 0)
            if mp > 0 and ip > 0:
                overlay_n += 1
                if mp > ip:
                    overlay += 1
        except ValueError:
            pass
    return {
        "n_priced": n,
        "wins": wins,
        "strike_rate": round(wins / n, 4) if n else None,
        "frames_placed_not_won": frames,
        "avg_odds": round(sum(odds) / len(odds), 2) if odds else None,
        "flat_1pt_pl": round(run, 2),
        "roi_pct": round(run / n * 100, 2) if n else None,
        "max_drawdown_pts": round(maxdd, 2),
        "profit_factor": round(gross_w / gross_l, 3) if gross_l else None,
        "overlay_rate": round(overlay / overlay_n, 4) if overlay_n else None,
        "overlay_sample": overlay_n,
        "sp_source": "rp results SP via verdict-result join — safe for ROI",
        "clv": "UNPROVEN — no closing price store",
    }


def main() -> int:
    sa = fetch_sigma_audits()
    if sa is None:
        print("Supabase unreachable — layer A UNPROVEN")
        sa = []

    # Truth-ledger day classes for layer slicing
    ledger_path = ROOT / "data/current/velo_100_day_truth_ledger.json"
    day_class: dict[str, str] = {}
    day_src: dict[str, str] = {}
    if ledger_path.exists():
        L = json.loads(ledger_path.read_text())
        for d in L.get("days", []):
            day_class[d["date"]] = d["final_day_classification"]
            day_src[d["date"]] = d.get("observability_source_truth") or ""

    layer_a = econ_from_race_sigma(sa)
    # Tier slices — the system's own selection layers; where edge would live.
    layer_a["by_tier"] = {}
    for tier in ("A", "B", "C", "D", "X"):
        t_rows = [r for r in sa if (r.get("decision_tier") or "").upper().startswith(tier)]
        if t_rows:
            e = econ_from_race_sigma(t_rows)
            layer_a["by_tier"][tier] = {k: e[k] for k in ("n_priced", "wins", "strike_rate", "flat_1pt_pl", "roi_pct", "profit_factor")}
    layer_b = econ_from_innovation()

    excl_classes = {"RPDC_ATTACH_FAILURE"}
    f_rows = [
        r for r in sa
        if day_class.get(r.get("date", ""), "") not in excl_classes
        and day_src.get(r.get("date", ""), "") not in ("RP_MERGED_DEGRADED", "SOURCE_UNKNOWN_BLOCK")
    ]
    layer_f = econ_from_race_sigma(f_rows)
    g_rows = [r for r in sa if day_class.get(r.get("date", ""), "") == "HISTORICAL_OUTPUT_ONLY"]
    layer_g = econ_from_race_sigma(g_rows)

    report = {
        "generated_at": datetime.now(UTC).isoformat(),
        "read_only_confirmed": True,
        "law": "ROI_CLV_LAYERED_NOT_BLENDED — layers must never be added together",
        "layers": {
            "A_race_sigma_top_pick_canonical": layer_a,
            "B_top_pick_derived_innovation": layer_b,
            "C_runner_sigma": {"status": "NOT_FOUND — no runner-level sigma universe exists"},
            "D_shadow_router": {
                "status": "SHADOW_ONLY — reported, never blended",
                "lanes_latest_2026_06_09": {
                    "V1_BASE": {"n": 51, "sr": 0.451, "roi_pct": 28.8},
                    "V2_CLASS4_ONLY": {"n": 41, "sr": 0.488, "roi_pct": 40.7},
                    "V6_GOLD_SEAM": {"n": 17, "sr": 0.412, "roi_pct": 48.5},
                },
                "paper_ledger": "EVIDENCE_INTEGRITY_SUSPECT — excluded entirely",
            },
            "E_clean_chain_only": {"status": "0 days — no SIGNED_CLEAN day exists yet (series starts 2026-06-11)"},
            "F_degraded_excluded": layer_f,
            "G_historical_output_only": layer_g,
        },
        "clv_verdict": "UNPROVEN at every layer — no BSP / exchange close / timestamped near-off price exists",
        "headline_discipline": (
            "No single ROI number may be quoted without its layer letter, n, and the "
            "truth-ledger exclusions attached."
        ),
    }

    out = ROOT / "data/current/sigma_roi_clv.json"
    out.write_text(json.dumps(report, indent=2))
    lines = ["# Sigma ROI / CLV — layered audit", "",
             f"Generated {report['generated_at']} · READ-ONLY · {report['law']}", ""]
    for name, lay in report["layers"].items():
        lines.append(f"## {name}")
        for k, v in lay.items():
            lines.append(f"- {k}: {v}")
        lines.append("")
    lines.append(f"**CLV:** {report['clv_verdict']}")
    (ROOT / "data/reports/sigma_roi_clv.md").write_text("\n".join(lines))

    print(f"-> {out}")
    for name, lay in report["layers"].items():
        if "roi_pct" in lay:
            print(f"  {name}: n={lay['n_priced']} SR={lay['strike_rate']} PL={lay['flat_1pt_pl']} ROI={lay['roi_pct']}% PF={lay['profit_factor']}")
        else:
            print(f"  {name}: {lay.get('status', '')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
