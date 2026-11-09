-- Durable, append-only storage for the exact v2 vector contract attached to
-- each Rich Context evidence packet. Existing rows remain truthful nulls.
alter table public.rich_context_shadow_packets
  add column if not exists enriched_feature_contract jsonb;

comment on column public.rich_context_shadow_packets.enriched_feature_contract is
  'Fixed-schema, leakage-checked Rich Context v2 vector, coverage and missingness. Shadow only.';

revoke update (enriched_feature_contract) on public.rich_context_shadow_packets
  from public, anon, authenticated, service_role;
