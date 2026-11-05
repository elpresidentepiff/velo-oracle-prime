-- Cover the World evidence foreign keys flagged by the Supabase performance advisor.
create index if not exists world_sigma_provider_race_idx
    on public.world_sigma_audits (provider_race_key);
create index if not exists world_learning_sigma_key_idx
    on public.world_learning_events (sigma_key);
