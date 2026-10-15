-- world_day_status: one row per race day, the end-of-day checklist for UK/IRE and the world.
-- Bounded to 30 days so each dashboard call is cheap (0.4 s). velo_vs_formfav_races is kept
-- for column compatibility but is NULL: the comparison has its own view and endpoint.
create or replace view public.world_day_status
with (security_invoker = true) as
with days as (
    select race_date as day from public.formfav_races where race_date >= current_date - 30
    union select date from public.races where date >= current_date - 30
),
ff as (
    select race_date as day, count(*) as world_races
    from public.formfav_races where race_date >= current_date - 30 group by race_date
),
pred as (
    select r.race_date as day, count(*) as world_predicted
    from public.formfav_predictions p join public.formfav_races r using (provider_race_key)
    where r.race_date >= current_date - 30
    group by r.race_date
),
eod as (
    select race_date as day,
           count(*) as world_eod_rows,
           count(*) filter (where basis = 'final') as world_final,
           count(*) filter (where basis = 'provisional') as world_provisional,
           count(*) filter (where basis = 'no_result') as world_no_result,
           max(computed_at) as world_eod_last_run
    from public.formfav_sigma_audits where race_date >= current_date - 30 group by race_date
),
uk_v as (
    select r.date as day, count(distinct v.race_id) as uk_verdict_races
    from public.races r join public.velo_verdicts v on v.race_id = r.race_id
    where r.date >= current_date - 30
    group by r.date
),
uk_s as (
    select date as day, count(*) as uk_sigma_rows from public.sigma_audits
    where date >= current_date - 30 group by date
),
hr as (
    select run_date as day, count(*) as uk_horse_runs from public.racing_horse_runs
    where run_date >= current_date - 30 group by run_date
),
mc as (
    select run_date as day, council_verdict, learning_gate_status, source_truth
    from public.velo_mission_control where run_date >= current_date - 30
)
select
    d.day,
    coalesce(ff.world_races, 0)          as world_races,
    coalesce(pred.world_predicted, 0)    as world_predicted,
    coalesce(eod.world_eod_rows, 0)      as world_eod_rows,
    coalesce(eod.world_final, 0)         as world_final,
    coalesce(eod.world_provisional, 0)   as world_provisional,
    coalesce(eod.world_no_result, 0)     as world_no_result,
    eod.world_eod_last_run,
    coalesce(uk_v.uk_verdict_races, 0)   as uk_verdict_races,
    coalesce(uk_s.uk_sigma_rows, 0)      as uk_sigma_rows,
    greatest(coalesce(uk_v.uk_verdict_races, 0) - coalesce(uk_s.uk_sigma_rows, 0), 0) as uk_sigma_missing,
    coalesce(hr.uk_horse_runs, 0)        as uk_horse_runs,
    mc.council_verdict,
    mc.learning_gate_status,
    mc.source_truth,
    null::bigint                         as velo_vs_formfav_races
from days d
left join ff   on ff.day = d.day
left join pred on pred.day = d.day
left join eod  on eod.day = d.day
left join uk_v on uk_v.day = d.day
left join uk_s on uk_s.day = d.day
left join hr   on hr.day = d.day
left join mc   on mc.day = d.day
where d.day is not null;
