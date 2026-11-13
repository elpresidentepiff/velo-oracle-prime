-- #189: FormFav EOD quarantines races whose clock, racecard and field cannot be proved to be one
-- race (US local-date vs UTC key collision, Remington Park R4 12 Nov 2026). Such rows are written
-- with basis 'identity_blocked' so they stay visible but never enter formfav_sigma_daily strike
-- rates as final/provisional. Same basis world_sigma_audits already allows.
-- Apply BEFORE deploying the FormFav worker that writes it, or its EOD upsert is rejected.
alter table public.formfav_sigma_audits drop constraint if exists formfav_sigma_audits_basis_check;
alter table public.formfav_sigma_audits
  add constraint formfav_sigma_audits_basis_check
  check (basis = any (array['final'::text, 'provisional'::text, 'no_result'::text, 'identity_blocked'::text]));
