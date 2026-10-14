-- FormFav global end-of-day sigma (SHADOW ONLY).
-- Separate from public.sigma_audits: international results never feed the UK
-- learning loop. One row per race, upserted on provider_race_key so reruns and
-- provisional -> final upgrades overwrite in place.
create table if not exists public.formfav_sigma_audits (
    provider_race_key    text primary key,
    race_date            date        not null,
    country              text,
    track                text,
    race_number          integer,
    start_time           timestamptz,
    basis                text        not null
        check (basis in ('final', 'provisional', 'no_result')),
    result_stage         text,
    model_version        text,
    confidence           text,
    field_size           integer,
    top1_name            text,
    top1_number          integer,
    top1_win_prob        numeric,
    top1_finish_position integer,
    top1_scratched       boolean     not null default false,
    top1_hit             boolean,
    top3_names           text[],
    winner_names         text[],
    winner_numbers       integer[],
    dead_heat            boolean     not null default false,
    winner_in_top3       boolean,
    winner_model_rank    integer,
    winner_win_prob      numeric,
    details              jsonb       not null default '{}'::jsonb,
    computed_at          timestamptz not null default now()
);

create index if not exists formfav_sigma_audits_date_idx
    on public.formfav_sigma_audits (race_date, country);

alter table public.formfav_sigma_audits enable row level security;

-- Daily rollup by country and result basis. Provisional rows are reported
-- separately and are never blended into the final strike rate.
create or replace view public.formfav_sigma_daily
with (security_invoker = true) as
select
    race_date,
    country,
    basis,
    count(*)                                           as races,
    count(*) filter (where top1_hit)                   as top1_wins,
    count(*) filter (where winner_in_top3)             as winner_in_top3,
    count(*) filter (where top1_scratched)             as top1_scratched,
    round(100.0 * count(*) filter (where top1_hit)
          / nullif(count(*), 0), 1)                    as top1_strike_pct,
    max(computed_at)                                   as computed_at
from public.formfav_sigma_audits
group by race_date, country, basis;
