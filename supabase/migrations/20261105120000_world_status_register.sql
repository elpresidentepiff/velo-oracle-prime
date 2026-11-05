-- World status register (docs/current/WORLD_ONE_TRUTH.md, "Aftercare").
-- Read-only views over the existing World tables: no new tables, no writes, PAPER/SHADOW only.
-- One row per race_date x country, plus a one-row summary. "Next safe action" is written by
-- people and agents in docs/current/DIARY.md; everything measurable is computed here.

create or replace view public.world_status_register
with (security_invoker = true) as
with world_races as (
    select race_date, lower(country) as country, count(*) as races
    from public.formfav_races
    where lower(country) not in ('gb', 'ie')
    group by 1, 2
),
top_picks as (
    select race_date, country, provider_race_key,
           coalesce(feature_payload ->> 'price_state',
                    case when captured_price is null or captured_price = 10 then 'MISSING'
                         else 'UNVERIFIED' end) as price_state
    from public.world_model_scorecards
    where runner_rank = 1
),
frozen as (
    select race_date, country,
           count(*) as frozen_races,
           count(*) filter (where price_state <> 'REAL') as price_blind_races
    from top_picks
    group by 1, 2
),
ranked as (
    select race_date, country, provider_race_key,
           rank() over (partition by provider_race_key order by score desc) as r
    from public.world_model_scorecards
    where score is not null
),
ties as (
    select race_date, country, count(*) as tied_top_races
    from (
        select race_date, country, provider_race_key
        from ranked where r = 1
        group by 1, 2, 3
        having count(*) > 1
    ) t
    group by 1, 2
),
sigma as (
    select race_date, lower(country) as country,
           count(*) filter (where basis = 'final') as settled_final,
           count(*) filter (where basis = 'provisional') as settled_provisional,
           count(*) filter (where basis = 'no_result') as no_result,
           count(*) filter (where basis = 'identity_blocked') as identity_blocked,
           count(*) filter (where basis = 'final' and top1_win) as final_wins,
           count(*) filter (where basis = 'final' and top1_frame) as final_frames,
           count(*) filter (where (details ->> 'skill_sample')::boolean) as skill_sample_races
    from public.world_sigma_audits
    group by 1, 2
),
learning as (
    select race_date, lower(country) as country,
           count(*) as learning_events,
           count(*) filter (where learning_eligible) as learning_eligible_events,
           count(*) filter (where consumed) as learning_consumed_events
    from public.world_learning_events
    group by 1, 2
),
last_run as (
    select distinct on (race_date, lower(country))
           race_date, lower(country) as country,
           status as last_run_status, generated_at as last_run_at,
           details ->> 'code_commit' as last_run_commit
    from public.world_pipeline_runs
    where model_name <> 'WORLD_SIGMA_V1'
    order by race_date, lower(country), generated_at desc
)
select w.race_date, w.country,
       w.races as world_races,
       coalesce(f.frozen_races, 0) as frozen_races,
       greatest(w.races - coalesce(f.frozen_races, 0), 0) as unfrozen_races,
       coalesce(f.price_blind_races, 0) as price_blind_races,
       coalesce(t.tied_top_races, 0) as tied_top_races,
       coalesce(s.settled_final, 0) as settled_final,
       coalesce(s.settled_provisional, 0) as settled_provisional,
       coalesce(s.no_result, 0) as no_result,
       coalesce(s.identity_blocked, 0) as identity_blocked,
       greatest(coalesce(f.frozen_races, 0) - coalesce(s.settled_final, 0), 0) as unresolved_results,
       coalesce(s.final_wins, 0) as final_wins,
       coalesce(s.final_frames, 0) as final_frames,
       coalesce(s.skill_sample_races, 0) as skill_sample_races,
       coalesce(l.learning_events, 0) as learning_events,
       coalesce(l.learning_eligible_events, 0) as learning_eligible_events,
       coalesce(l.learning_consumed_events, 0) as learning_consumed_events,
       r.last_run_status, r.last_run_at, r.last_run_commit,
       (coalesce(f.frozen_races, 0) > 0
        and w.races <= coalesce(f.frozen_races, 0)
        and coalesce(f.frozen_races, 0) = coalesce(s.settled_final, 0)) as day_complete
from world_races w
left join frozen f using (race_date, country)
left join ties t using (race_date, country)
left join sigma s using (race_date, country)
left join learning l using (race_date, country)
left join last_run r using (race_date, country);

create or replace view public.world_status_summary
with (security_invoker = true) as
select
    (select max(race_date) from public.world_status_register where day_complete)
        as last_complete_world_date,
    (select details ->> 'code_commit' from public.world_pipeline_runs
      where model_name <> 'WORLD_SIGMA_V1' order by generated_at desc limit 1)
        as last_deployed_commit,
    (select max(generated_at) from public.world_pipeline_runs
      where model_name <> 'WORLD_SIGMA_V1') as last_freeze_run_at,
    (select max(generated_at) from public.world_pipeline_runs
      where model_name = 'WORLD_SIGMA_V1') as last_settlement_run_at,
    (select coalesce(sum(frozen_races), 0) from public.world_status_register) as frozen_races,
    (select coalesce(sum(price_blind_races), 0) from public.world_status_register) as price_blind_races,
    (select coalesce(sum(unresolved_results), 0) from public.world_status_register) as unresolved_results,
    (select coalesce(sum(learning_eligible_events), 0) from public.world_status_register) as learning_eligible_events,
    (select coalesce(sum(learning_consumed_events), 0) from public.world_status_register) as learning_consumed_events;

comment on view public.world_status_register is
    'Velo World aftercare register: coverage, unresolved results, learning admission per day x country. Read-only.';
comment on view public.world_status_summary is
    'One-row Velo World status: last complete date, last deployed commit, unresolved and eligible counts. Read-only.';
