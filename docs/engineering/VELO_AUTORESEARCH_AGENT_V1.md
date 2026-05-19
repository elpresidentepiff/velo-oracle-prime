# VÉLØ AUTORESEARCH AGENT V1

**Status:** SPEC — not yet built  
**Purpose:** Scout tools, read GitHub/docs, produce adoption scorecards. Never install without Sentinel approval.

---

## Mission

The AutoResearch Agent is a read-only intelligence layer. It researches tools and frameworks autonomously, produces structured reports, and deposits them into the VÉLØ evidence trail. It never installs packages, never modifies models, and never touches production state.

Its output feeds the Tool Adoption Board (`VELO_TOOL_ADOPTION_BOARD_V1.md`).

---

## Responsibilities

1. **Tool scouting** — Monitor GitHub, arXiv, HuggingFace for tools relevant to VÉLØ domains (tabular ML, SLM, RL, agent orchestration, repo intelligence)
2. **Scorecard production** — Produce structured adoption scorecards for each candidate tool
3. **Benchmark comparison** — Compare tools against VÉLØ's existing stack on historical data
4. **Dependency audit** — Before any install recommendation, run dependency tree analysis
5. **Licence audit** — Flag GPL/AGPL licences (incompatible with VÉLØ's planned product)
6. **Security scan** — Check for known CVEs or recent security incidents

---

## Scorecard Schema

Every tool evaluated gets a scorecard:

```python
{
    "tool": str,
    "github_repo": str,
    "stars": int,
    "licence": str,
    "licence_compatible": bool,        # Apache/MIT/BSD = True; GPL/AGPL = False
    "last_commit_days_ago": int,
    "open_issues": int,
    "purpose": str,
    "velo_use_case": str,
    "install_size_mb": float,
    "has_cuda_dep": bool,
    "has_network_calls": bool,         # does it phone home?
    "known_cves": list[str],
    "benchmark_result": dict | None,   # result if we can test it
    "recommended_status": str,         # ADOPT_NOW | SHADOW_TEST | WATCH | REJECT
    "recommended_reason": str,
    "evaluated_at": str,
    "evaluated_by": str,               # "autoresearch_agent_v1" | "operator"
}
```

---

## Architecture

```
Trigger: weekly cron OR operator request
    ↓
Tool Scout (GitHub API, arXiv, HuggingFace)
    ↓
Dependency Auditor (pip-audit, licence-check)
    ↓
Benchmark Runner (optional — historical data only)
    ↓
Scorecard Writer → data/autoresearch/scorecards/YYYY_MM_DD_{tool}.json
    ↓
Adoption Board Updater → docs/engineering/VELO_TOOL_ADOPTION_BOARD_V1.md
    ↓
Sentinel Gate → operator approval before any install
```

---

## Hard Rules (Permanent)

```
NO_INSTALL_WITHOUT_APPROVAL = TRUE (unconditional)
NO_PRODUCTION_TOUCH         = TRUE
NO_SCORING_CHANGE           = TRUE
NO_MODEL_MODIFICATION       = TRUE
READ_ONLY_OPERATION         = TRUE (all data access)
SENTINEL_GATE_REQUIRED      = TRUE (before SHADOW_TEST → ADOPT_NOW)
```

---

## Implementation Plan

**Phase 1** — Stub agent using LangGraph or simple Python loop
- Reads GitHub REST API (rate-limited, no auth required for public repos)
- Reads arXiv API for recent papers
- Produces scorecard JSON

**Phase 2** — DSPy-powered summarization
- Uses local LLM to summarize README and extract VÉLØ-relevant capabilities
- Detects mentions of racing, sports betting, tabular data, categorical ML

**Phase 3** — Autonomous benchmark runner
- Clones tool in isolated venv
- Runs toy benchmark on `data/velo_unified_evidence_corpus_v1.csv`
- Compares AUC/Brier against SQPE baseline

**Gate to Phase 2:** Phase 1 produces 5 validated scorecards with correct recommendations.  
**Gate to Phase 3:** DSPy extraction precision >= 0.80 on manual spot-check.

---

## Output Locations

```
data/autoresearch/scorecards/          ← per-tool JSON scorecards
data/autoresearch/weekly_report.md     ← human-readable weekly digest
docs/engineering/VELO_TOOL_ADOPTION_BOARD_V1.md  ← updated on new adoptions
```
