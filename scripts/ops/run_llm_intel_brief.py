"""
LLM Intelligence Brief — DeepSeek-powered operator briefs (shadow only).

Operator-approved 2026-07-29. Two modes:
  --mode suggestions  Morning: reads today's verdicts, midprice shadow picks,
                      sidecar stack and deep-race-agent output; writes an
                      operator suggestion brief.
  --mode eod          Night: reads sigma results, multimodel ledger summary,
                      council verdict, trainer-intent tags and mission control
                      gates; writes an end-of-day truth report.

HARD LAW (docs/current/CLAUDE.md): this layer is ARCHIVE_CONTEXT_ONLY —
no Supabase writes, no Telegram, no live-scoring effect, no staking authority.
The brief must cite the artifact behind every claim (evidence-first rule).

Config: DEEPSEEK_API_KEY in .env. Missing key => clean SKIPPED_NO_KEY exit 0,
so the pipeline wiring is safe before the key exists. API errors exit 1
(both call sites wire this step non-critical).

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
    """Night inputs: results + gates."""
    sigma = _read_json(ROOT / "data" / "sigma_results" / f"sigma_results_{date_tag}.json", {}) or {}
    sigma_slim = {
        "sigma_status": sigma.get("sigma_status"),
        "results": [
            {"race_id": r.get("race_id"), "course": r.get("course"),
             "pick": r.get("top_pick"), "outcome": r.get("outcome"),
             "winner": r.get("winner"), "winner_sp": r.get("winner_sp")}
            for r in (sigma.get("results") or [])
        ],
    }
    day_rows, cum = [], {}
    ledger = ROOT / "data" / "model_comparison_ledger.csv"
    if ledger.exists():
        rows = list(csv.DictReader(open(ledger, encoding="utf-8")))
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
    return {
        "artifact_sigma_results": sigma_slim,
        "artifact_ledger_today": day_rows,
        "artifact_ledger_cumulative": cum,
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


def run_brief(date_str: str, mode: str) -> int:
    api_key = os.getenv("DEEPSEEK_API_KEY", "").strip()
    date_tag = date_str.replace("-", "_")
    if not api_key:
        print("LLM BRIEF: SKIPPED_NO_KEY — set DEEPSEEK_API_KEY in .env to enable.")
        return 0

    payload_data = (
        _gather_suggestions(date_str, date_tag) if mode == "suggestions"
        else _gather_eod(date_str, date_tag)
    )
    task = (
        "Write the MORNING SUGGESTIONS brief for the operator from these pre-race artifacts."
        if mode == "suggestions"
        else "Write the END-OF-DAY truth report for the operator from these post-race artifacts."
    )
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
