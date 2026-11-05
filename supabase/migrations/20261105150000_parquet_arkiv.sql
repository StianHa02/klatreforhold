-- Parquet-arkiv: varselarkivet slettes ikke lenger før det er tatt vare på.
-- 1) arkiv_eksport: kvittering per tabell og UTC-døgn (etter `generert`) som er eksportert til Parquet,
--    lastet opp til Storage-bøtta `arkiv` og kontrollert (sha256 av fila lastet ned igjen).
--    Skrives av modeling/scripts/eksporter_arkiv.py (systemd-timer på Raspberry Pi-en).
-- 2) Privat Storage-bøtte `arkiv` for Parquet-filene (bare service role).
-- 3) rydd_arkiv(): sletter varsel og stasjon_varsel bare for døgn som har en kvittering, så ingen rad
--    forsvinner fra databasen uten å finnes i Parquet-arkivet. Modelltilstand ryddes som før: den er et
--    omstartspunkt for modellen og kan regnes ut på nytt fra `vaer`, som aldri ryddes.
begin;

create table if not exists public.arkiv_eksport (
  tabell text not null check (tabell in ('varsel', 'stasjon_varsel')),
  dato date not null,                   -- UTC-døgn for `generert`
  rader integer not null check (rader >= 0),
  fil text not null,                    -- sti i bøtta `arkiv`, f.eks. varsel/2026-11/varsel_2026-11-04.parquet
  bytes integer not null,
  sha256 text not null,
  eksportert timestamptz not null default now(),
  primary key (tabell, dato)
);
alter table public.arkiv_eksport enable row level security;
grant select, insert, update, delete on public.arkiv_eksport to service_role;

insert into storage.buckets (id, name, public)
values ('arkiv', 'arkiv', false)
on conflict (id) do nothing;

-- Som før: etter p_dager beholdes bare ledetidene 0, 3, 6, 12, 24 og 48 og rader rundt en ekte observasjon.
-- Nytt: en rad slettes bare hvis døgnet dens finnes i arkiv_eksport (og dermed i Parquet med alle ledetider).
create or replace function public.rydd_arkiv(p_dager integer default 120)
returns jsonb
language plpgsql
security definer
set search_path = ''
as $$
declare
  grense timestamptz := now() - make_interval(days => p_dager);
  n_varsel bigint;
  n_stasjon bigint;
  n_tilstand bigint;
begin
  delete from public.varsel v
  where v.generert < grense
    and v.ledetid_timer not in (0, 3, 6, 12, 24, 48)
    and exists (
      select 1 from public.arkiv_eksport e
      where e.tabell = 'varsel' and e.dato = (v.generert at time zone 'UTC')::date)
    and not exists (
      select 1 from public.observasjoner o
      where o.felt = v.felt and o.kilde not in ('dev', 'test')
        and v.tid between o.tid - interval '3 hours' and o.tid + interval '3 hours');
  get diagnostics n_varsel = row_count;

  delete from public.stasjon_varsel s
  where s.generert < grense and s.ledetid_timer not in (0, 3, 6, 12, 24, 48)
    and exists (
      select 1 from public.arkiv_eksport e
      where e.tabell = 'stasjon_varsel' and e.dato = (s.generert at time zone 'UTC')::date);
  get diagnostics n_stasjon = row_count;

  delete from public.modelltilstand m
  where m.tid < now() - interval '30 days'
     or (m.tid < now() - interval '2 days' and extract(hour from m.tid at time zone 'UTC') <> 0);
  get diagnostics n_tilstand = row_count;

  return jsonb_build_object('varsel', n_varsel, 'stasjon_varsel', n_stasjon, 'modelltilstand', n_tilstand);
end;
$$;
revoke execute on function public.rydd_arkiv(integer) from public, anon, authenticated;
grant execute on function public.rydd_arkiv(integer) to service_role;

notify pgrst, 'reload schema';
commit;
