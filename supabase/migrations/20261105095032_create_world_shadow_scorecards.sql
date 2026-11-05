-- Velo World is a separate PAPER/SHADOW evidence system.  It never writes
-- canonical_model_scorecards, UK Sigma, UK learning, selections or weights.

create table if not exists public.world_model_scorecards (
    scorecard_key text primary key,
    provider_race_key text not null references public.formfav_races(provider_race_key),
    race_date date not null,
    country text not null check (lower(country) not in ('gb', 'ie')),
    track text not null,
    race_number integer not null,
    scheduled_off timestamptz not null,
    model_name text not null,
    freeze_stage text not null default 'FIRST_COMPLETE',
    runner_rank integer not null,
    horse_key text not null,
    horse_name text not null,
    score numeric,
    place_prob numeric,
    longshot_prob numeric,
    captured_price numeric,
    generated_at timestamptz not null,
    generated_pre_off boolean not null,
    provider_predictions_consumed boolean not null default false
        check (provider_predictions_consumed is false),
    identity_grade text not null default 'D_NAME_COUNTRY_ONLY',
    feature_payload jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now()
);

create index if not exists world_model_scorecards_day_country_idx
    on public.world_model_scorecards (race_date, country, model_name, runner_rank);
create index if not exists world_model_scorecards_race_idx
    on public.world_model_scorecards (provider_race_key, model_name);
alter table public.world_model_scorecards enable row level security;

create table if not exists public.world_pipeline_runs (
    run_key text primary key,
    race_date date not null,
    country text not null check (lower(country) not in ('gb', 'ie')),
    model_name text not null,
    status text not null check (status in ('STARTED','PASS','PARTIAL','FAILED')),
    races_seen integer not null default 0,
    races_scored integer not null default 0,
    races_skipped_post_off integer not null default 0,
    runners_scored integer not null default 0,
    provider_predictions_consumed boolean not null default false
        check (provider_predictions_consumed is false),
    generated_at timestamptz not null,
    details jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);
alter table public.world_pipeline_runs enable row level security;

create table if not exists public.world_sigma_audits (
    sigma_key text primary key,
    provider_race_key text not null references public.formfav_races(provider_race_key),
    race_date date not null,
    country text not null check (lower(country) not in ('gb', 'ie')),
    model_name text not null,
    basis text not null check (basis in ('final','provisional','no_result','identity_blocked')),
    top1_horse_key text,
    top1_horse_name text,
    top1_rank integer,
    top1_finish_position integer,
    top1_win boolean,
    top1_frame boolean,
    winner_names text[],
    captured_price numeric,
    level_stake_profit numeric,
    identity_grade text,
    learning_eligible boolean not null default false,
    learning_block_reason text,
    computed_at timestamptz not null default now(),
    details jsonb not null default '{}'::jsonb
);
create index if not exists world_sigma_day_country_idx
    on public.world_sigma_audits (race_date, country, model_name, basis);
alter table public.world_sigma_audits enable row level security;

create table if not exists public.world_learning_events (
    event_key text primary key,
    sigma_key text not null references public.world_sigma_audits(sigma_key),
    provider_race_key text not null,
    race_date date not null,
    country text not null check (lower(country) not in ('gb', 'ie')),
    model_name text not null,
    event_class text not null,
    retained boolean not null default true,
    learning_eligible boolean not null default false,
    learning_block_reason text,
    consumed boolean not null default false,
    evidence jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now()
);
create index if not exists world_learning_day_country_idx
    on public.world_learning_events (race_date, country, learning_eligible, consumed);
alter table public.world_learning_events enable row level security;

create or replace view public.world_scorecard_daily
with (security_invoker = true) as
select race_date, country, model_name,
       count(distinct provider_race_key) as races_scored,
       count(*) as runners_scored,
       count(*) filter (where runner_rank = 1) as top_picks,
       count(*) filter (where generated_pre_off) as rows_pre_off,
       max(generated_at) as last_generated_at
from public.world_model_scorecards
group by race_date, country, model_name;
