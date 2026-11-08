-- Append-only overlay of challenger scores, separate from the immutable evidence packet (WAKE-VELO-CHALLENGER-FIT-01).
-- rich_context_shadow_packets has no UPDATE grant for service_role by design (the packet is evidence, never
-- rewritten); a fitted model's score therefore cannot be written back onto the packet row once it exists. Per
-- docs/engineering/WAKE_VELO_RICH_CONTEXT_CHALLENGER_PLAN_V1.md Phase 5: "Persist a separate artifact and
-- Supabase rows with challenger probability, rank, ... scorer version". This table is that row: one score per
-- (packet input hash, model version), so a later model version scores the same immutable evidence again without
-- ever touching or losing the earlier version's row. Shadow only; nothing here feeds Prime.
create table if not exists public.rich_context_challenger_scores (
  id                      bigint generated always as identity primary key,
  race_date               date not null,
  race_id                 text not null,
  horse_id                text not null,
  packet_input_sha256     text not null,          -- the exact packet this score was computed from
  model_version           text not null,
  challenger_probability  double precision not null,
  challenger_rank         integer,                 -- within (race_id, model_version); null until ranked
  production_influence    boolean not null default false,
  paper_sim_only          boolean not null default true,
  code_sha                text,
  scored_at               timestamptz not null default now(),
  unique (packet_input_sha256, model_version)
);

create index if not exists rich_context_challenger_scores_race_idx
  on public.rich_context_challenger_scores (race_date, race_id, model_version);

alter table public.rich_context_challenger_scores enable row level security;
revoke all on public.rich_context_challenger_scores from public, anon, authenticated;
grant select, insert on public.rich_context_challenger_scores to service_role;
-- No update/delete grant anywhere, including postgres-via-API: a score is corrected by inserting a new
-- model_version, exactly like the packets themselves, never by rewriting history.

comment on table public.rich_context_challenger_scores is
  'Append-only Rich Context challenger scores, keyed by (packet_input_sha256, model_version). Shadow only, no production influence.';
