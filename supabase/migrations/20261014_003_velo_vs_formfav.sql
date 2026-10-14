-- VELO vs FormFav, one row per GB/IE race that has both. READ-ONLY comparison:
-- nothing here feeds VELO scoring (shadow rules unchanged). Join key is course
-- + UK off time + date (verified 39/39 on 2026-10-14). Horse names are matched
-- after stripping any "(IRE)"-style suffix and punctuation.
create or replace view public.velo_vs_formfav
with (security_invoker = true) as
with velo_latest as (
    select distinct on (race_id)
        race_id, generated_at, confidence_level as velo_confidence,
        decision_tier as velo_tier, full_analysis
    from public.velo_verdicts
    where full_analysis ? 'predictions'
    order by race_id, generated_at desc
),
velo_ranked as (
    select
        vl.race_id,
        p->>'horse'                                             as horse,
        lower(regexp_replace(regexp_replace(p->>'horse', '\s*\([^)]*\)', '', 'g'),
              '[^a-zA-Z0-9]', '', 'g'))                         as horse_key,
        (p->>'velo_prime_prob')::numeric                        as vp,
        row_number() over (partition by vl.race_id
                           order by (p->>'velo_prime_prob')::numeric desc nulls last) as velo_rank
    from velo_latest vl, jsonb_array_elements(vl.full_analysis->'predictions') p
),
ff_ranked as (
    select
        fp.provider_race_key,
        e->>'name'                                              as horse,
        lower(regexp_replace(regexp_replace(e->>'name', '\s*\([^)]*\)', '', 'g'),
              '[^a-zA-Z0-9]', '', 'g'))                         as horse_key,
        (e->>'winProb')::numeric                                as ff_win_prob,
        (e->>'modelRank')::int                                  as ff_rank
    from public.formfav_predictions fp, jsonb_array_elements(fp.predictions_payload->'predictions') e
),
pair as (
    select vl.race_id, fr.provider_race_key, r.course, r.date as race_date, r.time as off_time,
           vl.velo_confidence, vl.velo_tier, fp.confidence as ff_confidence, fp.model_version as ff_model_version
    from velo_latest vl
    join public.races r on r.race_id = vl.race_id
    join public.formfav_races fr
      on fr.race_date = r.date
     and lower(fr.track) = lower(r.course)
     and (fr.start_time at time zone 'Europe/London')::time = r.time::time
    join public.formfav_predictions fp on fp.provider_race_key = fr.provider_race_key
),
winner as (
    select x.provider_race_key,
           x.interim,
           (array_agg(lower(regexp_replace(regexp_replace(pl->>'name', '\s*\([^)]*\)', '', 'g'),
                  '[^a-zA-Z0-9]', '', 'g')))
               filter (where (pl->>'position')::int = 1 and coalesce((pl->>'scratched')::bool, false) = false))[1] as winner_key,
           (array_agg(pl->>'name')
               filter (where (pl->>'position')::int = 1 and coalesce((pl->>'scratched')::bool, false) = false))[1] as winner_name
    from public.formfav_results x, jsonb_array_elements(x.results_payload->'placings') pl
    group by x.provider_race_key, x.interim
)
select
    p.race_date,
    p.course,
    p.off_time,
    p.race_id,
    p.provider_race_key,
    vt.horse                                       as velo_top_horse,
    vt.vp                                          as velo_top_prob,
    p.velo_confidence,
    p.velo_tier,
    ft.horse                                       as formfav_top_horse,
    ft.ff_win_prob                                 as formfav_top_prob,
    p.ff_confidence                                as formfav_confidence,
    (vt.horse_key = ft.horse_key)                  as agree_on_top_pick,
    fv.ff_win_prob                                 as formfav_prob_on_velo_pick,
    fv.ff_rank                                     as formfav_rank_of_velo_pick,
    vf.vp                                          as velo_prob_on_formfav_pick,
    vf.velo_rank                                   as velo_rank_of_formfav_pick,
    w.winner_name,
    case when w.winner_key is null then null else not w.interim end as result_is_final,
    case when w.winner_key is null then null else vt.horse_key = w.winner_key end as velo_pick_won,
    case when w.winner_key is null then null else ft.horse_key = w.winner_key end as formfav_pick_won,
    p.ff_model_version
from pair p
join velo_ranked vt on vt.race_id = p.race_id and vt.velo_rank = 1
join ff_ranked  ft on ft.provider_race_key = p.provider_race_key and ft.ff_rank = 1
left join ff_ranked  fv on fv.provider_race_key = p.provider_race_key and fv.horse_key = vt.horse_key
left join velo_ranked vf on vf.race_id = p.race_id and vf.horse_key = ft.horse_key
left join winner w on w.provider_race_key = p.provider_race_key;
