# Deploy: Vercel + Supabase + GitHub Actions

Oppdatert mot kodegrunnlaget 30. oktober 2026. Ingen egen API-server i produksjon:
Actions → Python-modell → Supabase → Next.js på Vercel (`web/`).
Denne guiden bekrefter ikke siste produksjonskjøring eller kontoenes aktuelle forbruk.

## Database og timesjobb

Prosjektets Supabase-URL er `https://nmiydpcmfxkhtztzgzfx.supabase.co`.
Kontroller anvendte migrasjoner mot de seks filene i `supabase/migrations/` før en ny installasjon.
V2 krever `20261030090000_modell_v2.sql`, som legger til `modelltilstand` og arkivmetadata.
Tidligere overlevering rapporterer den kjørt 30. oktober 2026. Ikke kjør gamle migrasjoner blindt på nytt.
`20261030180000_vaer_og_rydding.sql` legger til `vaer`, `lagre_vaer()`, `rydd_arkiv()` og cron-jobben
`rydd-arkiv`. Kjør den før koden som skriver `vaer` deployes; uten den får timesjobben `vaer_feil` per felt,
men varselet publiseres likevel. Prøv nye migrasjoner lokalt først (README, «Lokal Supabase»).

Tabeller: `varsel_siste`, `varsel`, `observasjoner`, `stasjon_varsel`, `stasjon_maling`, `modelltilstand`, `vaer`.
RPC-er: `treffsikkerhet(text)`, `statistikk()`, `lagre_vaer(jsonb)` og `rydd_arkiv(integer)`.
RLS begrenser tilgangen til service role.

Sett GitHub Actions-secrets:

| Navn | Bruk |
|---|---|
| `SUPABASE_URL` | Prosjektets URL |
| `SUPABASE_SERVICE_ROLE_KEY` | Servernøkkel for lagring |
| `KLATREFORHOLD_CONTACT` | Kontaktadresse/nettside i MET User-Agent |
| `FROST_CLIENT_ID` | Valgfri innsamling for stasjonskontroll |

Workflowen «Oppdater varsel» kjører `python scripts/publish_forecast.py` fra `modeling/`, med
Python 3.12 og `requirements.txt`. Den har cron `7 * * * *`, manuell start, vær-cache og 15 minutters
tidsgrense. MET Nordic foretrekkes, Open-Meteo gir reserve/historikk, Nowcast gir nærnedbør, og MEPS
gir valgfri usikkerhet. Manglende ensemble skal ikke stoppe hovedvarselet.

Start én jobb manuelt etter publisering og kontroller deretter en ordinær planlagt kjøring.
[GitHub kan forsinke planlagte kjøringer](https://docs.github.com/en/actions/how-tos/troubleshoot-workflows).
I offentlige repo kan planen [deaktiveres etter 60 dager uten aktivitet](https://docs.github.com/en/actions/how-tos/manage-workflow-runs/disable-and-enable-workflows).
`supabase/valgfritt/cron_starter_github_jobb.sql` er et alternativ som utløser Actions; det er ikke
en migrasjon eller en bekreftelse på at alternativet er satt opp.

## Vercel

Importer repoet med **Root Directory: `web`**, rammeverk Next.js. Sett `SUPABASE_URL` og
`SUPABASE_SERVICE_ROLE_KEY` på serveren, aldri med `NEXT_PUBLIC_`. Ikke sett
`KLATREFORHOLD_DATAKILDE=api` i produksjon. Vercel bruker standard Next-output, Docker bruker standalone.
Nettsiden viser felt når jobben har publisert dem i `varsel_siste`.

## Kontroller etter publisering

```sql
select felt, generert, data->>'modellversjon' as modellversjon from public.varsel_siste;
select felt, count(*), max(generert) from public.varsel group by felt;
select felt, max(tid) from public.modelltilstand group by felt;
select count(*) from public.stasjon_maling;
select * from public.observasjoner order by registrert desc limit 10;
```

Forvent ni sistevarsler, modellversjon `2.0.0`, og ferske tidsstempler. Sistevarselet inneholder
121 prognosetidspunkt og 168 historikktimer; arkivet begrenses til ledetider ≤48 timer.
Se datakilder og reserver i payloaden og loggene. Et gammelt-varsel-banner betyr at dataene er
over tre timer gamle; kontroller Actions og lagring før årsaken konkluderes.

## Modeller og kapasitet

Kalibrering/trening kjøres lokalt fra `modeling/` med ekte etiketter. Se [modellguiden](MODELL_V2.md)
for valideringskrav. `calibrate.py --write` skriver bare godkjente forbedringer; `train.py --save`
skriver kandidater med `validated: false`. Modellversjon og konfigurasjonssignatur må stemme.
Timesjobben installerer ikke PyTorch og kan bruke validert sklearn-modell; Docker installerer CPU-torch.

Gratisnivå er ikke en garanti for kapasitet. Se gjeldende [Vercel-grenser](https://vercel.com/docs/limits),
[Supabase-priser](https://supabase.com/pricing) og [GitHub Actions-fakturering](https://docs.github.com/en/billing/concepts/product-billing/github-actions).
Kallmengde og kjøretid avhenger av reservekilder, innkjøring, ensemble og cache.
Med ni felt og opptil 49 arkivrader per time per felt blir det opptil 10 584 rader/døgn, i tillegg til
modelltilstander og stasjonsdata (målt ca. 2.2 MB/døgn, ca. 810 MB/år uten rydding, mot 500 MB gratis).
`rydd_arkiv()` kjører søndager 04:00 UTC: etter 120 dager beholdes ledetid 0, 3, 6, 12, 24 og 48 i `varsel`
og `stasjon_varsel`, pluss alle ledetider ±3 t rundt ekte observasjoner. `modelltilstand` beholder
midnattstilstander i 30 dager. Anslått vekst etterpå er ca. 135 MB/år, så gratisnivået holder i 3-4 år.
Postgres gir ikke plassen tilbake til disken av seg selv, men gjenbruker den, så databasen slutter å vokse.
Se hva som ville blitt slettet uten å slette: `begin; select public.rydd_arkiv(); rollback;`.
