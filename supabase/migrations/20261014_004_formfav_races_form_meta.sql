-- Race-level /v1/form fields were stored inside formfav_races.metadata, which the
-- live worker rewrites every tick with the bare meeting-race dict, so they were
-- lost within a minute. Give them their own column.
alter table public.formfav_races add column if not exists form_meta jsonb;
comment on column public.formfav_races.form_meta is 'Race-level fields from FormFav /v1/form (everything except runners). Kept apart from metadata, which the worker rewrites each tick with the meeting-race dict.';
