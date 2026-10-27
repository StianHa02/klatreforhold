-- Aggregater til "Om modellen"-siden: observasjoner per felt (uten dev/test) og størrelsen på varselarkivet.
create or replace function public.statistikk()
returns jsonb
language sql
stable
security definer
set search_path = ''
as $$
  with obs as (
    select felt,
           count(*) as antall,
           count(*) filter (where status = 'tort') as tort,
           count(*) filter (where status = 'fuktig') as fuktig,
           count(*) filter (where status = 'vatt') as vatt,
           count(riktig) as vurdert,
           round(avg(case when riktig then 1.0 when riktig is not null then 0.0 end), 3) as andel_riktig
    from public.observasjoner
    where kilde not in ('dev', 'test')
    group by felt
  ),
  arkiv as (
    select felt, count(distinct generert) as kjoringer, min(generert) as forste, max(generert) as siste
    from public.varsel
    group by felt
  )
  select jsonb_build_object(
    'felt', coalesce(jsonb_agg(jsonb_build_object(
      'felt', a.felt,
      'observasjoner', coalesce(o.antall, 0), 'tort', coalesce(o.tort, 0), 'fuktig', coalesce(o.fuktig, 0),
      'vatt', coalesce(o.vatt, 0), 'vurdert', coalesce(o.vurdert, 0), 'andel_riktig', o.andel_riktig,
      'kjoringer', a.kjoringer, 'forste_varsel', a.forste, 'siste_varsel', a.siste
    ) order by a.felt), '[]'::jsonb)
  )
  from arkiv a left join obs o on o.felt = a.felt;
$$;
revoke execute on function public.statistikk() from public, anon, authenticated;
grant execute on function public.statistikk() to service_role;
