# research/ — Quarantined Research Code

This directory holds experimental code and migrations that are NOT part of the
live scoring path and must NOT be imported by any production module.

## Contents

| Path | Moved from | Reason |
|------|-----------|--------|
| `v13/racing_analogs/` | `src/v13/racing_analogs/` | 4,271 lines added in G shadow commit; never imported in live path; unvalidated analog matching logic |
| `migrations/hk_research_schema.sql` | `supabase/migrations/` | HK market research schema — not applied to production DB |
| `migrations/fr_research_schema.sql` | `supabase/migrations/` | FR market research schema — not applied to production DB |

## Rules

- **NEVER import from `research/` in `app/`, `src/`, `scripts/`, or `workers/`.**
- To promote any code here to live: open a PR, add test coverage, get explicit sign-off.
- Research migrations in `research/migrations/` must NOT be applied to the production Supabase project.
