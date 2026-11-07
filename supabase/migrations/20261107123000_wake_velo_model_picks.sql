-- Read-only per-race, per-model top picks for the dashboard "WAKE VELO" panel (WAKE-VELO-DASH-01).
-- Every model that writes canonical scorecards appears, Prime included, so the panel can put all
-- of them side by side. A TIED_* top pick is arbitrary, and rank1_rows > 1 means the lane wrote
-- several rank-1 rows for the race; neither is a clean read. (tie_status N/A = not applicable.) Shadow only. No table is changed and nothing here feeds Prime.
create or replace view public.wake_velo_model_picks
with (security_invoker = true) as
with top as not materialized (
  select distinct on (run_date, race_id, model_name)
         run_date as race_date, race_id, model_name, lane_name,
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
)
select t.race_date, t.race_id, m.course, m.off_time, m.off_minutes,
       t.model_name, t.lane_name, t.top_horse, t.score, t.tie_status,
       t.result_position, t.win,
       pr.top_horse as prime_horse, pr.tie_status as prime_tie_status,
       (t.top_horse is not null and t.top_horse = pr.top_horse) as agrees_with_prime,
       t.rank1_rows
from top t
left join meta m using (race_date, race_id)
left join top pr on pr.race_date = t.race_date and pr.race_id = t.race_id
                and pr.model_name = 'MAIN_VELO_PRIME';

revoke all on public.wake_velo_model_picks from public, anon, authenticated;
grant select on public.wake_velo_model_picks to service_role;
