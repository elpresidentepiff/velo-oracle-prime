-- Immutable, time-safe evidence ledger for RP Horse Arrival Snapshot facts.
-- This is a shadow/research source only; it cannot alter Prime production.
create table if not exists public.rp_arrival_snapshot_facts (
  id bigint generated always as identity primary key,
  race_date date not null,
  race_id text not null,
  horse_id text not null,
  horse_name text not null,
  feature_schema_version text not null,
  parser_version text not null,
  captured_at timestamptz null,
  off_time_utc timestamptz null,
  captured_before_off boolean not null default false,
  identity_eligible boolean not null default false,
  raw_text_sha256 text null check (raw_text_sha256 is null or raw_text_sha256 ~ '^[0-9a-f]{64}$'),
  normalized_text_sha256 text null check (normalized_text_sha256 is null or normalized_text_sha256 ~ '^[0-9a-f]{64}$'),
  has_spotlight_text boolean not null default false,
  has_diomed_text boolean not null default false,
  source_capture_provenance text not null,
  source_url text null,
  source_html_sha256 text null check (source_html_sha256 is null or source_html_sha256 ~ '^[0-9a-f]{64}$'),
  factual_spans jsonb not null default '[]'::jsonb,
  rejected_spans jsonb not null default '[]'::jsonb,
  feature_families jsonb not null default '[]'::jsonb,
  family_counts jsonb not null default '{}'::jsonb,
  eligible_family_count integer not null default 0 check (eligible_family_count >= 0),
  training_eligible boolean not null default false,
  ineligibility_reasons jsonb not null default '[]'::jsonb,
  production_prime_consumed boolean not null default false check (production_prime_consumed = false),
  provider_prediction_consumed boolean not null default false check (provider_prediction_consumed = false),
  created_at timestamptz not null default now(),
  unique (race_id, horse_id)
);

-- The initial hosted creation was applied outside repository history.  Keep
-- this migration additive/idempotent so production receives the evidence
-- provenance needed by the governed builder without rewriting any packet.
alter table public.rp_arrival_snapshot_facts
  add column if not exists has_diomed_text boolean not null default false,
  add column if not exists source_capture_provenance text not null default 'UNKNOWN',
  add column if not exists source_url text,
  add column if not exists source_html_sha256 text;

create index if not exists rp_arrival_snapshot_facts_day_idx
  on public.rp_arrival_snapshot_facts (race_date, race_id);
create index if not exists rp_arrival_snapshot_facts_eligible_idx
  on public.rp_arrival_snapshot_facts (race_date, training_eligible)
  where training_eligible;

alter table public.rp_arrival_snapshot_facts enable row level security;
revoke all on table public.rp_arrival_snapshot_facts from anon, authenticated;
grant select, insert on table public.rp_arrival_snapshot_facts to service_role;
revoke update, delete, truncate, references, trigger on table public.rp_arrival_snapshot_facts from service_role;
revoke all on sequence public.rp_arrival_snapshot_facts_id_seq from anon, authenticated;
grant usage, select on sequence public.rp_arrival_snapshot_facts_id_seq to service_role;

create or replace function public.block_rp_arrival_snapshot_fact_mutation()
returns trigger
language plpgsql
set search_path = ''
as $$
begin
  raise exception 'rp_arrival_snapshot_facts is append-only';
end;
$$;

drop trigger if exists rp_arrival_snapshot_facts_append_only on public.rp_arrival_snapshot_facts;
create trigger rp_arrival_snapshot_facts_append_only
before update or delete on public.rp_arrival_snapshot_facts
for each row execute function public.block_rp_arrival_snapshot_fact_mutation();
