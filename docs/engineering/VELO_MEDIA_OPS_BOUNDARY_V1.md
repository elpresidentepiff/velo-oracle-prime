# VÉLØ Media Ops Engine — Architectural Boundary Doctrine (V1)
**Author:** Manus AI | **Status:** RATIFIED | **Date:** Jun 08, 2026 | **Version:** 1.0.0

---

## 1. The Boundary

The Agent Harness and the Media Ops Engine are two completely separate systems.
They must never share code, imports, or execution paths.

```
┌─────────────────────────────────────────────────────────────────┐
│  AGENT HARNESS (VELO protection only)                           │
│    Source truth · Pipeline health · Scoring safety              │
│    Learning eligibility · Contamination recovery                │
│    Mission Control · Council evidence                           │
│                                                                 │
│    Produces: Trusted Truth Artifacts                            │
│    (data/harness_returns/, sigma/, data/council_evidence_*.json)│
└──────────────────────────┬──────────────────────────────────────┘
                           │  READ ONLY — one-way data flow
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│  MEDIA OPS ENGINE (separate lane)                               │
│    Podcast production · Spotify publishing                      │
│    Audio generation · Distribution                              │
│                                                                 │
│    Reads: Final approved VELO truth artifacts                   │
│    Never: Invokes, modifies, or becomes part of Agent Harness   │
└─────────────────────────────────────────────────────────────────┘
```

---

## 2. Hard Rules

### 2.1 Agent Harness — what it must never do

The Agent Harness (`src/velo/harness/`, `scripts/ops/run_agent_harness.py`) must
never contain any of the following:

| Forbidden dependency | Reason |
|---|---|
| `spotify` imports or API calls | Media Ops concern only |
| `podcast` generation or publishing | Media Ops concern only |
| `media_ops` module imports | Media Ops concern only |
| Audio file creation or upload | Media Ops concern only |
| RSS feed management | Media Ops concern only |

Spotify failures must **never** affect VELO operations or learning.
If the Media Ops Engine is down, the Agent Harness continues without interruption.

### 2.2 Media Ops Engine — what it must never do

The Media Ops Engine must never:

| Forbidden action | Reason |
|---|---|
| Import from `src/velo/harness/` | Harness is VELO-internal only |
| Call `run_agent_harness.py` | Execution control belongs to harness |
| Write to `data/sentient_state*.json` | VELO learning state — harness-controlled |
| Write to `sigma/` | Sigma is a harness truth artifact |
| Modify scoring or model weights | Harness-protected |
| Invoke `run_prime_today.py` | Scoring pipeline — harness-controlled |

### 2.3 One-way data flow

The only permitted interaction is a **read-only, one-way data flow**:

```
Agent Harness writes → Trusted Truth Artifacts → Media Ops Engine reads
```

Permitted artifact reads by Media Ops Engine:

| Artifact | Location | Content |
|---|---|---|
| Daily sigma close | `sigma/{date}/sigma_close_*.json` | Race-day performance summary |
| Council evidence packet | `data/council_evidence_latest.json` | Audit evidence |
| Harness execution return | `data/harness_returns/*_latest.json` | Run verdict and metrics |
| VELO prime observability | `data/velo_prime_observability_latest.json` | Scoring health |

---

## 3. Enforcement

The Sentinel (`src/velo/harness/sentinel.py`) enforces Rule 3 at runtime:

```python
# RULE_3_MEDIA_OPS: Any contract item containing 'spotify', 'podcast',
# 'media_ops', 'audio_publish', or 'media_engine' is immediately blocked.
```

The `TaskContract.__post_init__` validator enforces the same rule at
contract construction time, so contamination is caught before any
execution begins.

---

## 4. Deployment Sequence

The Media Ops Engine is built and deployed **after** the Agent Harness
is stable and producing trusted artifacts. It is never co-deployed with
or inside the harness.

| Phase | System | Action |
|---|---|---|
| 1 | Agent Harness | Shadow mode — observe and record |
| 2 | Agent Harness | Enforced read-only — control audits and Council |
| 3 | Agent Harness | Enforced code — govern non-live file tasks |
| 4 | Media Ops Engine | Read harness artifacts — produce podcast content |
| 5 | Media Ops Engine | Publish to Spotify — harness has no knowledge of this |

---

## 5. Summary

> The Agent Harness protects VELO and produces trusted truth artifacts.
> Trusted truth artifacts feed the Media Ops Engine.
> The podcast lane may read VELO's final approved artifacts, but it
> cannot invoke, modify, or become part of the Agent Harness.
> Spotify failures must never affect VELO operations or learning.
