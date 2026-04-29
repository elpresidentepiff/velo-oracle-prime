from __future__ import annotations

import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
RUN_PRIME = ROOT / "scripts" / "run_prime_today.py"
VERDICT_SAMPLE = ROOT / "data" / "velo_prime_verdicts_2026_04_28.json"
OUT_JSON = ROOT / "data" / "telegram_signal_visibility_audit_v1.json"
OUT_MD = ROOT / "data" / "telegram_signal_visibility_audit_v1.md"
OUT_DOC = ROOT / "docs" / "evidence" / "VELO_TELEGRAM_SIGNAL_VISIBILITY_AUDIT_V1.md"


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def _line_no(path: Path, needle: str) -> int | None:
    for idx, line in enumerate(_text(path).splitlines(), start=1):
        if needle in line:
            return idx
    return None


def _git(cmd: list[str]) -> str:
    return subprocess.check_output(cmd, cwd=ROOT, text=True, encoding="utf-8").strip()


def _answer(value: bool, note: str, proof: list[dict]) -> dict:
    return {
        "answer": "YES" if value else "NO",
        "value": value,
        "note": note,
        "proof": proof,
    }


def main() -> None:
    run_prime_text = _text(RUN_PRIME)
    sample_verdicts = json.loads(_text(VERDICT_SAMPLE))
    sample_top = (sample_verdicts[0] or {}).get("top") or {}
    sample_top_keys = sorted(sample_top.keys())

    branch = _git(["git", "branch", "--show-current"])
    head = _git(["git", "rev-parse", "HEAD"])

    proofs = {
        "build_governed_card": {
            "path": str(RUN_PRIME),
            "line": _line_no(RUN_PRIME, "def build_governed_card("),
        },
        "tier_line": {
            "path": str(RUN_PRIME),
            "line": _line_no(RUN_PRIME, "TIER:        {tier}"),
        },
        "mds_line": {
            "path": str(RUN_PRIME),
            "line": _line_no(RUN_PRIME, "MDS (DECOY): {mds:.4f}"),
        },
        "prob_gap_line": {
            "path": str(RUN_PRIME),
            "line": _line_no(RUN_PRIME, "PROB GAP:    {prob_gap:.4f}"),
        },
        "c_watch_prob": {
            "path": str(RUN_PRIME),
            "line": _line_no(RUN_PRIME, 'lines.append(f"{course} {off}  {primary}\\n  prob {prob:.3f} | gap {gap:.3f} | place {place:.3f}\\n  {r0}")'),
        },
        "step5_live_sender": {
            "path": str(RUN_PRIME),
            "line": _line_no(RUN_PRIME, 'print("\\nSTEP 5: Send to Telegram")'),
        },
        "a_bucket_sender": {
            "path": str(RUN_PRIME),
            "line": _line_no(RUN_PRIME, 'card = build_governed_card(race, top, second, "A", reasons, racecard_source, date_str)'),
        },
        "b_bucket_sender": {
            "path": str(RUN_PRIME),
            "line": _line_no(RUN_PRIME, 'card = build_governed_card(race, top, second, "B", reasons, racecard_source, date_str)'),
        },
    }

    # The current live formatter does not compute any candidate-lane booleans.
    badge_tokens = [
        "VP30_TIER_A",
        "MARKET_DECEPTION_HIGH",
        "IMPROVEMENT_SCORE_HIGH",
        "PLACE_PROB_HIGH",
        "B_TIER_LOW_VP_SUPPRESS",
        "MID_PRICE_WINNER_FORENSICS",
    ]
    badge_presence = {token: (token in run_prime_text) for token in badge_tokens}

    answers = {
        "A_does_current_telegram_output_show_vp": _answer(
            False,
            "The live governed A/B card does not print a dedicated VP line. Only the C-WATCH grouped list prints 'prob', so VP is not consistently surfaced to the operator.",
            [proofs["build_governed_card"], proofs["prob_gap_line"], proofs["c_watch_prob"]],
        ),
        "B_does_current_telegram_output_show_tier": _answer(
            True,
            "Tier is explicitly rendered in the governed card and also implied by the A/B/C/D/X bucketed Telegram flow.",
            [proofs["tier_line"], proofs["step5_live_sender"]],
        ),
        "C_does_current_telegram_output_show_vp30_tier_a_badge": _answer(
            False,
            "The live Telegram sender never computes or renders the VP30_TIER_A badge.",
            [proofs["build_governed_card"], proofs["a_bucket_sender"]],
        ),
        "D_does_current_telegram_output_show_mds_high_badge": _answer(
            False,
            "The live card prints a numeric MDS value but does not promote it to the MDS_HIGH lane badge.",
            [proofs["mds_line"], proofs["build_governed_card"]],
        ),
        "E_does_current_telegram_output_show_improve_high_badge": _answer(
            False,
            "Improvement score is present in the verdict payload but is not rendered in the current Telegram message.",
            [proofs["build_governed_card"], proofs["a_bucket_sender"]],
        ),
        "F_does_current_telegram_output_show_place_prob_high_badge": _answer(
            False,
            "Place probability appears only in the C-WATCH grouped list and is never surfaced as the PLACE_PROB_HIGH badge.",
            [proofs["build_governed_card"], proofs["c_watch_prob"]],
        ),
        "G_does_current_telegram_output_show_b_low_vp_suppress_warning": _answer(
            False,
            "No suppress-zone warning exists in the live day-of Telegram formatter.",
            [proofs["build_governed_card"], proofs["step5_live_sender"]],
        ),
        "H_does_current_telegram_output_show_mid_price_forensics_warning": _answer(
            False,
            "The live formatter does not mention mid-price miss forensics or danger-zone warnings.",
            [proofs["build_governed_card"], proofs["step5_live_sender"]],
        ),
    }

    available_to_formatter = {
        "race_argument": ["course", "off_time", "date", "race_id"],
        "top_argument_keys_sample": sample_top_keys,
        "top_keys_read_by_build_governed_card": [
            "horse",
            "velo_prime_prob (indirectly via prob gap)",
            "market_deception_score",
            "assigned_product",
            "execution_allowed",
            "confidence_level",
        ],
        "top_keys_present_but_not_rendered_in_governed_card": [
            "velo_prime_prob",
            "improvement_score",
            "place_prob",
            "g_shadow_multiplier",
            "horse_state",
            "candidate_execution_allowed",
            "race_archetype",
            "cash_run_flag",
            "setup_run_flag",
            "doctrines_fired",
        ],
    }

    missing_from_live_message = [
        "explicit VP line on governed A/B cards",
        "VP30_TIER_A badge",
        "MDS_HIGH badge",
        "IMPROVE_HIGH badge",
        "PLACE_PROB_HIGH badge",
        "B_LOW_VP suppress warning",
        "MID_PRICE_FORENSICS warning",
        "lane evidence lines (n / SR / frame / status)",
        "shadow-only operator note for signal stack",
    ]

    display_only_patch = {
        "required": True,
        "summary": (
            "Add a display-only signal stack renderer to scripts/run_prime_today.py. "
            "The patch should evaluate lane conditions from existing top-pick fields and append a "
            "shadow-only evidence panel to the governed card without changing routing, ranking, "
            "execution flags, or staking."
        ),
        "missing_code_path": [
            {
                "path": str(RUN_PRIME),
                "line": proofs["build_governed_card"]["line"],
                "gap": "No signal-stack render call inside build_governed_card().",
            },
            {
                "path": str(RUN_PRIME),
                "line": proofs["step5_live_sender"]["line"],
                "gap": "Step 5 sends A/B cards directly with no candidate-lane evaluation pass.",
            },
            {
                "path": str(RUN_PRIME),
                "line": proofs["c_watch_prob"]["line"],
                "gap": "C-WATCH list prints prob/gap/place only; no lane badges or suppress warnings.",
            },
        ],
    }

    audit = {
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "repo_state": {
            "branch": branch,
            "head": head,
        },
        "telegram_live_script": str(RUN_PRIME),
        "formatter": {
            "live_sender_script": str(RUN_PRIME),
            "a_b_formatter": "build_governed_card",
            "c_watch_formatter": "inline grouped list in STEP 5",
            "d_x_formatter": "inline pass list in STEP 5",
        },
        "visibility_answers": answers,
        "I_which_script_sends_telegram_reports": {
            "answer": "scripts/run_prime_today.py",
            "note": "This is the live day-of Telegram sender. scripts/run_results_sigma.py is post-result sigma reporting, not tomorrow's day card pipeline.",
            "proof": [proofs["step5_live_sender"]],
        },
        "J_which_template_or_formatter_builds_the_message": {
            "answer": "build_governed_card() for A/B governed cards, plus inline formatters for C-WATCH and D/X summaries.",
            "proof": [proofs["build_governed_card"], proofs["c_watch_prob"]],
        },
        "K_what_exact_fields_are_available_to_that_formatter": available_to_formatter,
        "L_what_exact_fields_are_missing_from_the_live_operator_message": missing_from_live_message,
        "M_would_tomorrows_telegram_show_the_new_signals_without_code_changes": {
            "answer": "NO",
            "note": "The current live sender does not evaluate or render the candidate-lane badges.",
        },
        "N_if_no_what_display_only_patch_is_required": display_only_patch,
        "badge_tokens_found_in_live_sender_source": badge_presence,
    }

    OUT_JSON.write_text(json.dumps(audit, indent=2), encoding="utf-8")

    lines = [
        "# VELO Telegram Signal Visibility Audit V1",
        "",
        f"Generated: {audit['generated_at']}",
        "",
        "## Verdict",
        "",
        "Current Telegram output does **not** surface the candidate-lane badges.",
        "The live sender shows Tier and MDS, but VP is not consistently rendered and",
        "VP30_TIER_A / MDS_HIGH / IMPROVE_HIGH / PLACE_HIGH / B_LOW_VP / MID_PRICE_FORENSICS",
        "are all absent from the operator-facing message.",
        "",
        "## Yes / No Matrix",
        "",
        "| Check | Answer | Note |",
        "|---|---|---|",
    ]
    for key, item in answers.items():
        label = key.split("_", 1)[1].replace("_", " ")
        lines.append(f"| {label} | {item['answer']} | {item['note']} |")

    lines.extend(
        [
            "",
            "## Live Sender",
            "",
            f"- Script: `{audit['I_which_script_sends_telegram_reports']['answer']}`",
            f"- Formatter: `{audit['J_which_template_or_formatter_builds_the_message']['answer']}`",
            "",
            "## Formatter Fields Currently Rendered",
            "",
            f"- `horse`",
            f"- `tier`",
            f"- `confidence_level`",
            f"- `prob_gap` (derived from `velo_prime_prob`)",
            f"- `market_deception_score`",
            f"- `assigned_product`",
            f"- `execution_allowed`",
            f"- `reasons`",
            "",
            "## Fields Available But Not Surfaced",
            "",
        ]
    )
    for field in available_to_formatter["top_keys_present_but_not_rendered_in_governed_card"]:
        lines.append(f"- `{field}`")

    lines.extend(
        [
            "",
            "## Missing Code Path",
            "",
            "A display-only patch is required in `scripts/run_prime_today.py`.",
            "The missing path is the lack of any signal-stack render call inside the live day-of Telegram flow.",
            "",
            "Patch shape:",
            "- compute lane badges from existing top-pick fields only",
            "- append shadow evidence lines (n / SR / frame / status)",
            "- do not change ranking, routing, candidate execution, or staking",
            "",
            "## Proof References",
            "",
        ]
    )
    for proof_name, proof in proofs.items():
        lines.append(f"- `{proof_name}`: `{proof['path']}:{proof['line']}`")

    markdown = "\n".join(lines) + "\n"
    OUT_MD.write_text(markdown, encoding="utf-8")
    OUT_DOC.write_text(markdown, encoding="utf-8")


if __name__ == "__main__":
    main()
