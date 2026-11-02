"""
LLM Intelligence Brief — DeepSeek-powered operator briefs (shadow only).

Operator-approved 2026-07-29. Two modes:
  --mode suggestions  Morning: reads today's verdicts, midprice shadow picks,
                      sidecar stack and deep-race-agent output; writes an
                      operator suggestion brief.
  --mode eod          Night: reads sigma results, multimodel ledger summary,
                      council verdict, trainer-intent tags and mission control
                      gates; writes a deterministic end-of-day truth report.

HARD LAW (docs/current/CLAUDE.md): this layer is ARCHIVE_CONTEXT_ONLY —
no Supabase writes, no Telegram, no live-scoring effect, no staking authority.
The brief must cite the artifact behind every claim (evidence-first rule).

Config: DEEPSEEK_API_KEY in .env is used by suggestions mode only. Missing key
=> clean SKIPPED_NO_KEY exit 0. EOD mode never calls an LLM: post-race counts,
race identities and product outcomes are rendered directly from artifacts.

Usage:
    PYTHONPATH=. python scripts/ops/run_llm_intel_brief.py --date YYYY-MM-DD --mode suggestions
    PYTHONPATH=. python scripts/ops/run_llm_intel_brief.py --date YYYY-MM-DD --mode eod
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path

import requests
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(str(ROOT / ".env"))

_key = os.getenv("DEEPSEEK_API_KEY", "").strip()
# sk-or-* keys are OpenRouter keys — route there (model slug vendor/model),
# otherwise hit DeepSeek's native API. Both are OpenAI-compatible.
_default_url = (
    "https://openrouter.ai/api/v1/chat/completions"
    if _key.startswith("sk-or-")
    else "https://api.deepseek.com/chat/completions"
)
_default_model = "deepseek/deepseek-v4-pro" if _key.startswith("sk-or-") else "deepseek-chat"
API_URL = os.getenv("DEEPSEEK_API_URL", _default_url)
MODEL = os.getenv("DEEPSEEK_MODEL", _default_model)
OUT_DIR = ROOT / "data" / "reports"

SYSTEM_PROMPT = """You are the VELO intelligence analyst. VELO is an auditable
UK/IRE horse-racing prediction system. You write context-only briefs for its
human operator. Hard rules you must follow:
1. EVIDENCE-FIRST: every claim must name the source artifact it came from
   (the JSON section you were given). Never invent numbers.
2. You have NO staking authority. Never present anything as a betting
   instruction; frame observations as evidence for the operator to weigh.
3. Model rank, policy decision, staking authorisation and race result are
   four distinct facts — never collapse them into one word.
4. Be specific and short. Flag disagreements between models, unusually
   confident picks, and anything that looks like a data-quality problem.
Structure: ## Headline / ## Model Agreement & Divergence / ## Flags /
## Data Quality. Under 600 words."""


def _read_json(path: Path, default=None):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _gather_suggestions(date_str: str, date_tag: str) -> dict:
    """Morning inputs: pre-race only."""
    verdicts = _read_json(ROOT / "data" / f"velo_prime_verdicts_{date_tag}.json", []) or []
    top_picks = [
        {
            "race_id": v.get("race_id"), "course": v.get("course"),
            "off": v.get("off_time"), "tier": v.get("tier"),
            "pick": (v.get("top") or {}).get("horse"),
            "vp": (v.get("signal_stack") or {}).get("vp"),
            "confidence": (v.get("signal_stack") or {}).get("effective_confidence"),
            "badges": (v.get("signal_stack") or {}).get("badges"),
        }
        for v in verdicts
    ]
    mp = _read_json(OUT_DIR / f"midprice_shadow_{date_tag}.json", {}) or {}
    mp_picks = [
        {"race_id": r.get("race_id"), "course": r.get("course"),
         "pick": (r.get("top_pick") or {}).get("horse"),
         "prob": (r.get("top_pick") or {}).get("midprice_prob")}
        for r in mp.get("races", []) if r.get("top_pick")
    ]
    sidecar = _read_json(ROOT / "app" / "static" / "dashboard" / "sidecar_stack_latest.json", {}) or {}
    agent = None
    for suffix in ("v1", "v2"):
        agent = agent or _read_json(OUT_DIR / f"deep_race_agent_v1_{date_tag}_{suffix}.json")
    agent_summary = (agent or {}).get("summary")
    return {
        "artifact_velo_verdicts": top_picks,
        "artifact_midprice_shadow": mp_picks,
        "artifact_sidecar_stack": {"date": sidecar.get("date"), "stacks": sidecar.get("stacks")},
        "artifact_deep_race_agent_summary": agent_summary,
    }


