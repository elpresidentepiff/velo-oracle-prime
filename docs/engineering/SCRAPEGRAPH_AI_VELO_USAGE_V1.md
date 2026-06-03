# ScrapeGraphAI VELO Usage V1

## Status

ScrapeGraphAI is installed in the local repo venv as optional tooling:

- `scrapegraphai==2.1.1`
- `scrapegraph-py==2.1.0`

It is not part of production scoring, staking, Telegram, Playbook G, or live learning.

## Allowed Use

Use ScrapeGraphAI only for local/licensed extraction:

- local HTML exports
- local text/markdown exports
- uploaded/licensed racecard files converted to text/HTML
- parser fallback audits

Do not use it to bypass website access controls or scrape unauthorized Racing Post pages.

## VELO Role

Recommended role:

`RacingPostAdapter fallback extractor`

When the normal parser misses fields, ScrapeGraphAI can attempt to extract:

- selections
- race times
- runner names
- Spotlight text
- Postdata picks
- Topspeed picks
- RP Ratings picks
- OR/TS/RPR fields when present

Every ScrapeGraphAI-derived output must be marked as fallback extraction and audited before scoring use.

## Local Wrapper

Wrapper:

```bash
python scripts/ops/scrapegraph_local_extract.py \
  --source-file data/some_local_export.html \
  --prompt "Extract race time, horse, Spotlight pick, Postdata pick, Topspeed pick as JSON." \
  --output data/scrapegraph_outputs/example.json
```

By default this is a dry run. To execute an LLM call:

```bash
python scripts/ops/scrapegraph_local_extract.py \
  --source-file data/some_local_export.html \
  --prompt "Extract race time, horse, Spotlight pick, Postdata pick, Topspeed pick as JSON." \
  --output data/scrapegraph_outputs/example.json \
  --execute
```

The wrapper requires `OPENAI_API_KEY` by default. It never prints the key.

## Compatibility Note

`scrapegraphai==2.1.1` currently imports `ChatOllama` from `langchain_community.chat_models`, while the installed LangChain ecosystem exposes it from `langchain_ollama`. The local wrapper applies a small runtime compatibility shim before importing ScrapeGraphAI graphs.

Do not import `scrapegraphai.graphs` directly in production code until this dependency issue is resolved upstream or pinned cleanly.
