-- VELO's own World picks, one row per frozen race (WORLD-PICKS-01).
-- Source: the first-complete, pre-off freeze in world_model_scorecards (model existing_velo_prime_stack),
-- beside the race clock from formfav_races and the settled result from world_sigma_audits when one exists.
-- Read-only, security_invoker, service_role select only. Nothing here feeds Prime and nothing is staked.
--
-- world_model_scorecards.runner_rank is 1-BASED. A race can carry two rank-1 rows (seen on 3 US races on
-- 2026-11-07) and many races tie on score (France, US), so the pick is ordered by rank then score and the
-- view says plainly when it is not a clean read: tied_top, rank1_rows > 1, price_state, pick_is_shortest_price.
create or replace view public.world_velo_picks
with (security_invoker = true) as
with ranked as not materialized (
  select s.race_date, s.provider_race_key, s.country, s.runner_rank, s.horse_name, s.score,
         s.place_prob, s.longshot_prob, s.captured_price, s.identity_grade, s.feature_payload,
         row_number() over (partition by s.race_date, s.provider_race_key
                            order by s.runner_rank asc, s.score desc nulls last, s.horse_name asc) as ord,
         count(*) filter (where s.runner_rank = 1)
           over (partition by s.race_date, s.provider_race_key) as rank1_rows,
         min(s.captured_price) over (partition by s.race_date, s.provider_race_key) as shortest_price
  from public.world_model_scorecards s
  where s.model_name = 'existing_velo_prime_stack'
    and s.freeze_stage = 'FIRST_COMPLETE'
)
select
  t1.race_date,
  t1.provider_race_key,
  t1.country,
  r.track,
  r.race_number,
  r.start_time,
  r.status                                              as race_status,
  (t1.feature_payload ->> 'field_size')::int            as field_size,
  t1.horse_name                                         as pick_name,
  t1.score                                              as pick_score,
  t1.place_prob                                         as pick_place_prob,
  t1.longshot_prob                                      as pick_longshot_prob,
  t1.captured_price                                     as pick_price,
  coalesce(t1.feature_payload ->> 'price_state',
           case when t1.captured_price is null or t1.captured_price = 10 then 'MISSING' else 'UNVERIFIED' end)
                                                        as price_state,
  t1.feature_payload ->> 'race_price_state'             as race_price_state,
  (t1.feature_payload ->> 'priced_runners')::int        as priced_runners,
  t1.feature_payload ->> 'confidence_level'             as confidence_level,
  t2.horse_name                                         as second_name,
  t2.score                                              as second_score,
  t3.horse_name                                         as third_name,
  t3.score                                              as third_score,
  t1.score - t2.score                                   as margin,
  (coalesce((t1.feature_payload ->> 'top_tie_size')::int, 1) > 1
     or t1.score is not distinct from t2.score)         as tied_top,
  t1.rank1_rows,
  t1.identity_grade,
  t1.feature_payload ->> 'code_commit'                  as code_commit,
  res.basis                                             as result_basis,
  res.top1_finish_position                              as finish_position,
  res.top1_win                                          as won,
  res.top1_frame                                        as framed,
  res.winner_names                                      as winner_names,
  -- Where a market exists the VELO World pick is almost always the shortest price (123 of 126 priced
  -- races on 2026-11-07), so a good strike rate there is the favourite's, not evidence of skill.
  (t1.captured_price is not null and t1.captured_price = t1.shortest_price) as pick_is_shortest_price
from ranked t1
left join ranked t2 on t2.race_date = t1.race_date and t2.provider_race_key = t1.provider_race_key and t2.ord = 2
left join ranked t3 on t3.race_date = t1.race_date and t3.provider_race_key = t1.provider_race_key and t3.ord = 3
left join public.formfav_races r on r.provider_race_key = t1.provider_race_key
left join lateral (
  select a.basis, a.top1_finish_position, a.top1_win, a.top1_frame, a.winner_names
  from public.world_sigma_audits a
  where a.provider_race_key = t1.provider_race_key
    and a.model_name = 'existing_velo_prime_stack'
  order by case a.basis when 'final' then 0 when 'provisional' then 1 else 2 end, a.computed_at desc
  limit 1
) res on true
where t1.ord = 1;

revoke all on public.world_velo_picks from public, anon, authenticated;
grant select on public.world_velo_picks to service_role;

comment on view public.world_velo_picks is
  'VELO World top pick per frozen race (existing_velo_prime_stack, FIRST_COMPLETE) with race clock and settled result. Shadow only.';
