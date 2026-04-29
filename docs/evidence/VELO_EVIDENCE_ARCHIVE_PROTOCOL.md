# VÉLØ Evidence Archive Protocol

**Version:** 1.0 | **Date:** 2026-04-28

This document defines how VÉLØ evidence is archived, versioned, and preserved.
It governs both the Git canonical archive and the optional Supabase evidence path.

---

## Path 1 — Git Canonical Archive (PRIMARY)

### Location
```
docs/evidence/           ← Human-readable Markdown evidence documents
data/evidence_vault/     ← Machine-readable JSON + CSV evidence data
```

### Rules
1. **Never overwrite.** All evidence files are versioned (v1, v2, v3). Old versions stay in Git forever.
2. **Commit immediately.** Evidence artifacts should be committed as soon as they are generated.
3. **No secrets in evidence files.** Run `git diff --cached | grep -Ei "service_role|api_key|secret|password|token"` before every evidence commit.
4. **Meaningful commit messages.** Every evidence commit should describe what changed in the evidence, not just "update files."
5. **Tag major evidence milestones.** When a signal is promoted from WATCHLIST to PROVEN, tag the commit: `git tag evidence/v2_watchlist_crossed XXXXXXX`

### File naming convention
```
data/evidence_vault/velo_unified_evidence_audit_v1.json   ← first audit
data/evidence_vault/velo_unified_evidence_audit_v2.json   ← second audit (increment)
docs/evidence/special_days/VELO_SPECIAL_DAY_2026-04-28.md
docs/evidence/VELO_SIGNAL_RANKINGS_V1.md
docs/evidence/VELO_SIGNAL_RANKINGS_V2.md                  ← add new, don't replace
```

---

## Path 2 — Supabase Optional Archive

### Status: SCHEMA PROPOSED — NOT YET WRITTEN

**Do not write to Supabase automatically.** Only write after explicit operator approval.
The proposed schema is documented below for future implementation.

### Proposed table: `velo_evidence_artifacts`

```sql
CREATE TABLE velo_evidence_artifacts (
  id              uuid DEFAULT gen_random_uuid() PRIMARY KEY,
  artifact_type   text NOT NULL,   -- 'unified_audit', 'special_day', 'signal_rankings', etc.
  artifact_name   text NOT NULL,   -- e.g., 'velo_unified_evidence_audit_v1'
  artifact_date   date NOT NULL,   -- evidence date
  source_path     text,            -- git repo path
  git_commit      text,            -- SHA of commit containing artifact
  json_payload    jsonb,           -- full JSON content (for query access)
  markdown_payload text,           -- full Markdown content (for display)
  created_at      timestamptz DEFAULT now(),
  created_by_agent text,           -- e.g., 'claude-sonnet-4-6'
  checksum        text,            -- SHA256 of json_payload
  status          text DEFAULT 'active'  -- 'active', 'superseded', 'archived'
);
```

### Proposed Supabase archive manifest
`data/evidence_vault/supabase_evidence_archive_manifest_v1.json`
Contains: list of artifacts, their git commits, and whether they have been uploaded to Supabase.

### Trigger for Supabase write
When operator explicitly approves: "upload evidence artifact X to Supabase"
Script to run: `scripts/upload_evidence_to_supabase.py --artifact <name>`
(Script to be built when needed.)

---

## Evidence Hierarchy

```
Tier 1 (Gold): data/evidence_vault/ — machine-readable, queryable, immutable
Tier 2 (Silver): docs/evidence/ — human-readable, investor-facing
Tier 3 (Bronze): CLAUDE.md — agent context, updated per session
Tier 4 (Reference): router_shadow_audit_ledger.csv — daily accumulation
```

Tier 1 artifacts are the source of truth. Tier 3 and 4 are derived summaries.

---

## Audit Cycle

| Frequency | Action |
|---|---|
| Daily (after sigma) | `build_innovation_protocol.py --date` + `router_shadow_audit.py` |
| Weekly or after 20+ new results | `run_velo_unified_evidence_audit.py` → update evidence_vault |
| When signal ranking changes | New `VELO_SIGNAL_RANKINGS_VN.md` + vault copy |
| When router lane is promoted | `git tag evidence/lane_promotion_XXXXXXX` + update index |
| When major modification lands | Special Day report for first post-modification day |

---

*VÉLØ Oracle Prime — Evidence Archive Protocol V1*