def _gather_eod(date_str: str, date_tag: str) -> dict:
    """Night inputs: results + gates, with a deterministic integrity verdict."""
    sigma = _read_json(ROOT / "data" / "sigma_results" / f"sigma_results_{date_tag}.json", {}) or {}
    sigma_rows = sigma.get("rows") or sigma.get("results") or []
    sigma_slim = {
        "sigma_status": sigma.get("sigma_status"),
        "expected_predictions": sigma.get("expected_predictions"),
        "evaluated_count": sigma.get("evaluated_count"),
        "ew_tracking": sigma.get("ew_tracking") or {},
        "results": [
            {"race_id": r.get("race_id"), "course": r.get("course"),
             "pick": r.get("predicted") or r.get("top_pick"),
             "outcome": r.get("outcome"),
             "assigned_product": r.get("assigned_product"),
             "ew_outcome": r.get("ew_outcome"),
             "winner": r.get("actual_name") or r.get("winner"),
             "winner_sp": r.get("winner_sp")}
            for r in sigma_rows
        ],
    }
    day_rows, cum = [], {}
    ledger = ROOT / "data" / "model_comparison_ledger.csv"
    if ledger.exists():
        with ledger.open(newline="", encoding="utf-8") as handle:
            rows = list(csv.DictReader(handle))
        day_rows = [r for r in rows if r["date"] == date_str]
        for col, name in [
            ("velo_outcome", "old_velo"), ("norpr_outcome", "no_rpr"),
            ("nb_outcome", "new_build_a"), ("nbc_outcome", "lane_c"),
            ("champion_outcome", "champion"), ("mp_outcome", "midprice"),
        ]:
            m = [r for r in rows if r.get(col, "").strip() not in ("", "NO_DATA")]
            if m:
                w = sum(1 for r in m if r[col] == "WIN")
                cum[name] = {"n": len(m), "win_sr_pct": round(100 * w / len(m), 1)}
    council = _read_json(ROOT / "data" / "council_runs" / f"council_run_{date_str}.json", {}) or {}
    notes = _read_json(ROOT / "data" / f"runner_notes_{date_tag}.json", {}) or {}
    mc = _read_json(ROOT / "data" / "mission_control" / f"{date_str}_mission_control.json", {}) or {}
    integrity = _build_eod_integrity(sigma, sigma_rows, day_rows)
    return {
        "artifact_sigma_results": sigma_slim,
        "artifact_ledger_today": day_rows,
        "artifact_ledger_cumulative": cum,
        "artifact_integrity": integrity,
        "artifact_council": {
            "council_verdict": council.get("council_verdict"),
            "summary": council.get("summary"),
        },
        "artifact_trainer_intent_tags": notes.get("trainer_intent"),
        "artifact_mission_control": {
            "source_truth": mc.get("source_truth"),
            "learning_gate_status": mc.get("learning_gate_status"),
            "gate_reasons": mc.get("gate_reasons"),
        },
    }


