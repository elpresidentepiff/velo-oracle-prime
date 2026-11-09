-- Prime's top pick beside the Rich Context challenger's top pick, one row per UK/IRE race (PVC-DASH-01).
-- Read-only, security_invoker, service_role select only, bounded to the last 45 days so a request for one
-- date stays fast. Shadow only: the challenger has production_influence = false and picks nothing Prime reads.
-- runner_prediction_snapshots.rank is 0-BASED (rank 0 = Prime's top pick); the challenger's rank is 1-based.
-- Result letters: W won, P placed (not won), L unplaced, null = race not settled yet (no winner recorded).
-- Prices on the pick columns are the morning snapshot price; *_sp is the price the horse returned.
create or replace view public.prime_vs_challenger
with (security_invoker = true) as
with snap as not materialized (
  select distinct on (race_date, race_id, horse_id)
         race_date, race_id, horse_id, horse, rank, velo_prime_prob, sp_dec, course, off_time
  from public.runner_prediction_snapshots
  where race_date >= current_date - 45
  order by race_date, race_id, horse_id, created_at desc
), prime as not materialized (
  select distinct on (race_date, race_id)
         race_date, race_id, horse_id, horse, velo_prime_prob, sp_dec, course, off_time
  from snap
  order by race_date, race_id, rank, velo_prime_prob desc nulls last, horse_id
), priced as not materialized (
  select race_date, race_id, horse_id, horse, sp_dec,
         count(*) over (partition by race_date, race_id, sp_dec) as runners_at_price,
         min(sp_dec) over (partition by race_date, race_id) as best_price
  from snap where sp_dec is not null
), fav as not materialized (
  select distinct on (race_date, race_id)
         race_date, race_id, horse_id, horse, sp_dec, (runners_at_price > 1) as tied
  from priced where sp_dec = best_price
  order by race_date, race_id, horse_id
), ch as not materialized (
  select distinct on (race_date, race_id)
         race_date, race_id, horse_id, challenger_probability, model_version
  from public.rich_context_challenger_scores
  where challenger_rank = 1 and race_date >= current_date - 45
  order by race_date, race_id, scored_at desc
), res as not materialized (
  select run_date, race_id, horse_id, bool_or(is_win) as w, bool_or(is_place) as pl, max(sp_dec) as sp
  from public.racing_horse_runs
  where run_date >= current_date - 45
  group by run_date, race_id, horse_id
), settled as not materialized (
  select run_date, race_id, bool_or(is_win) as done
  from public.racing_horse_runs
  where run_date >= current_date - 45
  group by run_date, race_id
)
select p.race_date, p.race_id, p.course, p.off_time,
       -- Racing Post prints afternoon times without am/pm ("3.00" = 15:00); a one-digit hour is pm.
       case when p.off_time ~ '^[0-9]{1,2}[.:][0-9]{2}$' then
         (case when length(split_part(replace(p.off_time, ':', '.'), '.', 1)) = 1
               then split_part(replace(p.off_time, ':', '.'), '.', 1)::int + 12
               else split_part(replace(p.off_time, ':', '.'), '.', 1)::int end) * 60
         + split_part(replace(p.off_time, ':', '.'), '.', 2)::int
       end as off_minutes,
       p.horse as prime_horse, p.velo_prime_prob as prime_prob, p.sp_dec as prime_price,
       cn.horse as challenger_horse, c.challenger_probability as challenger_prob, cn.sp_dec as challenger_price,
       c.model_version as challenger_model,
       f.horse as favourite_horse, f.sp_dec as favourite_price, f.tied as favourite_tied,
       (p.horse_id = c.horse_id) as agree,
       coalesce(st.done, false) as settled,
       case when st.done then case when pr.w then 'W' when pr.pl then 'P' else 'L' end end as prime_result,
       case when st.done then case when cr.w then 'W' when cr.pl then 'P' else 'L' end end as challenger_result,
       case when st.done then case when fr.w then 'W' when fr.pl then 'P' else 'L' end end as favourite_result,
       pr.sp as prime_sp, cr.sp as challenger_sp, fr.sp as favourite_sp
from prime p
join ch c on c.race_date = p.race_date and c.race_id = p.race_id
join snap cn on cn.race_date = c.race_date and cn.race_id = c.race_id and cn.horse_id = c.horse_id
left join fav f on f.race_date = p.race_date and f.race_id = p.race_id
left join settled st on st.run_date = p.race_date and st.race_id = p.race_id
left join res pr on pr.run_date = p.race_date and pr.race_id = p.race_id and pr.horse_id = p.horse_id
left join res cr on cr.run_date = c.race_date and cr.race_id = c.race_id and cr.horse_id = c.horse_id
left join res fr on fr.run_date = f.race_date and fr.race_id = f.race_id and fr.horse_id = f.horse_id;

revoke all on public.prime_vs_challenger from public, anon, authenticated;
grant select on public.prime_vs_challenger to service_role;

comment on view public.prime_vs_challenger is
  'Prime top pick vs Rich Context challenger top pick per race, with results where settled. Shadow only, read-only.';
