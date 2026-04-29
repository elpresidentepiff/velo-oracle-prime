from __future__ import annotations

import glob
import json
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
CANDIDATE_JSON = ROOT / "data" / "velo_candidate_lane_design_v1.json"
SPECIAL_DAY_JSON = ROOT / "data" / "evidence_vault" / "special_days" / "velo_special_day_2026-04-28.json"
OUT_JSON = ROOT / "data" / "telegram_signal_attribution_preview_v1.json"
OUT_MD = ROOT / "data" / "telegram_signal_attribution_preview_v1.md"
OUT_DOC = ROOT / "docs" / "evidence" / "VELO_TELEGRAM_SIGNAL_ATTRIBUTION_PREVIEW_V1.md"


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def _json(path: Path) -> dict:
    return json.loads(_text(path))


def _verdict_index() -> dict[str, dict]:
    index: dict[str, dict] = {}
    for path_str in glob.glob(str(ROOT / "data" / "velo_prime_verdicts_*.json")):
        path = Path(path_str)
        try:
            verdicts = json.loads(_text(path))
        except Exception:
            continue
        for verdict in verdicts:
            race_id = verdict.get("race_id")
            if race_id:
                index[race_id] = verdict
    return index


def _fmt_pct(value: float | int | None) -> str:
    if value is None:
        return "UNKNOWN"
    return f"{value}%"


def _lane_catalog() -> dict[str, dict]:
    data = _json(CANDIDATE_JSON)
    return {lane["lane_id"]: lane for lane in data["lanes"]}


def _find_actual_strong_example(verdict_index: dict[str, dict]) -> dict | None:
    for verdict in verdict_index.values():
        top = verdict.get("top") or {}
        vp = float(top.get("velo_prime_prob") or 0)
        tier = verdict.get("tier")
        mds = float(top.get("market_deception_score") or 0)
        improve = float(top.get("improvement_score") or 0)
        place_prob = float(top.get("place_prob") or 0)
        if vp >= 0.30 and tier == "A" and mds <= 0.50 and improve <= 0.40 and place_prob <= 0.80:
            return verdict
    return None


def _badge_block(lane_ids: list[str], lane_catalog: dict[str, dict]) -> list[dict]:
    rows = []
    for lane_id in lane_ids:
        lane = lane_catalog[lane_id]
        evidence = lane.get("evidence", {})
        n_value = evidence.get("n", lane.get("miss_count"))
        sr_value = evidence.get("strike_rate")
        fr_value = evidence.get("frame_rate")
        if lane_id == "MID_PRICE_WINNER_FORENSICS":
            sr_value = "FORENSIC_ONLY"
            fr_value = "FORENSIC_ONLY"
        rows.append(
            {
                "lane_id": lane_id,
                "display_name": lane.get("display_name"),
                "status": lane.get("status"),
                "n": n_value,
                "strike_rate": sr_value,
                "frame_rate": fr_value,
            }
        )
    return rows


def _render_preview(example: dict) -> str:
    lines = [
        f"VÉLØ pick: {example['pick']}",
        f"VP: {example['vp']}",
        f"Tier: {example['tier']}",
        f"Course/Time: {example['course']} {example['off_time']}",
        "",
        "Lane badges triggered:",
    ]
    for badge in example["badge_evidence"]:
        sr_text = badge["strike_rate"] if isinstance(badge["strike_rate"], str) else _fmt_pct(badge["strike_rate"])
        fr_text = badge["frame_rate"] if isinstance(badge["frame_rate"], str) else _fmt_pct(badge["frame_rate"])
        lines.append(
            f"- {badge['lane_id']}: n={badge['n']} | SR={sr_text} | "
            f"frame={fr_text} | status={badge['status']}"
        )
    lines.extend(
        [
            "",
            "Sidecar values:",
            f"- market_deception_score: {example['sidecars']['market_deception_score']}",
            f"- improvement_score: {example['sidecars']['improvement_score']}",
            f"- place_prob: {example['sidecars']['place_prob']}",
            "",
            "Risk flags:",
        ]
    )
    if example["risk_flags"]:
        for flag in example["risk_flags"]:
            lines.append(f"- {flag}")
    else:
        lines.append("- none triggered")
    lines.extend(
        [
            "",
            "Operator note:",
            "SHADOW EVIDENCE ONLY — NO STAKING AUTOMATION",
        ]
    )
    return "\n".join(lines)


