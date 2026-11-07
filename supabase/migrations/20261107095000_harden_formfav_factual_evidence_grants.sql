-- Supabase project defaults grant service_role broad table privileges.
-- Immutable evidence is intentionally limited to append + read.

revoke update, delete, truncate, references, trigger
  on public.formfav_factual_captures from service_role;
revoke update, delete, truncate, references, trigger
  on public.formfav_rich_context_manifests from service_role;

grant select, insert on public.formfav_factual_captures to service_role;
grant select, insert on public.formfav_rich_context_manifests to service_role;

revoke all on public.formfav_factual_captures from anon, authenticated;
revoke all on public.formfav_rich_context_manifests from anon, authenticated;
