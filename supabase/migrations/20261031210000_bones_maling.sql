-- Målinger fra Bønes værstasjon (privat, weather.kippenbroeck.no, CC BY 4.0), 1,3 km fra Ekstraveggen.
-- API-et gir bare siste femminuttsmåling, så timesjobben lagrer én rad per kjøring. Timeverdiene regnes ut
-- i Python (data/bones.py). Én rad i timen er under 10 000 rader i året, så tabellen ryddes ikke.
begin;

create table if not exists public.bones_maling (
  tid timestamptz primary key,
  hentet timestamptz not null default now(),
  lufttemp real,
  luftfuktighet real,
  vind_ms real,
  vindkast_ms real,
  vindretning real,
  nedbor_i_dag_mm real,
  nedbor_dato date not null,
  nedbor_intensitet_mm_t real
);
comment on table public.bones_maling is 'Siste måling fra Bønes værstasjon per kjøring av timesjobben. tid er slutten av femminuttsintervallet (UTC). nedbor_dato er døgnet nedbor_i_dag_mm gjelder.';
alter table public.bones_maling enable row level security;
revoke all on public.bones_maling from anon, authenticated;
grant all on public.bones_maling to service_role;

notify pgrst, 'reload schema';
commit;