def _build_eod_integrity(sigma: dict, sigma_rows: list[dict], day_rows: list[dict]) -> dict:
    """Cross-check EOD sources before any prose is presented as truth.

    This deliberately uses race IDs and explicit artifact fields only.  It is
    the guard that the old generative brief lacked: a model can no longer turn
    36 source rows into a reported 38, or silently omit one EW candidate.
    """

    def _ids(rows: list[dict]) -> list[str]:
        return [str(row.get("race_id") or "").strip() for row in rows]

    sigma_ids = _ids(sigma_rows)
    ledger_ids = _ids(day_rows)
    sigma_id_set = {race_id for race_id in sigma_ids if race_id}
    ledger_id_set = {race_id for race_id in ledger_ids if race_id}
    sigma_duplicates = sorted({race_id for race_id in sigma_ids if race_id and sigma_ids.count(race_id) > 1})
    ledger_duplicates = sorted({race_id for race_id in ledger_ids if race_id and ledger_ids.count(race_id) > 1})

    ew_rows = [row for row in day_rows if row.get("velo_assigned_product") == "EW_CANDIDATE"]
    ew_race_ids = [str(row.get("race_id") or "") for row in ew_rows]
    ew_outcomes: dict[str, int] = {}
    for row in ew_rows:
        outcome = (row.get("velo_ew_outcome") or "MISSING").strip() or "MISSING"
        ew_outcomes[outcome] = ew_outcomes.get(outcome, 0) + 1

    missing_pick_ids = [
        str(row.get("race_id") or "")
        for row in day_rows
        if (row.get("velo_top_pick") or "").strip() in ("", "?")
    ]
    model_columns = {
        "old_velo": "velo_outcome",
        "no_rpr": "norpr_outcome",
        "new_build_a": "nb_outcome",
        "champion": "champion_outcome",
        "midprice": "mp_outcome",
        "lane_c": "nbc_outcome",
    }
    model_coverage = {
        model: sum(
            1
            for row in day_rows
            if (row.get(column) or "").strip() not in ("", "NO_DATA")
        )
        for model, column in model_columns.items()
    }
    old_velo_outcomes = {
        outcome: sum(1 for row in day_rows if row.get("velo_outcome") == outcome)
        for outcome in ("WIN", "PLACE", "MISS")
    }

    expected_predictions = sigma.get("expected_predictions")
    evaluated_count = sigma.get("evaluated_count")
    sigma_ew_count = (sigma.get("ew_tracking") or {}).get("ew_candidate_n")
    blocking_reasons: list[str] = []
    if sigma.get("sigma_status") != "PASS":
        blocking_reasons.append(f"SIGMA_STATUS_{sigma.get('sigma_status') or 'MISSING'}")
    if expected_predictions != len(sigma_rows):
        blocking_reasons.append("SIGMA_EXPECTED_COUNT_MISMATCH")
    if evaluated_count != len(sigma_rows):
        blocking_reasons.append("SIGMA_EVALUATED_COUNT_MISMATCH")
    if sigma_id_set != ledger_id_set:
        blocking_reasons.append("SIGMA_LEDGER_RACE_UNIVERSE_MISMATCH")
    if len(sigma_ids) != len(sigma_id_set) or sigma_duplicates:
        blocking_reasons.append("SIGMA_DUPLICATE_OR_MISSING_RACE_ID")
    if len(ledger_ids) != len(ledger_id_set) or ledger_duplicates:
        blocking_reasons.append("LEDGER_DUPLICATE_OR_MISSING_RACE_ID")
    if sigma_ew_count != len(ew_rows):
        blocking_reasons.append("EW_CANDIDATE_COUNT_MISMATCH")
    if missing_pick_ids:
        blocking_reasons.append("VELO_TOP_PICK_IDENTITY_MISSING")

    return {
        "status": "PASS" if not blocking_reasons else "BLOCKED",
        "blocking_reasons": blocking_reasons,
        "sigma_status": sigma.get("sigma_status"),
        "expected_predictions": expected_predictions,
        "evaluated_count": evaluated_count,
        "sigma_row_count": len(sigma_rows),
        "ledger_row_count": len(day_rows),
        "sigma_unique_race_count": len(sigma_id_set),
        "ledger_unique_race_count": len(ledger_id_set),
        "sigma_only_race_ids": sorted(sigma_id_set - ledger_id_set),
        "ledger_only_race_ids": sorted(ledger_id_set - sigma_id_set),
        "sigma_duplicate_race_ids": sigma_duplicates,
        "ledger_duplicate_race_ids": ledger_duplicates,
        "missing_velo_pick_count": len(missing_pick_ids),
        "missing_velo_pick_race_ids": missing_pick_ids,
        "ew_candidate_count": len(ew_rows),
        "ew_candidate_race_ids": ew_race_ids,
        "ew_outcomes": ew_outcomes,
        "model_coverage": model_coverage,
        "old_velo_outcomes": old_velo_outcomes,
    }


