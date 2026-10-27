-- Arkitektur uten eget API: en GitHub Actions-jobb kjører modellen hver time og skriver hit.
-- Nettsiden (Next.js på Vercel) leser siste varsel og skriver observasjoner via server-ruter med service role.

-- Siste komplette varsel per felt (samme JSON som predict() i Python). Én rad per felt, overskrives hver time.
create table public.varsel_siste (
  felt text primary key,
  generert timestamptz not null,
  data jsonb not null
);
comment on table public.varsel_siste is 'Siste varsel per felt (hele JSON-en fra modellen). Skrives av timesjobben.';
alter table public.varsel_siste enable row level security;

-- Treffsikkerhet for nettsiden uten å hente alle rader.
create or replace function public.treffsikkerhet(p_felt text)
returns jsonb
language sql
stable
security definer
set search_path = ''
as $$
  select jsonb_build_object(
    'antall', count(*),
    'antall_vurdert', count(riktig),
    'andel_riktig', round(avg(case when riktig then 1.0 when riktig is not null then 0.0 end), 3)
  )
  from public.observasjoner
  where felt = p_felt;
$$;
revoke execute on function public.treffsikkerhet(text) from public, anon, authenticated;
grant execute on function public.treffsikkerhet(text) to service_role;

-- Supabase Cron trengs ikke lenger for å kalle et API.
select cron.unschedule('lagre-varsel');
drop function if exists public.lagre_varsel_via_api();
delete from vault.secrets where name = 'klatreforhold_cron_secret';
