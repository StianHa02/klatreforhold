-- 1) vaer: været modellen faktisk brukte, per felt og time (bare timer som er passert). Gjør treningen
--    uavhengig av en lokal vær-CSV, og trening ser samme input som timesjobben.
-- 2) rydd_arkiv(): holder varsel, stasjon_varsel og modelltilstand innenfor gratisnivået (500 MB)
--    uten å kaste rader som trengs til trening eller treff per ledetid.
-- 3) Eksplisitte rettigheter for service_role på de gamle tabellene. Produksjonen fikk dem fra Supabases
--    gamle standardrettigheter; nyere Supabase (bl.a. lokal CLI) gir bare DELETE/TRUNCATE, så timesjobben
--    fikk 403 mot en ny database. Ingen endring i produksjonen, der rettighetene alt finnes.
begin;

grant select, insert, update, delete on public.observasjoner, public.varsel, public.varsel_siste,
  public.stasjon_maling, public.stasjon_varsel to service_role;

-- Kolonnenavnene er de samme som i værtabellen i Python (predict.get_weather), så en rad kan spilles
-- rett inn i run_model uten oversetting. Én hel time kommer alltid fra én kilde (se lagre_vaer).
create table if not exists public.vaer (
  felt text not null,
  tid timestamptz not null,
  generert timestamptz not null,
  air_temperature real,
  relative_humidity real,
  dew_point_2m real,
  precipitation real,
  cloud_cover real,
  ghi real,
  dni real,
  dhi real,
  longwave_down real,
  wind_speed real,
  wind_direction real,
  snow_probability real,
  snow_water_mm real,
  weather_source text,
  weather_kind text,
  weather_issued timestamptz,
  precipitation_source text,
  primary key (felt, tid)
);
comment on table public.vaer is 'Værinput til modellen per felt og passert time. Skrives av timesjobben via lagre_vaer(). Treningsdata.';
alter table public.vaer enable row level security;
revoke all on public.vaer from anon, authenticated;
grant all on public.vaer to service_role;

-- Nyere kjøringer oppdaterer timen (Open-Meteo retter seg), men en MET Nordic-analyse byttes bare
-- mot en nyere analyse, aldri mot reservevær fra en kjøring der direkte MET var nede.
create or replace function public.lagre_vaer(rader jsonb)
returns integer
language sql
security definer
set search_path = ''
as $$
  with lagret as (
    insert into public.vaer
    select * from jsonb_populate_recordset(null::public.vaer, rader)
    on conflict (felt, tid) do update set
      generert = excluded.generert, air_temperature = excluded.air_temperature,
      relative_humidity = excluded.relative_humidity, dew_point_2m = excluded.dew_point_2m,
      precipitation = excluded.precipitation, cloud_cover = excluded.cloud_cover, ghi = excluded.ghi,
      dni = excluded.dni, dhi = excluded.dhi, longwave_down = excluded.longwave_down,
      wind_speed = excluded.wind_speed, wind_direction = excluded.wind_direction,
      snow_probability = excluded.snow_probability, snow_water_mm = excluded.snow_water_mm,
      weather_source = excluded.weather_source, weather_kind = excluded.weather_kind,
      weather_issued = excluded.weather_issued, precipitation_source = excluded.precipitation_source
    where public.vaer.weather_kind is distinct from 'analysis' or excluded.weather_kind = 'analysis'
    returning 1
  )
  select count(*)::integer from lagret;
$$;
revoke execute on function public.lagre_vaer(jsonb) from public, anon, authenticated;
grant execute on function public.lagre_vaer(jsonb) to service_role;

-- Etter p_dager beholdes bare ledetidene treff per ledetid og verify.py bruker (0, 3, 6, 12, 24, 48),
-- pluss alle ledetider rundt en ekte observasjon (trening, evaluate.py, nettsidens predikert_status).
-- Nettsiden leser bare de siste 7 døgnene og observasjoner opptil 13 dager bak, godt innenfor 120.
-- Modelltilstand: timesjobben trenger bare den siste før nå - 8 døgn; midnattstilstander holder.
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
    and not exists (
      select 1 from public.observasjoner o
      where o.felt = v.felt and o.kilde not in ('dev', 'test')
        and v.tid between o.tid - interval '3 hours' and o.tid + interval '3 hours');
  get diagnostics n_varsel = row_count;

  delete from public.stasjon_varsel s
  where s.generert < grense and s.ledetid_timer not in (0, 3, 6, 12, 24, 48);
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

-- Søndager 04:00 UTC, etter rydd-cron-historikk. Samme navn på nytt oppdaterer jobben.
select cron.schedule('rydd-arkiv', '0 4 * * 0', 'select public.rydd_arkiv()');

notify pgrst, 'reload schema';
commit;
