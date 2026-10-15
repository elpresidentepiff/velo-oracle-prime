-- FormFav's own top-3 per race, flattened for the dashboard. NOT a VELO selection.
create or replace view public.formfav_race_picks
with (security_invoker = true) as
select
    r.race_date,
    r.country,
    r.track,
    r.race_number,
    r.start_time,
    to_char(r.start_time at time zone 'Europe/London', 'HH24:MI') as off_uk,
    r.metadata->>'raceClass'  as race_class,
    r.metadata->>'distance'   as distance,
    p.confidence,
    p.model_version,
    p.captured_at,
    jsonb_array_length(p.predictions_payload->'predictions') as field_size,
    (select count(*) from public.formfav_runner_form f
      where f.provider_race_key = r.provider_race_key and f.scratched) as scratched,
    t1.name as pick1_name, t1.num as pick1_number, t1.win as pick1_win, t1.plc as pick1_place,
    t2.name as pick2_name, t2.num as pick2_number, t2.win as pick2_win,
    t3.name as pick3_name, t3.num as pick3_number, t3.win as pick3_win
from public.formfav_races r
join public.formfav_predictions p using (provider_race_key)
left join lateral (select e->>'name' name, (e->>'number')::int num, (e->>'winProb')::numeric win, (e->>'placeProb')::numeric plc
                   from jsonb_array_elements(p.predictions_payload->'predictions') e where (e->>'modelRank')::int = 1 limit 1) t1 on true
left join lateral (select e->>'name' name, (e->>'number')::int num, (e->>'winProb')::numeric win
                   from jsonb_array_elements(p.predictions_payload->'predictions') e where (e->>'modelRank')::int = 2 limit 1) t2 on true
left join lateral (select e->>'name' name, (e->>'number')::int num, (e->>'winProb')::numeric win
                   from jsonb_array_elements(p.predictions_payload->'predictions') e where (e->>'modelRank')::int = 3 limit 1) t3 on true;
