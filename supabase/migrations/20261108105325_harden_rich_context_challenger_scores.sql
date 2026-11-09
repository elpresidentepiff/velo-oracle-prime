-- Harden the fitted Rich Context score overlay at the database boundary.
-- Existing production rows were verified shadow-only before this migration was authored.
-- The constraints are additive: scores remain in their own table and immutable evidence packets
-- are never touched.  A corrected score must use a new model_version, never rewrite history.

alter table public.rich_context_challenger_scores
  add constraint rich_context_challenger_scores_no_production_influence
  check (production_influence = false) not valid;

alter table public.rich_context_challenger_scores
  validate constraint rich_context_challenger_scores_no_production_influence;

alter table public.rich_context_challenger_scores
  add constraint rich_context_challenger_scores_paper_sim_only
  check (paper_sim_only = true) not valid;

alter table public.rich_context_challenger_scores
  validate constraint rich_context_challenger_scores_paper_sim_only;

alter table public.rich_context_challenger_scores
  add constraint rich_context_challenger_scores_packet_hash_shape
  check (packet_input_sha256 ~ '^[0-9a-f]{64}$') not valid;

alter table public.rich_context_challenger_scores
  validate constraint rich_context_challenger_scores_packet_hash_shape;

alter table public.rich_context_challenger_scores
  add constraint rich_context_challenger_scores_probability_range
  check (challenger_probability between 0.0 and 1.0) not valid;

alter table public.rich_context_challenger_scores
  validate constraint rich_context_challenger_scores_probability_range;

alter table public.rich_context_challenger_scores
  add constraint rich_context_challenger_scores_rank_positive
  check (challenger_rank is null or challenger_rank > 0) not valid;

alter table public.rich_context_challenger_scores
  validate constraint rich_context_challenger_scores_rank_positive;

-- The packet table already owns this exact unique key.  The composite FK proves
-- that the duplicated race/runner identity on a score agrees with the packet
-- hash; no name-based identity is involved.
alter table public.rich_context_challenger_scores
  add constraint rich_context_challenger_scores_packet_identity_fk
  foreign key (race_id, horse_id, packet_input_sha256)
  references public.rich_context_shadow_packets (race_id, horse_id, input_sha256)
  not valid;

alter table public.rich_context_challenger_scores
  validate constraint rich_context_challenger_scores_packet_identity_fk;

create or replace function public.block_rich_context_challenger_score_mutation()
returns trigger
language plpgsql
set search_path = ''
as $$
begin
  raise exception 'rich_context_challenger_scores is append-only';
end;
$$;

revoke all on function public.block_rich_context_challenger_score_mutation() from public, anon, authenticated;
grant execute on function public.block_rich_context_challenger_score_mutation() to service_role;

drop trigger if exists rich_context_challenger_scores_append_only
  on public.rich_context_challenger_scores;

create trigger rich_context_challenger_scores_append_only
before update or delete on public.rich_context_challenger_scores
for each row execute function public.block_rich_context_challenger_score_mutation();

revoke update, delete, truncate, references, trigger
  on public.rich_context_challenger_scores from service_role;
