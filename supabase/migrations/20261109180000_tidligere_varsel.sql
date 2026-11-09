-- «Slik det ble varslet»: én rad per time med varselet nærmest 24 t før (22–26 t godtas, timesjobben har hull).
-- Lagt i databasen fordi PostgREST gir maks 1000 rader per kall. Felt med flere kjøringer i timen
-- (Pi-testfelt publiseres også ved :15) gikk over grensen, og de nyeste timene forsvant fra nettsiden.
-- Ved lik avstand fra 24 t: korteste ledetid, deretter nyeste kjøring.
begin;

create or replace function public.tidligere_varsel(p_felt text, p_fra timestamptz, p_til timestamptz)
returns table (tid timestamptz, status text, ledetid_timer smallint)
language sql stable set search_path = '' as $$
  select distinct on (v.tid) v.tid, v.status, v.ledetid_timer
  from public.varsel v
  where v.felt = p_felt
    and v.tid >= p_fra
    and v.tid <= p_til
    and v.ledetid_timer between 22 and 26
  order by v.tid, abs(v.ledetid_timer - 24), v.ledetid_timer, v.generert desc;
$$;

revoke execute on function public.tidligere_varsel(text, timestamptz, timestamptz) from public, anon, authenticated;
grant execute on function public.tidligere_varsel(text, timestamptz, timestamptz) to service_role;

commit;