def _render_verified_eod(payload: dict) -> str:
    """Render the authoritative EOD brief directly from verified artifacts."""
    integrity = payload["artifact_integrity"]
    ew_ids = ", ".join(integrity["ew_candidate_race_ids"]) or "none"
    reasons = ", ".join(integrity["blocking_reasons"]) or "none"
    coverage = integrity["model_coverage"]
    outcomes = integrity["old_velo_outcomes"]
    ew_outcomes = integrity["ew_outcomes"]

    return "\n".join(
        [
            "## Headline",
            f"EOD artifact integrity: **{integrity['status']}**. This section is deterministic; no LLM generated its facts.",
            "",
            "## Canonical Counts",
            f"- Sigma status: `{integrity['sigma_status']}`.",
            f"- Expected/evaluated/Sigma rows: {integrity['expected_predictions']}/{integrity['evaluated_count']}/{integrity['sigma_row_count']}.",
            f"- Ledger rows/unique races: {integrity['ledger_row_count']}/{integrity['ledger_unique_race_count']}.",
            f"- Old VELO outcomes: WIN {outcomes['WIN']}, PLACE {outcomes['PLACE']}, MISS {outcomes['MISS']}.",
            "",
            "## EW Candidate Truth",
            f"- EW candidates: {integrity['ew_candidate_count']}.",
            f"- Race IDs: {ew_ids}.",
            f"- Outcomes: {json.dumps(ew_outcomes, sort_keys=True)}.",
            "",
            "## Model Data Coverage",
            *[f"- {model}: {count} races." for model, count in coverage.items()],
            "",
            "## Data Quality",
            f"- Missing VELO top-pick names: {integrity['missing_velo_pick_count']}.",
            f"- Sigma-only race IDs: {', '.join(integrity['sigma_only_race_ids']) or 'none'}.",
            f"- Ledger-only race IDs: {', '.join(integrity['ledger_only_race_ids']) or 'none'}.",
            f"- Blocking reasons: {reasons}.",
            "",
            "This report is post-race context only. It has no staking, scoring, promotion, or learning authority.",
        ]
    )


