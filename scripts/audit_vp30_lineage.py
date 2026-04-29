from __future__ import annotations

import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
OUT_JSON = ROOT / "data" / "vp30_lineage_audit_v1.json"
OUT_MD = ROOT / "data" / "vp30_lineage_audit_v1.md"
OUT_GLOSSARY = ROOT / "docs" / "evidence" / "VELO_SIGNAL_GLOSSARY_V1.md"
OUT_REPORT_JSON = ROOT / "data" / "evidence_vault" / "velo_49_day_signal_discovery_report_v1.json"
OUT_REPORT_MD = ROOT / "docs" / "evidence" / "VELO_49_DAY_SIGNAL_DISCOVERY_REPORT_V1.md"
OUT_GOOGLE_DOC = ROOT / "docs" / "evidence" / "VELO_GOOGLE_DOC_EXPORT_49_DAY_SIGNAL_DISCOVERY.md"

UNIFIED_JSON = ROOT / "data" / "evidence_vault" / "velo_unified_evidence_audit_v1.json"
CANDIDATE_JSON = ROOT / "data" / "velo_candidate_lane_design_v1.json"
SPECIAL_DAY_JSON = ROOT / "data" / "evidence_vault" / "special_days" / "velo_special_day_2026-04-28.json"
TELEGRAM_AUDIT_JSON = ROOT / "data" / "telegram_signal_visibility_audit_v1.json"

VELO_SERVICE = ROOT / "app" / "services" / "velo_prime_service.py"
ENSEMBLE = ROOT / "src" / "intelligence" / "velo_prime_ensemble.py"
BUILD_INNOVATION = ROOT / "scripts" / "build_innovation_protocol.py"
SPECIAL_DAY_SCRIPT = ROOT / "scripts" / "generate_special_day_report.py"
SIGMA_SCRIPT = ROOT / "scripts" / "run_results_sigma.py"
RUN_PRIME = ROOT / "scripts" / "run_prime_today.py"
UNIFIED_SCRIPT = ROOT / "scripts" / "run_velo_unified_evidence_audit.py"


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def _json(path: Path) -> dict:
    return json.loads(_text(path))


def _line_no(path: Path, needle: str) -> int | None:
    for idx, line in enumerate(_text(path).splitlines(), start=1):
        if needle in line:
            return idx
    return None


def _git(cmd: list[str]) -> str:
    return subprocess.check_output(cmd, cwd=ROOT, text=True, encoding="utf-8").strip()


def _proof(path: Path, needle: str) -> dict:
    return {
        "path": str(path),
        "line": _line_no(path, needle),
        "needle": needle,
    }


def _find_band(bands: list[dict], label: str) -> dict:
    for band in bands:
        if band.get("label") == label:
            return band
    return {}


def _find_labeled(items: list[dict], label: str) -> dict:
    for item in items:
        if item.get("label") == label or item.get("signal") == label:
            return item
    return {}


