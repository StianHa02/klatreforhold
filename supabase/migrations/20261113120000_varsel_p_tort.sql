-- MEPS-andelen p_tort (andel ensemblemedlemmer som gir tørt berg) arkiveres per time og ledetid.
-- Den kan ikke regnes ut i ettertid: MEPS-prognosene lagres ikke, bare været som faktisk kom (vaer).
-- Kjør før koden som skriver p_tort til varsel deployes; uten kolonnen avviser PostgREST hele arkivraden
-- og timesjobben feiler for alle felt.
-- Null betyr uten ensemble (kildefeil, eldre kjøring) eller time etter ensemblets slutt. Ukalibrert.
begin;

alter table public.varsel add column if not exists p_tort real;
comment on column public.varsel.p_tort is
  'Andel MEPS-medlemmer som gir tørt berg (0-1). Ukalibrert; null uten ensemble eller etter dekningsslutt.';

commit;