def run_brief(date_str: str, mode: str) -> int:
    date_tag = date_str.replace("-", "_")

    # EOD is a truth report, not a creative-writing task.  Render it directly
    # from Sigma and the canonical comparison ledger so row counts, race IDs,
    # EW candidates, and missing identities cannot be hallucinated or omitted.
    # The LLM remains available for the pre-race suggestions mode only, where
    # its output is explicitly archive-context and non-authoritative.
    if mode == "eod":
        payload_data = _gather_eod(date_str, date_tag)
        integrity = payload_data["artifact_integrity"]
        text = _render_verified_eod(payload_data)
        OUT_DIR.mkdir(parents=True, exist_ok=True)
        md_path = OUT_DIR / f"llm_brief_{mode}_{date_tag}.md"
        md_path.write_text(
            f"# VERIFIED EOD BRIEF — {date_str}\n\n"
            "> trust_policy: DETERMINISTIC_POST_RACE_TRUTH · velo_scoring_allowed: false ·"
            f" stake_authorised: false\n\n{text}\n",
            encoding="utf-8",
        )
        (OUT_DIR / f"llm_brief_{mode}_{date_tag}.json").write_text(
            json.dumps(
                {
                    "generated_at": datetime.now(UTC).isoformat(),
                    "date": date_str,
                    "mode": mode,
                    "model": "deterministic-eod-v1",
                    "usage": {},
                    "trust_policy": "DETERMINISTIC_POST_RACE_TRUTH",
                    "velo_scoring_allowed": False,
                    "stake_authorised": False,
                    "integrity": integrity,
                    "brief_markdown": text,
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        print(f"VERIFIED EOD BRIEF — {date_str} -> {md_path.relative_to(ROOT)}")
        print(f"  integrity: {integrity['status']}")
        print("  DETERMINISTIC_POST_RACE_TRUTH: no LLM, Supabase, Telegram, or scoring effect.")
        return 0 if integrity["status"] == "PASS" else 2

    api_key = os.getenv("DEEPSEEK_API_KEY", "").strip()
    if not api_key:
        print("LLM BRIEF: SKIPPED_NO_KEY — set DEEPSEEK_API_KEY in .env to enable.")
        return 0

    payload_data = _gather_suggestions(date_str, date_tag)
    task = "Write the MORNING SUGGESTIONS brief for the operator from these pre-race artifacts."
    user_msg = f"{task}\nDate: {date_str}\n\nARTIFACTS (JSON):\n{json.dumps(payload_data, default=str)[:60000]}"

    try:
        resp = requests.post(
            API_URL,
            headers={"Authorization": f"Bearer {api_key}"},
            json={
                "model": MODEL,
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_msg},
                ],
                "temperature": 0.3,
                # Reasoning models (deepseek v4 pro) spend tokens thinking
                # before answering — a small cap starves the final answer
                # (observed 2026-07-29: 1600 cap -> content=None).
                "max_tokens": 5000,
            },
            timeout=180,
        )
        resp.raise_for_status()
        body = resp.json()
        msg = body["choices"][0]["message"]
        text = (
            msg.get("content")
            or msg.get("reasoning_content")
            or msg.get("reasoning")
            or ""
        ).strip()
        usage = body.get("usage", {})
        if not text:
            print(f"LLM BRIEF: API_FAILED — empty completion (finish_reason="
                  f"{body['choices'][0].get('finish_reason')!r}); not writing a blank brief.")
            return 1
    except Exception as e:
        print(f"LLM BRIEF: API_FAILED — {e}")
        return 1

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    md_path = OUT_DIR / f"llm_brief_{mode}_{date_tag}.md"
    md_path.write_text(
        f"# LLM {mode.upper()} BRIEF — {date_str}\n\n"
        f"> trust_policy: ARCHIVE_CONTEXT_ONLY_NOT_SCORING · velo_scoring_allowed: false ·"
        f" stake_authorised: false · model: {MODEL}\n\n{text}\n",
        encoding="utf-8",
    )
    (OUT_DIR / f"llm_brief_{mode}_{date_tag}.json").write_text(
        json.dumps(
            {
                "generated_at": datetime.now(UTC).isoformat(),
                "date": date_str,
                "mode": mode,
                "model": MODEL,
                "usage": usage,
                "trust_policy": "ARCHIVE_CONTEXT_ONLY_NOT_SCORING",
                "velo_scoring_allowed": False,
                "stake_authorised": False,
                "brief_markdown": text,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"LLM BRIEF ({mode}) — {date_str} -> {md_path.relative_to(ROOT)}")
    print(f"  tokens: {usage.get('prompt_tokens','?')}+{usage.get('completion_tokens','?')}")
    print("  ARCHIVE_CONTEXT_ONLY: no Supabase, no Telegram, no scoring effect.")
    return 0


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--date", required=True, help="YYYY-MM-DD")
    p.add_argument("--mode", required=True, choices=["suggestions", "eod"])
    args = p.parse_args()
    sys.exit(run_brief(args.date, args.mode))


if __name__ == "__main__":
    main()