def main() -> None:
    lane_catalog = _lane_catalog()
    special_day = _json(SPECIAL_DAY_JSON)
    verdict_index = _verdict_index()

    elite_attr = next(
        row
        for row in special_day["V_signal_attribution"]["race_attributions"]
        if row["race_id"] == "rac_11938940"
    )
    elite_verdict = verdict_index[elite_attr["race_id"]]

    warning_attr = next(
        row
        for row in special_day["V_signal_attribution"]["race_attributions"]
        if row.get("suppress_warning")
    )
    warning_verdict = verdict_index[warning_attr["race_id"]]

    forensic_attr = next(
        row
        for row in special_day["V_signal_attribution"]["race_attributions"]
        if "MID_PRICE_WINNER_FORENSICS" in row.get("lanes_fired", []) and not row.get("suppress_warning")
    )
    forensic_verdict = verdict_index[forensic_attr["race_id"]]

    strong_verdict = _find_actual_strong_example(verdict_index)
    if strong_verdict is None:
        strong_example = {
            "example_id": "normal_strong",
            "source": "illustrative_preview_only",
            "pick": "Illustrative Tier A Pick",
            "course": "Sample Course",
            "off_time": "3:00",
            "vp": 0.334,
            "tier": "A",
            "badge_evidence": _badge_block(["VP30_TIER_A"], lane_catalog),
            "sidecars": {
                "market_deception_score": 0.21,
                "improvement_score": 0.17,
                "place_prob": 0.64,
            },
            "risk_flags": [],
        }
    else:
        strong_top = strong_verdict.get("top") or {}
        strong_example = {
            "example_id": "normal_strong",
            "source": "repo_actual",
            "pick": strong_top.get("horse"),
            "course": strong_verdict.get("course"),
            "off_time": strong_verdict.get("off_time"),
            "vp": round(float(strong_top.get("velo_prime_prob") or 0), 3),
            "tier": strong_verdict.get("tier"),
            "badge_evidence": _badge_block(["VP30_TIER_A"], lane_catalog),
            "sidecars": {
                "market_deception_score": round(float(strong_top.get("market_deception_score") or 0), 3),
                "improvement_score": round(float(strong_top.get("improvement_score") or 0), 3),
                "place_prob": round(float(strong_top.get("place_prob") or 0), 3),
            },
            "risk_flags": [],
        }

    elite_top = elite_verdict.get("top") or {}
    warning_top = warning_verdict.get("top") or {}
    forensic_top = forensic_verdict.get("top") or {}

    examples = [
        {
            "example_id": "elite_stack",
            "source": "repo_actual",
            "pick": elite_top.get("horse"),
            "course": elite_verdict.get("course"),
            "off_time": elite_verdict.get("off_time"),
            "vp": round(float(elite_top.get("velo_prime_prob") or 0), 3),
            "tier": elite_verdict.get("tier"),
            "badge_evidence": _badge_block(
                [
                    "VP30_TIER_A",
                    "MARKET_DECEPTION_HIGH",
                    "IMPROVEMENT_SCORE_HIGH",
                ],
                lane_catalog,
            ),
            "sidecars": {
                "market_deception_score": round(float(elite_top.get("market_deception_score") or 0), 3),
                "improvement_score": round(float(elite_top.get("improvement_score") or 0), 3),
                "place_prob": round(float(elite_top.get("place_prob") or 0), 3),
            },
            "risk_flags": ["short-fav override warning (review if winner SP is compressed)"],
        },
        strong_example,
        {
            "example_id": "warning_b_tier_low_vp",
            "source": "repo_actual",
            "pick": warning_top.get("horse"),
            "course": warning_verdict.get("course"),
            "off_time": warning_verdict.get("off_time"),
            "vp": round(float(warning_top.get("velo_prime_prob") or 0), 3),
            "tier": warning_verdict.get("tier"),
            "badge_evidence": _badge_block(["B_TIER_LOW_VP_SUPPRESS"], lane_catalog),
            "sidecars": {
                "market_deception_score": round(float(warning_top.get("market_deception_score") or 0), 3),
                "improvement_score": round(float(warning_top.get("improvement_score") or 0), 3),
                "place_prob": round(float(warning_top.get("place_prob") or 0), 3),
            },
            "risk_flags": [
                "B-tier VP<0.30",
                "VP 0.20-0.30 drag",
                "SP 3.0-8.5 danger zone",
            ],
        },
        {
            "example_id": "forensic_mid_price_risk",
            "source": "repo_actual",
            "pick": forensic_top.get("horse"),
            "course": forensic_verdict.get("course"),
            "off_time": forensic_verdict.get("off_time"),
            "vp": round(float(forensic_top.get("velo_prime_prob") or 0), 3),
            "tier": forensic_verdict.get("tier"),
            "badge_evidence": _badge_block(["MID_PRICE_WINNER_FORENSICS"], lane_catalog),
            "sidecars": {
                "market_deception_score": round(float(forensic_top.get("market_deception_score") or 0), 3),
                "improvement_score": round(float(forensic_top.get("improvement_score") or 0), 3),
                "place_prob": round(float(forensic_top.get("place_prob") or 0), 3),
            },
            "risk_flags": ["SP 3.0-8.5 danger zone"],
        },
    ]

    payload = {
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "status": "preview_only_not_live",
        "examples": examples,
    }
    OUT_JSON.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    lines = [
        "# VELO Telegram Signal Attribution Preview V1",
        "",
        f"Generated: {payload['generated_at']}",
        "",
        "Status: preview only. Not live. Not sent to Telegram.",
        "",
    ]
    for example in examples:
        lines.append(f"## {example['example_id']}")
        lines.append("")
        if example["source"] != "repo_actual":
            lines.append("*Illustrative preview only - no clean single-badge repo example was found in the sampled archive.*")
            lines.append("")
        lines.append("```text")
        lines.append(_render_preview(example))
        lines.append("```")
        lines.append("")

    markdown = "\n".join(lines)
    OUT_MD.write_text(markdown + "\n", encoding="utf-8")
    OUT_DOC.write_text(markdown + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
