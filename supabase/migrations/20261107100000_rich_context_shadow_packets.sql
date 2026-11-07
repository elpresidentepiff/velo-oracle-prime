create table if not exists public.rich_context_shadow_packets (
  id bigint generated always as identity primary key,
  race_date date not null,
  race_id text not null,
  horse_id text not null,
  packet_schema_version text not null,
  challenger_version text not null,
  model_status text not null,
  input_sha256 text not null check (input_sha256 ~ '^[0-9a-f]{64}$'),
  feature_vector_sha256 text not null check (feature_vector_sha256 ~ '^[0-9a-f]{64}$'),
  family_coverage jsonb not null,
  provenance jsonb not null,
  feature_families jsonb not null,
  eligible_for_future_fit boolean not null,
  ineligibility_reasons jsonb not null,
  challenger_probability double precision null,
  challenger_rank integer null,
  production_influence boolean not null default false check (production_influence = false),
  provider_predictions_consumed boolean not null default false check (provider_predictions_consumed = false),
  paper_sim_only boolean not null default true check (paper_sim_only = true),
  code_sha text not null,
  created_at timestamptz not null default now(),
  unique (race_id, horse_id, input_sha256)
);

create index if not exists rich_context_shadow_packets_day_race_idx
  on public.rich_context_shadow_packets (race_date, race_id);
create index if not exists rich_context_shadow_packets_fit_idx
  on public.rich_context_shadow_packets (race_date, eligible_for_future_fit)
  where eligible_for_future_fit;

alter table public.rich_context_shadow_packets enable row level security;
revoke all on table public.rich_context_shadow_packets from anon, authenticated;
grant select, insert on table public.rich_context_shadow_packets to service_role;
revoke update, delete, truncate, references, trigger on table public.rich_context_shadow_packets from service_role;
revoke all on sequence public.rich_context_shadow_packets_id_seq from anon, authenticated;
grant usage, select on sequence public.rich_context_shadow_packets_id_seq to service_role;

create or replace function public.block_rich_context_shadow_packet_mutation()
returns trigger
language plpgsql
set search_path = ''
as $$
begin
  raise exception 'rich_context_shadow_packets is append-only';
end;
$$;

drop trigger if exists rich_context_shadow_packets_append_only on public.rich_context_shadow_packets;
create trigger rich_context_shadow_packets_append_only
before update or delete on public.rich_context_shadow_packets
for each row execute function public.block_rich_context_shadow_packet_mutation();
