-- VALGFRITT, ikke kjørt. Kjør selv i Supabase SQL Editor hvis GitHubs timeplan er for upålitelig.
-- Lag først et fine-grained token på GitHub (kun dette repoet, Actions: Read and write) og legg det i Vault:
--   select vault.create_secret('<token>', 'github_dispatch_token');
-- Sett så GitHub-timeplanen i .github/workflows/varsel.yml til sjeldnere (f.eks. hver 3. time) som reserve.

-- GitHubs egen timeplan ("schedule") er upålitelig for nye repoer (kan bli forsinket i timevis).
-- Supabase Cron starter derfor workflowen "Oppdater varsel" presist hvert time via GitHub-API-et.
-- Tokenet (fine-grained PAT med Actions: Read and write på repoet) legges i Vault som 'github_dispatch_token'.
-- Uten token gjør jobben ingenting.

create or replace function public.start_varsel_jobb()
returns bigint
language plpgsql
security definer
set search_path = ''
as $$
declare
  token text;
  request_id bigint;
begin
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

revoke execute on function public.start_varsel_jobb() from public, anon, authenticated;

select cron.schedule('start-varsel-jobb', '5 * * * *', 'select public.start_varsel_jobb()');
