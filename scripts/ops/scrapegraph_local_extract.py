#!/usr/bin/env python3
"""
VELO ScrapeGraphAI local extraction wrapper.

This wrapper is intentionally not an autonomous scraper. It only accepts a
local source file and requires --execute before any LLM/API call is made.
Use it for uploaded/licensed HTML/text exports, not unauthorized websites.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]


def _load_prompt(args: argparse.Namespace) -> str:
    if args.prompt_file:
        return Path(args.prompt_file).read_text(encoding="utf-8")
    if args.prompt:
        return args.prompt
    raise SystemExit("Provide --prompt or --prompt-file")


def _import_smart_scraper():
    # scrapegraphai 2.1.1 imports ChatOllama from langchain_community, but the
    # modern package exposes it from langchain_ollama. Patch before graph import.
    import langchain_community.chat_models as community_chat_models
    from langchain_ollama import ChatOllama

    if not hasattr(community_chat_models, "ChatOllama"):
        community_chat_models.ChatOllama = ChatOllama

    from scrapegraphai.graphs import SmartScraperGraph

    return SmartScraperGraph


def run_local_extract(
    *,
    source_file: Path,
    prompt: str,
    output_path: Path,
    model: str,
    api_key_env: str,
    execute: bool,
) -> dict[str, Any]:
    source_file = source_file.resolve()
    output_path = output_path.resolve()

    if not source_file.exists():
        raise SystemExit(f"Source file not found: {source_file}")
    if ROOT not in source_file.parents and source_file != ROOT:
        raise SystemExit(f"Source file must live under repo root: {ROOT}")
    if ROOT not in output_path.parents:
        raise SystemExit(f"Output path must live under repo root: {ROOT}")

    dry_payload = {
        "status": "DRY_RUN",
        "source_file": str(source_file),
        "output_path": str(output_path),
        "model": model,
        "api_key_env": api_key_env,
        "prompt_preview": prompt[:500],
        "execute_required": True,
    }
    if not execute:
        return dry_payload

    api_key = os.getenv(api_key_env, "").strip()
    if not api_key:
        raise SystemExit(f"Missing API key env var: {api_key_env}")

    SmartScraperGraph = _import_smart_scraper()
    config = {
        "llm": {
            "model": model,
            "api_key": api_key,
        },
        "verbose": False,
        "headless": True,
    }
    graph = SmartScraperGraph(prompt=prompt, source=str(source_file), config=config)
    result = graph.run()

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    return {
        "status": "PASS",
        "source_file": str(source_file),
        "output_path": str(output_path),
        "model": model,
        "result": result,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Run ScrapeGraphAI against a local VELO source file.")
    parser.add_argument("--source-file", required=True, help="Local HTML/text/markdown file under repo root.")
    parser.add_argument("--prompt", default=None, help="Extraction prompt.")
    parser.add_argument("--prompt-file", default=None, help="Prompt file path.")
    parser.add_argument("--output", required=True, help="Output JSON path under repo root.")
    parser.add_argument("--model", default="openai/gpt-4o-mini", help="ScrapeGraphAI/LangChain model name.")
    parser.add_argument("--api-key-env", default="OPENAI_API_KEY", help="Environment variable containing API key.")
    parser.add_argument("--execute", action="store_true", help="Actually run the LLM extraction.")
    args = parser.parse_args()

    prompt = _load_prompt(args)
    payload = run_local_extract(
        source_file=Path(args.source_file),
        prompt=prompt,
        output_path=Path(args.output),
        model=args.model,
        api_key_env=args.api_key_env,
        execute=args.execute,
    )
    print(json.dumps(payload, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
