# VÉLØ MCP Boundary V1

**Status:** DESIGN ONLY  
**Phase:** 9 — Agent Operations  
**Classification:** `MCP_BOUNDARY_DEFINED` / `DESIGN_ONLY`

---

## Purpose

Agents may only connect to tools through approved MCP boundaries. This prevents runaway agents from accessing secrets, live state, or production systems.

---

## Allowed First (Read-Only)

| Tool | Access | Notes |
|---|---|---|
| Filesystem (read-only) | Historical parquets, reports, scripts | No write to live paths |
| Supabase read-only views | Evidence corpus, sigma results | No INSERT/UPDATE/DELETE |
| GitHub repo metadata | Issue list, PR status, commit log | No force push, no merge |
| Report index | `data/reports/*.json` | Read-only |

## Blocked (Hard)

| Tool | Block Reason |
|---|---|
| `.env` / secrets | Credentials never exposed to agents |
| `models/sqpe_v17/sqpe_v17.pkl` | Live model — no agent access |
| `src/velo/weight_policy_registry.py` (write) | Live scoring weights |
| Telegram API | Format locked — no agent writes |
| Betfair API | Hard guard — no agent access |
| Railway service config | No agent activation of workers |
| Supabase INSERT on `runner_release_candidates` | Live pipeline table |
| Any `.env` variable write path | Credential mutation blocked |

---

## MCP Server Registration Policy

New MCP servers may only be registered if:
1. They provide read-only access OR
2. They are sandboxed to a non-live path AND
3. Council reviews the registration before activation

No MCP server may be registered that exposes:
- Production secrets
- Betfair execution paths
- Railway deployment triggers
- Live model file paths

```
MCP_BOUNDARY_V1_STATUS: DEFINED
ENFORCEMENT: DESIGN — implementation when agent harness (Phase 3) is live
```
