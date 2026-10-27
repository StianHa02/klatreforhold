-- klatreforhold: tilbakemeldinger fra brukere og arkiv av varsler.
-- Kun API-et (service role) leser/skriver. RLS er på uten policyer, så anon/authenticated får ingen tilgang.

create table public.observasjoner (
  id bigint generated always as identity primary key,
  felt text not null,
  tid timestamptz not null,
  status text not null check (status in ('tort', 'fuktig', 'vatt')),
  predikert_status text check (predikert_status in ('tort', 'fuktig', 'vatt', 'is')),
  riktig boolean,
  kommentar text check (char_length(kommentar) <= 500),
  kilde text not null default 'web',
  registrert timestamptz not null default now()
);
comment on table public.observasjoner is 'Brukernes observasjoner av forholdene (tørt/fuktig/vått). Treningsdata.';
create index observasjoner_felt_tid_idx on public.observasjoner (felt, tid desc);
alter table public.observasjoner enable row level security;

create table public.varsel (
  felt text not null,
  generert timestamptz not null,
  tid timestamptz not null,
  ledetid_timer smallint not null,
  status text not null check (status in ('tort', 'fuktig', 'vatt', 'is')),
  vann_mm real,
  p_vatt real,
  bergtemp real,
  duggpunkt real,
  nedbor_mm real,
  regn_mot_veggen_mm real,
  sol_pa_veggen boolean,
  primary key (felt, generert, tid)
);
comment on table public.varsel is 'Arkiv: varselet slik det så ut hver time. Brukes til å måle treffsikkerhet per ledetid.';
create index varsel_felt_tid_idx on public.varsel (felt, tid);
alter table public.varsel enable row level security;

-- Timesjobb: Supabase Cron kaller API-et, som lagrer varselet i public.varsel.
-- URL og hemmelighet ligger i Vault (settes etter at API-et er deployet, se README).
create extension if not exists pg_cron;
create extension if not exists pg_net with schema extensions;

create or replace function public.lagre_varsel_via_api()
returns bigint
language plpgsql
security definer
set search_path = ''
as $$
declare
  api_url text;
  hemmelighet text;
  request_id bigint;
begin
  select decrypted_secret into api_url from vault.decrypted_secrets where name = 'klatreforhold_api_url';
  select decrypted_secret into hemmelighet from vault.decrypted_secrets where name = 'klatreforhold_cron_secret';
  if api_url is null or hemmelighet is null then
    raise notice 'klatreforhold: mangler Vault-secrets, hopper over';
    return null;
  end if;
  select net.http_post(
    url := api_url || '/api/cron/lagre-varsel',
    headers := jsonb_build_object('Content-Type', 'application/json', 'Authorization', 'Bearer ' || hemmelighet),
    body := '{}'::jsonb,
    timeout_milliseconds := 120000
  ) into request_id;
  return request_id;
end;
$$;

revoke execute on function public.lagre_varsel_via_api() from public, anon, authenticated;

select cron.schedule('lagre-varsel', '7 * * * *', 'select public.lagre_varsel_via_api()');
select cron.schedule('rydd-cron-historikk', '30 3 * * 0',
  $$delete from cron.job_run_details where end_time < now() - interval '14 days'$$);
