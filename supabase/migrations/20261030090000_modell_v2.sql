-- Kjør før v2-timesjobben. Ingen endring i gamle prognoser eller nettførerens database.
begin;
alter table public.observasjoner drop constraint if exists observasjoner_status_check;
alter table public.observasjoner add constraint observasjoner_status_check
  check (status in ('tort', 'fuktig', 'vatt', 'is'));
alter table public.varsel add column if not exists modellversjon text;
alter table public.varsel add column if not exists konfigurasjon text;
alter table public.varsel add column if not exists is_mm real;
alter table public.varsel add column if not exists sno_mm real;
alter table public.varsel add column if not exists vaerkilde text;
create table if not exists public.modelltilstand (
  felt text not null,
  tid timestamptz not null,
  model_version text not null,
  config_hash text not null,
  state jsonb not null,
  primary key (felt, tid, config_hash)
);
alter table public.modelltilstand enable row level security;
revoke all on public.modelltilstand from anon, authenticated;
grant all on public.modelltilstand to service_role;
create or replace function public.statistikk()
returns jsonb language sql stable security definer set search_path = '' as $$
  with obs as (
    select felt, count(*) as antall,
      count(*) filter (where status = 'tort') as tort,
      count(*) filter (where status = 'fuktig') as fuktig,
      count(*) filter (where status = 'vatt') as vatt,
      count(*) filter (where status = 'is') as is_antall,
      count(riktig) as vurdert,
      round(avg(case when riktig then 1.0 when riktig is not null then 0.0 end), 3) as andel_riktig
    from public.observasjoner where kilde not in ('dev', 'test') group by felt
  ), arkiv as (
    select felt, count(distinct generert) as kjoringer, min(generert) as forste, max(generert) as siste
    from public.varsel group by felt
  )
  select jsonb_build_object('felt', coalesce(jsonb_agg(jsonb_build_object(
    'felt', a.felt, 'observasjoner', coalesce(o.antall, 0), 'tort', coalesce(o.tort, 0),
    'fuktig', coalesce(o.fuktig, 0), 'vatt', coalesce(o.vatt, 0), 'is', coalesce(o.is_antall, 0),
    'vurdert', coalesce(o.vurdert, 0), 'andel_riktig', o.andel_riktig,
    'kjoringer', a.kjoringer, 'forste_varsel', a.forste, 'siste_varsel', a.siste
  ) order by a.felt), '[]'::jsonb)) from arkiv a left join obs o on o.felt = a.felt;
$$;
revoke execute on function public.statistikk() from public, anon, authenticated;
grant execute on function public.statistikk() to service_role;
notify pgrst, 'reload schema';
commit;