def main() -> None:
    unified = _json(UNIFIED_JSON)
    candidate = _json(CANDIDATE_JSON)
    special_day = _json(SPECIAL_DAY_JSON)
    telegram_audit = _json(TELEGRAM_AUDIT_JSON) if TELEGRAM_AUDIT_JSON.exists() else {}

    summary = unified["summary"]
    vp_analysis = unified["vp_band_analysis"]
    tier_analysis = unified["tier_analysis"]
    sidecar_analysis = unified["sidecar_analysis"]
    miss_profile = unified["miss_class_analysis"]

    band_vp_low = _find_band(vp_analysis["bands"], "VP<0.20")
    band_vp_mid1 = _find_band(vp_analysis["bands"], "VP 0.20-0.30")
    band_vp_mid2 = _find_band(vp_analysis["bands"], "VP 0.30-0.40")
    band_vp_high = _find_band(vp_analysis["bands"], "VP>=0.40")
    vp30_tier_a = vp_analysis["vp_30_tier_a"]
    suppress = tier_analysis["b_low_vp"]

    lane_lookup = {lane["lane_id"]: lane for lane in candidate["lanes"]}
    mds_lane = lane_lookup["MARKET_DECEPTION_HIGH"]
    improve_lane = lane_lookup["IMPROVEMENT_SCORE_HIGH"]
    place_lane = lane_lookup["PLACE_PROB_HIGH"]
    vp_lane = lane_lookup["VP30_TIER_A"]

    elite_examples = special_day["V_signal_attribution"]["race_attributions"]
    example_lines = [
        {
            "race_id": row.get("race_id"),
            "track": row.get("track"),
            "off_time": row.get("off_time"),
            "vp": row.get("vp"),
            "tier": row.get("tier"),
            "lanes_fired": row.get("lanes_fired"),
        }
        for row in elite_examples[:5]
    ]

    branch = _git(["git", "branch", "--show-current"])
    head = _git(["git", "rev-parse", "HEAD"])

    lineage = {
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "repo_state": {"branch": branch, "head": head},
        "A_what_does_vp_stand_for_in_the_live_pipeline": {
            "answer": "VP is the shorthand used by the audits for velo_prime_prob, the live VELO_PRIME field-level win probability output.",
            "proof": [
                _proof(BUILD_INNOVATION, 'vp = float(top.get("velo_prime_prob") or 0)'),
                _proof(UNIFIED_SCRIPT, '"velo_prime_prob"'),
            ],
        },
        "B_is_vp_the_same_as_velo_prime_prob_or_another_field": {
            "answer": "VP is the same field as velo_prime_prob. It is not sqpe_v17_prob and not a separate verdict-only alias.",
            "proof": [
                _proof(BUILD_INNOVATION, 'vp = float(top.get("velo_prime_prob") or 0)'),
                _proof(SPECIAL_DAY_SCRIPT, '"vp_json": top.get("velo_prime_prob")'),
            ],
        },
        "C_exact_source_field_names": {
            "answer": [
                "velo_prime_prob (live verdict field)",
                "vp_json (special-day loader alias for top.velo_prime_prob)",
                "vp (local audit alias derived from velo_prime_prob)",
            ],
        },
        "D_where_vp_is_calculated": {
            "answer": (
                "score_race_velo_prime() builds runner inputs, VeloPrimeEnsemble.compute() builds the weighted "
                "probability, and VeloPrimeEnsemble.predict_race() race-normalizes it."
            ),
            "proof": [
                _proof(VELO_SERVICE, "def score_race_velo_prime("),
                _proof(ENSEMBLE, 'prob = sum(_WEIGHTS[k] * v for k, v in scores.items()) / total_weight'),
                _proof(ENSEMBLE, "# Re-normalise so race probabilities sum to 1.0"),
            ],
        },
        "E_where_vp_is_written": {
            "answer": "VP is written into the top-pick verdict payload and persisted from run_prime_today into velo_verdicts and local daily verdict JSON files.",
            "proof": [
                _proof(RUN_PRIME, '"velo_prime_prob":    float(top.get("velo_prime_prob", 0)),'),
                _proof(RUN_PRIME, "persist_race_predictions(race, preds, decision_tier=tier)"),
            ],
        },
        "F_where_vp_is_read_by_sigma_audits": {
            "answer": "run_results_sigma.py loads velo_prime_prob directly from velo_verdicts, uses it for calibration summaries, high-confidence cuts, learned patterns, and Telegram sigma reports.",
            "proof": [
                _proof(SIGMA_SCRIPT, '/velo_verdicts?select=race_id,top_rank_horse_id,velo_prime_prob,decision_tier'),
                _proof(SIGMA_SCRIPT, 'high_conf = [r for r in all_matched if r["velo_prime_prob"] >= 0.30]'),
            ],
        },
        "G_where_vp_is_read_by_telegram_reporting": {
            "answer": "run_prime_today.py reads velo_prime_prob to build prob_gap in A/B governed cards and prints prob directly in the C-WATCH grouped Telegram list.",
            "proof": [
                _proof(RUN_PRIME, 'prob_gap = float(top.get("velo_prime_prob", 0)) - float(second.get("velo_prime_prob", 0))'),
                _proof(RUN_PRIME, 'lines.append(f"{course} {off}  {primary}\\n  prob {prob:.3f} | gap {gap:.3f} | place {place:.3f}\\n  {r0}")'),
            ],
        },
        "H_where_vp_is_read_by_evidence_audits": {
            "answer": "The unified evidence audit, special day report generator, and innovation protocol builder all consume velo_prime_prob-derived VP values.",
            "proof": [
                _proof(UNIFIED_SCRIPT, '"vp_json": top.get("velo_prime_prob")'),
                _proof(SPECIAL_DAY_SCRIPT, '"vp_json": top.get("velo_prime_prob")'),
                _proof(BUILD_INNOVATION, 'vp = float(top.get("velo_prime_prob") or 0)'),
            ],
        },
        "I_is_vp_raw_or_calibrated": {
            "answer": "RAW_NORMALIZED_ENSEMBLE_NOT_POSTHOC_CALIBRATED",
            "note": (
                "The live ensemble computes a weighted average, applies macro adjustments, clips, "
                "and then renormalizes across the race. No isotonic, Platt, or temperature scaling "
                "appears in the live scorer path."
            ),
            "proof": [
                _proof(ENSEMBLE, 'prob = sum(_WEIGHTS[k] * v for k, v in scores.items()) / total_weight'),
                _proof(ENSEMBLE, "# Re-normalise so race probabilities sum to 1.0"),
            ],
        },
        "J_is_vp_pre_race_only": {
            "answer": "YES",
            "note": "The live scoring path builds VP from racecard, market, rating, macro, and specialist pre-race fields only.",
            "proof": [
                _proof(ENSEMBLE, "Per D007: all inputs are LIVE-USABLE (pre-race available)."),
                _proof(VELO_SERVICE, 'sp_dec = odds if odds > 1.0 else 10.0'),
            ],
        },
        "K_does_vp_ever_touch_outcome_fields": {
            "answer": "NO_REPO_PROOF_OF_OUTCOME_FIELD_USE_IN_SCORING_PATH",
            "note": "No winner_flag, finish_position, placed_flag, or results ingestion appears in the live score_race_velo_prime -> VeloPrimeEnsemble path.",
            "proof": [
                _proof(VELO_SERVICE, "def _build_live_features("),
                _proof(VELO_SERVICE, "def score_race_velo_prime("),
            ],
        },
        "L_exact_definition_of_vp30": {
            "answer": "velo_prime_prob >= 0.30",
            "proof": [
                _proof(BUILD_INNOVATION, "m_vp30 = vp >= 0.30"),
                _proof(SPECIAL_DAY_SCRIPT, 'vp_30_a = band_stats(non_x[(non_x["vp"] >= 0.30) & (non_x["decision_tier"] == "A")],'),
            ],
        },
        "M_exact_definition_of_vp30_tier_a": {
            "answer": "velo_prime_prob >= 0.30 AND decision_tier == 'A'",
            "proof": [
                _proof(BUILD_INNOVATION, "m_vp30 = vp >= 0.30"),
                _proof(SPECIAL_DAY_SCRIPT, 'if vp >= 0.30 and tier == "A":'),
                _proof(CANDIDATE_JSON, '"condition_plain": "velo_prime_prob >= 0.30 AND decision_tier == \'A\'"'),
            ],
        },
        "N_examples_from_the_49_day_audit": {
            "answer": {
                "vp_bands": [
                    band_vp_low,
                    band_vp_mid1,
                    band_vp_mid2,
                    band_vp_high,
                ],
                "vp30_tier_a": vp30_tier_a,
                "examples": example_lines,
            }
        },
        "O_audit_safe_public_definition": {
            "answer": (
                "VP is the live VELO_PRIME race-normalized win probability field (velo_prime_prob). "
                "VP30 means VP >= 0.30. VP30_TIER_A means VP >= 0.30 and decision_tier A. "
                "These are evidence cohorts, not deployment approvals."
            )
        },
    }

    OUT_JSON.write_text(json.dumps(lineage, indent=2), encoding="utf-8")

    md_lines = [
        "# VELO VP30 Lineage Audit V1",
        "",
        f"Generated: {lineage['generated_at']}",
        "",
        "## Core Verdict",
        "",
        "`VP` in the audit layer is the same field as `velo_prime_prob`.",
        "`VP30` is the explicit threshold `velo_prime_prob >= 0.30`.",
        "`VP30_TIER_A` is `velo_prime_prob >= 0.30 AND decision_tier == 'A'`.",
        "",
        "## Answers",
        "",
    ]
    for key, value in lineage.items():
        if key in {"generated_at", "repo_state"}:
            continue
        label = key.split("_", 1)[1].replace("_", " ")
        answer = value["answer"]
        md_lines.append(f"### {label}")
        if isinstance(answer, dict):
            md_lines.append("")
            md_lines.append("```json")
            md_lines.append(json.dumps(answer, indent=2))
            md_lines.append("```")
        elif isinstance(answer, list):
            md_lines.append("")
            for item in answer:
                md_lines.append(f"- `{item}`")
        else:
            md_lines.append("")
            md_lines.append(str(answer))
        if value.get("note"):
            md_lines.append("")
            md_lines.append(f"Note: {value['note']}")
        if value.get("proof"):
            md_lines.append("")
            md_lines.append("Proof:")
            for proof in value["proof"]:
                md_lines.append(f"- `{proof['path']}:{proof['line']}`")
        md_lines.append("")

    OUT_MD.write_text("\n".join(md_lines) + "\n", encoding="utf-8")

    glossary_lines = [
        "# VELO Signal Glossary V1",
        "",
        "## Core Probability Terms",
        "",
        "- **VP**: shorthand for `velo_prime_prob`, the live VELO_PRIME race-normalized win probability field.",
        "- **VP30**: the evidence cohort where `velo_prime_prob >= 0.30`.",
        "- **VP30_TIER_A**: `velo_prime_prob >= 0.30` and `decision_tier == 'A'`.",
        "- **Tier A**: the highest live decision tier assigned by the daily scorer.",
        "",
        "## Sidecar / Candidate Lane Terms",
        "",
        "- **MDS_HIGH / MARKET_DECEPTION_HIGH**: `market_deception_score > 0.50`.",
        "- **IMPROVE_HIGH / IMPROVEMENT_SCORE_HIGH**: `improvement_score > 0.40`.",
        "- **PLACE_HIGH / PLACE_PROB_HIGH**: `place_prob > 0.80`.",
        "- **B_LOW_VP / B_TIER_LOW_VP_SUPPRESS**: `decision_tier == 'B'` and `velo_prime_prob < 0.30`.",
        "- **MID_PRICE_WINNER_FORENSICS**: misses where the actual winner SP landed in the 3.0-8.5 zone.",
        "",
        "## Public Definition",
        "",
        "These labels are evidence cohorts used for shadow analysis and operator visibility.",
        "They are not auto-execution permissions and not deployment approvals.",
        "",
    ]
    OUT_GLOSSARY.write_text("\n".join(glossary_lines), encoding="utf-8")

    telegram_live = telegram_audit.get("visibility_answers", {})
    telegram_badges_live = {
        "vp30_tier_a_badge": telegram_live.get(
            "C_does_current_telegram_output_show_vp30_tier_a_badge",
            {"answer": "UNKNOWN_NOT_PROVEN"},
        )["answer"],
        "mds_high_badge": telegram_live.get(
            "D_does_current_telegram_output_show_mds_high_badge",
            {"answer": "UNKNOWN_NOT_PROVEN"},
        )["answer"],
        "improve_high_badge": telegram_live.get(
            "E_does_current_telegram_output_show_improve_high_badge",
            {"answer": "UNKNOWN_NOT_PROVEN"},
        )["answer"],
    }

    report_json = {
        "title": "VELO 49-Day Signal Discovery Report — The First Evidence of Signal Compression",
        "generated_at": lineage["generated_at"],
        "executive_summary": {
            "global_sr": summary["E_global_strike_rate"],
            "global_frame": summary["F_global_frame_rate"],
            "vp30_tier_a": {
                "n": vp30_tier_a["n"],
                "strike_rate": vp30_tier_a["strike_rate"],
                "frame_rate": vp30_tier_a["frame_rate"],
            },
            "mds_high": {
                "n": mds_lane["evidence"]["n"],
                "strike_rate": mds_lane["evidence"]["strike_rate"],
                "frame_rate": mds_lane["evidence"]["frame_rate"],
            },
            "improve_high": {
                "n": improve_lane["evidence"]["n"],
                "strike_rate": improve_lane["evidence"]["strike_rate"],
                "frame_rate": improve_lane["evidence"]["frame_rate"],
            },
        },
        "vp_definition": lineage["A_what_does_vp_stand_for_in_the_live_pipeline"]["answer"],
        "vp30_definition": lineage["L_exact_definition_of_vp30"]["answer"],
        "vp30_tier_a_definition": lineage["M_exact_definition_of_vp30_tier_a"]["answer"],
        "operator_visibility": {
            "telegram_badges_live": telegram_badges_live,
            "current_gap": "Operator sees tier/MDS/context but not candidate-lane badges or evidence lines.",
        },
        "signal_metrics": {
            "vp_bands": [band_vp_low, band_vp_mid1, band_vp_mid2, band_vp_high],
            "vp30_tier_a": vp_lane["evidence"],
            "mds_high": mds_lane["evidence"],
            "improve_high": improve_lane["evidence"],
            "place_high": place_lane["evidence"],
            "b_tier_low_vp": {
                "n": suppress["n"],
                "strike_rate": suppress["strike_rate"],
                "frame_rate": suppress["frame_rate"],
            },
            "mid_price_winner_forensics": {
                "sp_3_8_misses": miss_profile["sp_3_8_misses"],
                "pct_of_all_misses": miss_profile["sp_3_8_pct_of_misses"],
            },
        },
        "not_deployment": [
            "candidate lanes are shadow evidence only",
            "operator visibility patch is not live yet",
            "no routing promotion is approved",
            "no staking automation is approved",
        ],
        "next_shadow_step": "candidate_lane_shadow_ledger_dry_run",
    }
    OUT_REPORT_JSON.write_text(json.dumps(report_json, indent=2), encoding="utf-8")

    report_lines = [
        "# VELO 49-Day Signal Discovery Report — The First Evidence of Signal Compression",
        "",
        f"Generated: {lineage['generated_at']}",
        "",
        "## 1. Executive Summary",
        "",
        "VÉLØ is no longer just producing predictions. The 49-day evidence base shows signal compression:",
        "certain internal score combinations are dramatically stronger than the global baseline.",
        "",
        f"- Global 49-day SR = **{summary['E_global_strike_rate']}%**",
        f"- Global 49-day frame = **{summary['F_global_frame_rate']}%**",
        f"- VP>=0.30 + Tier A = **{vp30_tier_a['strike_rate']}% SR / {vp30_tier_a['frame_rate']}% frame / n={vp30_tier_a['n']}**",
        f"- MDS>0.5 = **{mds_lane['evidence']['strike_rate']}% SR / {mds_lane['evidence']['frame_rate']}% frame / n={mds_lane['evidence']['n']}**",
        f"- Improvement score >0.40 = **{improve_lane['evidence']['strike_rate']}% SR / {improve_lane['evidence']['frame_rate']}% frame / n={improve_lane['evidence']['n']}**",
        "",
        "The intelligence is real. The operator visibility layer is still behind it.",
        "",
        "## 2. What We Found",
        "",
        "- VP is monotonic: higher VP bands win and frame more often.",
        "- VP>=0.30 + Tier A is the broadest proven live-quality lane.",
        "- Market deception score >0.50 is the strongest hidden sidecar signal.",
        "- Improvement score >0.40 is a strong underused signal.",
        "- Tier B with VP<0.30 is a confirmed drag zone.",
        "- The main miss battlefield is the SP 3.0-8.5 winner zone.",
        "",
        "## 3. VP30 Definition From Repo Proof",
        "",
        f"- VP = `{lineage['A_what_does_vp_stand_for_in_the_live_pipeline']['answer']}`",
        f"- VP30 = `{lineage['L_exact_definition_of_vp30']['answer']}`",
        f"- VP30_TIER_A = `{lineage['M_exact_definition_of_vp30_tier_a']['answer']}`",
        "",
        "## 4. VP Monotonic Truth",
        "",
        "| Band | n | SR | Frame |",
        "|---|---:|---:|---:|",
        f"| VP<0.20 | {band_vp_low['n']} | {band_vp_low['strike_rate']}% | {band_vp_low['frame_rate']}% |",
        f"| VP 0.20–0.30 | {band_vp_mid1['n']} | {band_vp_mid1['strike_rate']}% | {band_vp_mid1['frame_rate']}% |",
        f"| VP 0.30–0.40 | {band_vp_mid2['n']} | {band_vp_mid2['strike_rate']}% | {band_vp_mid2['frame_rate']}% |",
        f"| VP>=0.40 | {band_vp_high['n']} | {band_vp_high['strike_rate']}% | {band_vp_high['frame_rate']}% |",
        "",
        "The monotonic climb is structural, not cosmetic.",
        "",
        "## 5. VP30_TIER_A Evidence",
        "",
        f"- SR = **{vp_lane['evidence']['strike_rate']}%**",
        f"- Frame = **{vp_lane['evidence']['frame_rate']}%**",
        f"- n = **{vp_lane['evidence']['n']}**",
        "",
        "## 6. MDS_HIGH Evidence",
        "",
        f"- SR = **{mds_lane['evidence']['strike_rate']}%**",
        f"- Frame = **{mds_lane['evidence']['frame_rate']}%**",
        f"- n = **{mds_lane['evidence']['n']}**",
        "",
        "## 7. IMPROVE_HIGH Evidence",
        "",
        f"- SR = **{improve_lane['evidence']['strike_rate']}%**",
        f"- Frame = **{improve_lane['evidence']['frame_rate']}%**",
        f"- n = **{improve_lane['evidence']['n']}**",
        "",
        "## 8. PLACE_PROB_HIGH Evidence",
        "",
        f"- SR = **{place_lane['evidence']['strike_rate']}%**",
        f"- Frame = **{place_lane['evidence']['frame_rate']}%**",
        f"- n = **{place_lane['evidence']['n']}**",
        "",
        "## 9. B_TIER_LOW_VP_SUPPRESS Evidence",
        "",
        f"- SR = **{suppress['strike_rate']}%**",
        f"- Frame = **{suppress['frame_rate']}%**",
        f"- n = **{suppress['n']}**",
        "",
        "## 10. MID_PRICE_WINNER_FORENSICS Evidence",
        "",
        f"- SP 3.0-8.5 winners = **{miss_profile['sp_3_8_misses']} misses**",
        f"- Share of all misses = **{miss_profile['sp_3_8_pct_of_misses']}%**",
        "",
        "## 11. What the Operator Currently Sees",
        "",
        "- Tier buckets and governed A/B cards",
        "- MDS numeric line on governed cards",
        "- Execution state and reasons",
        "- C-WATCH grouped lines with prob/gap/place",
        "",
        "## 12. What the Operator Must See",
        "",
        "- VP as a visible number on every governed card",
        "- candidate lane badges (VP30_TIER_A, MDS_HIGH, IMPROVE_HIGH, PLACE_HIGH)",
        "- suppress warnings (B-tier VP<0.30)",
        "- forensic risk warnings (SP 3.0-8.5 danger zone)",
        "- shadow evidence lines: n, SR, frame, status",
        "",
        "## 13. Whether Telegram Currently Shows It",
        "",
        f"- VP30_TIER_A badge live: **{telegram_badges_live['vp30_tier_a_badge']}**",
        f"- MDS_HIGH badge live: **{telegram_badges_live['mds_high_badge']}**",
        f"- IMPROVE_HIGH badge live: **{telegram_badges_live['improve_high_badge']}**",
        "",
        "Current answer: treat operator visibility as unresolved until the display-only Telegram patch is approved and wired.",
        "",
        "## 14. Why This Is Not Deployment",
        "",
        "- These are shadow evidence cohorts, not promotion approvals.",
        "- No routing change is approved.",
        "- No staking automation is approved.",
        "- The shadow ledger append script is not yet live.",
        "",
        "## 15. Next Shadow-Ledger Step",
        "",
        "`candidate_lane_shadow_ledger_dry_run`",
        "",
        "The dry run must prove that every VP30_TIER_A, MDS_HIGH, IMPROVE_HIGH, PLACE_HIGH,",
        "B_LOW_VP_SUPPRESS, and MID_PRICE_FORENSICS event is captured with correct running SR/frame.",
        "",
        "## 16. Company Meaning",
        "",
        "VÉLØ is no longer just predicting. It is learning which parts of itself are trustworthy.",
        "That is the commercial turn: a racing intelligence system that can expose why a pick is elite,",
        "dangerous, suppressed, or only forensic - and can prove the evidence trail behind each claim.",
        "",
    ]
    report_markdown = "\n".join(report_lines)
    OUT_REPORT_MD.write_text(report_markdown + "\n", encoding="utf-8")
    OUT_GOOGLE_DOC.write_text(report_markdown + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
