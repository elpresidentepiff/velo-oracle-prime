-- Horse-history candidate SHADOW output, one row per runner per race per day (HISTORY-SHADOW-01).
-- Shadow only: production_influence is always false. Written by the morning run via the service role.
-- Read by /api/horse-history-shadow. RLS on, no policies: only the service role reads or writes.
create table if not exists public.horse_history_shadow (
  run_date        date        not null,
  race_id         text        not null,
  horse           text        not null,
  horse_key       text,
  model           text        not null,
  prob            double precision,
  rank_in_race    integer,
  runs_prior      integer,
  history_known   boolean,
  status          text        not null,
  production_influence boolean not null default false,
  generated_at    timestamptz not null default now(),
  primary key (run_date, race_id, horse)
);
alter table public.horse_history_shadow enable row level security;
create index if not exists horse_history_shadow_date_idx on public.horse_history_shadow (run_date);
