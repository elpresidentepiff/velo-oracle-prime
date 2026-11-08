-- Read-only fallback for the WAKE VELO panel (WAKE-VELO-SETTLE-01 follow-up).
-- A scorecard row only gets its result when the EOD rebuilds it, and Champion Intent, New Build A/B and the Passport proxy
-- could not be rebuilt in the clean EOD container (their morning inputs were never saved), so ~75 picks each sat with no
-- result although the Racing Post results are ingested. Where the scorecard has no result, read it from racing_horse_runs
-- by EXACT race_id + horse_id (never by name). The scorecard's own result still wins wherever it exists, and
-- result_source says which one was used. Nothing is written; shadow only.
create or replace view public.wake_velo_model_picks
with (security_invoker = true) as
with top as not materialized (
  select distinct on (run_date, race_id, model_name)
         run_date as race_date, race_id, horse_id, model_name, lane_name,
         horse as top_horse, score, tie_status, result_position, win,
         count(*) over (partition by run_date, race_id, model_name) as rank1_rows
  from public.canonical_model_scorecards
  where rank = 1
  order by run_date, race_id, model_name, score desc nulls last, horse
), meta as not materialized (
  select distinct on (race_date, race_id)
         race_date, race_id, course, off_time,
         -- Racing Post prints afternoon times without am/pm ("3.00" = 15:00); a one-digit hour is pm.
         case when off_time ~ '^[0-9]{1,2}[.:][0-9]{2}$' then
           (case when length(split_part(replace(off_time, ':', '.'), '.', 1)) = 1
                 then split_part(replace(off_time, ':', '.'), '.', 1)::int + 12
                 else split_part(replace(off_time, ':', '.'), '.', 1)::int end) * 60
           + split_part(replace(off_time, ':', '.'), '.', 2)::int
         end as off_minutes
  from public.runner_prediction_snapshots
  order by race_date, race_id, created_at desc
), ingested as not materialized (
  select run_date as race_date, race_id, horse_id, position_int
  from public.racing_horse_runs
  where position_int is not null
)
select t.race_date, t.race_id, m.course, m.off_time, m.off_minutes,
       t.model_name, t.lane_name, t.top_horse, t.score, t.tie_status,
       coalesce(t.result_position, i.position_int)                                     as result_position,
       case when t.result_position is not null then t.win else (i.position_int = 1) end as win,
       pr.top_horse as prime_horse, pr.tie_status as prime_tie_status,
       (t.top_horse is not null and t.top_horse = pr.top_horse) as agrees_with_prime,
       t.rank1_rows,
       case when t.result_position is not null then 'scorecard'
            when i.position_int is not null then 'ingested_results' end                as result_source
from top t
left join meta m using (race_date, race_id)
left join top pr on pr.race_date = t.race_date and pr.race_id = t.race_id
                and pr.model_name = 'MAIN_VELO_PRIME'
left join ingested i on i.race_date = t.race_date and i.race_id = t.race_id and i.horse_id = t.horse_id;

revoke all on public.wake_velo_model_picks from public, anon, authenticated;
grant select on public.wake_velo_model_picks to service_role;
