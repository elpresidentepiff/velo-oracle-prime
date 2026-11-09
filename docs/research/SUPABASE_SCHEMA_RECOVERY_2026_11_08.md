# Supabase Schema Recovery Contract — 8 November 2026

## Status

**P0 deployment integrity blocker.** The production database is healthy enough to
serve VÉLØ, but its schema cannot currently be reproduced from the Git migration
directory. No production data, model weights, or learning gates may be changed
to work around this condition.

This is a platform-control problem, not a scoring-model problem.

## Evidence

The production project (`ltbsxbvfsxtnharjvqcm`) contains live foundation tables
that are used by VÉLØ and have material data:

| Table | Verified production rows | Repository creation migration |
| --- | ---: | --- |
| `runner_race_facts` | 14,699 | Missing |
| `runner_results` | 33,430 | Missing |
| `horse_profiles` | 183,699 | Missing |
| `velo_post_race_reviews` | 363 | Missing |
| `runners` | 17,377 | Present, but incompatible historical variants existed |
| `races` | 8,382 | Present, but incompatible historical variants existed |

Production's `supabase_migrations.schema_migrations` ledger records numerous
applied versions absent from this repository. It includes the March 2026
foundation-era steps and later operational migrations. This proves that parts of
the schema were created through the SQL editor, MCP, or another deployment path
without their authoritative migration files landing in Git.

A clean Supabase preview branch therefore stops at
`20260315_phase22_hardening.sql`:

```text
ERROR: relation "runner_race_facts" does not exist (SQLSTATE 42P01)
```

That failure is correct. It must not be bypassed by creating empty placeholder
tables, suppressing the preview check, or accepting a production deploy without
a replay-safe schema chain.

## Repairs already made on PR #183

1. Moved a destructive legacy V12 bootstrap out of the active migration chain.
   It dropped and recreated core tables with a conflicting schema.
2. Timestamped legacy migrations so their real prerequisites run first.
3. Recreated `batch_status_overview` safely where its historical migration
   inserts a column in the middle of the view projection.
4. Archived two explicitly “already live” hotfixes that cannot replay against
   the canonical ingestion spine.

These fixes remove known false history. They do **not** invent the missing
production foundation.

## Required recovery sequence

### 1. Freeze the source of truth

- Treat production as read-only during recovery.
- Do not run `db reset --linked`, destructive SQL, or broad backfills.
- Do not change EOD gates to compensate for schema drift.
- Preserve the current migration directory and production migration ledger as
  forensic evidence.

### 2. Export the production schema, excluding data

Use a linked Supabase CLI session against the production project and generate a
schema-only pull. The authoritative operation is:

```text
supabase db pull --linked
```

The generated migration must be reviewed before committing. It is a schema
baseline, not a data dump; do not export Racing Post artifacts, user data,
credentials, or operational secrets into Git.

### 3. Build a baseline from the exported schema

- Place the reviewed baseline before all replayable application migrations.
- Keep it additive with respect to the live production ledger: production must
  record the baseline version as already applied before any future `db push`.
- Preserve public-schema RLS and policies. New public tables must not become
  anonymously writable or readable by accident.
- Split views, functions, triggers, indexes, policies, and grants into clearly
  reviewed sections if the pull makes that safer to audit.

### 4. Reconcile historical files

Classify every legacy SQL file into exactly one class:

| Class | Treatment |
| --- | --- |
| Replayable migration | Keep active, timestamped, and testable on a fresh database. |
| Already-applied one-off hotfix | Archive with an explicit warning and ledger reference. |
| Destructive bootstrap | Archive; it must never be replayed into VÉLØ. |
| Missing production step | Recover from the reviewed baseline/export, never reconstruct from guesses. |

### 5. Prove the reconstruction

1. Create a new Supabase preview branch.
2. Replay every active migration from an empty branch.
3. Confirm migration, configuration, seed, and service stages succeed.
4. Compare critical tables, columns, constraints, RLS and functions against
   production metadata.
5. Run canonical settlement and learning tests.
6. Only then allow the settlement-writer PR to merge.

## Acceptance criteria

- A fresh preview branch finishes with **Migrations ✅**.
- No active migration refers to a table absent from all earlier active schema
  definitions.
- `supabase_migrations.schema_migrations` and Git agree on all future versions.
- Canonical scorecard rows persist typed settlement and price provenance.
- A subsequent governed EOD produces nonzero official-eligible rows only when
  a complete, immutable Racing Post result artifact exists.
- No prediction is promoted and no paper/shadow result is represented as live
  performance before those gates pass.

## Ownership boundary

PR #183 repairs the canonical settlement and learning-writer contract. Schema
baseline recovery is a separate P0 prerequisite because it affects every future
Supabase deployment, not just that feature. Do not merge PR #183 until the
baseline has made Supabase Preview green.
