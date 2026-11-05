-- VALGFRITT, ikke en migrasjon. Kjør selv i Supabase SQL Editor. Satt opp i produksjon (jobben 'start-varsel-jobb').
-- Lag først et fine-grained token på GitHub (kun dette repoet, Actions: Read and write) og legg det i Vault:
--   select vault.create_secret('<token>', 'github_dispatch_token');

-- Reserve for timesjobben på Raspberry Pi-en (drift/raspberrypi/). Supabase Cron sjekker hver time ved :05
-- om varselet er ferskt. Er det nyeste varselet i varsel_siste eldre enn p_maks_alder (standard 90 minutter),
-- har Pi-en hoppet over minst én kjøring (den kjører ved :07), og workflowen «Oppdater varsel» startes via
-- GitHub-API-et. Ellers gjør jobben ingenting, så hver time publiseres bare én gang. GitHubs egen timeplan
-- brukes ikke: den kan bli forsinket i timevis. Uten token gjør jobben ingenting.
--
-- To moduser, valgt i cron-kommandoen nederst:
--   start_varsel_jobb(interval '0 minutes')  Actions hver time (overgang, før Pi-en kjører)  <- nå
--   start_varsel_jobb()                      reserve: bare når varselet er over 90 min gammelt

drop function if exists public.start_varsel_jobb();
create or replace function public.start_varsel_jobb(p_maks_alder interval default interval '90 minutes')
returns bigint
language plpgsql
security definer
set search_path = ''
as $$
declare
  token text;
  request_id bigint;
begin
  if (select max(generert) from public.varsel_siste) > now() - p_maks_alder then
    return null;  -- Pi-en publiserer, ingen reserve nødvendig
  end if;
  select decrypted_secret into token from vault.decrypted_secrets where name = 'github_dispatch_token';
  if token is null then
    raise notice 'klatreforhold: mangler github_dispatch_token i Vault, hopper over';
    return null;
  end if;
  select net.http_post(
    url := 'https://api.github.com/repos/StianHa02/klatreforhold/actions/workflows/varsel.yml/dispatches',
    headers := jsonb_build_object(
      'Authorization', 'Bearer ' || token,
      'Accept', 'application/vnd.github+json',
      'X-GitHub-Api-Version', '2022-11-28',
      'User-Agent', 'klatreforhold-supabase-cron'
    ),
    body := '{"ref": "main"}'::jsonb,
    timeout_milliseconds := 10000
  ) into request_id;
  return request_id;
end;
$$;

revoke execute on function public.start_varsel_jobb(interval) from public, anon, authenticated;

-- Overgang: Actions hver time til Pi-en kjører. Samme navn på nytt oppdaterer jobben.
select cron.schedule('start-varsel-jobb', '5 * * * *', $c$select public.start_varsel_jobb(interval '0 minutes')$c$);

-- Når Pi-en har publisert et par timer på rad (se drift/raspberrypi/README.md, «Bytt til reservemodus»):
-- select cron.schedule('start-varsel-jobb', '5 * * * *', 'select public.start_varsel_jobb()');
