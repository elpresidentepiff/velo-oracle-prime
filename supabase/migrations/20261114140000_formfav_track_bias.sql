-- FormFav track/barrier bias, stored as timestamped snapshots (FORMFAV-INGEST-01).
-- Written by the live worker after each racecard refresh. Append-only. Raw payload kept, so the
-- sample sizes and missingness FormFav returns are never lost. Service role only (RLS on, no policies).
create table if not exists public.formfav_track_bias (
  provider_race_key text        not null,
  captured_at       timestamptz not null,
  venue             text,
  country           text,
  distance          text,
  condition         text,
  window_days       integer,
  bias_strength     double precision,
  barrier_stats     jsonb,
  payload           jsonb       not null,
  primary key (provider_race_key, captured_at)
);
alter table public.formfav_track_bias enable row level security;
create index if not exists formfav_track_bias_race_idx on public.formfav_track_bias (provider_race_key);
