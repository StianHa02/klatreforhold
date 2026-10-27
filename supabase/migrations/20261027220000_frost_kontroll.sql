-- Kontroll av værvarselet mot målestasjoner (Frost). Varselet lagres for stasjonens egne koordinater,
-- så vi måler varselets feil og ikke forskjellen mellom to steder.

create table public.stasjon_maling (
  stasjon text not null,
  tid timestamptz not null,
  lufttemp real,
  luftfuktighet real,
  nedbor_mm real,
  vind_ms real,
  vindretning real,
  primary key (stasjon, tid)
);
comment on table public.stasjon_maling is 'Timesmålinger fra Frost for stasjonene feltene kontrolleres mot.';
alter table public.stasjon_maling enable row level security;

create table public.stasjon_varsel (
  stasjon text not null,
  generert timestamptz not null,
  tid timestamptz not null,
  ledetid_timer smallint not null,
  lufttemp real,
  luftfuktighet real,
  nedbor_mm real,
  vind_ms real,
  vindretning real,
  primary key (stasjon, generert, tid)
);
comment on table public.stasjon_varsel is 'Værvarselet (MET Nordic via Open-Meteo) for stasjonens koordinater, slik det så ut hver time.';
create index stasjon_varsel_tid_idx on public.stasjon_varsel (stasjon, tid);
alter table public.stasjon_varsel enable row level security;
