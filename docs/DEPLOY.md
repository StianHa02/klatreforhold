# Deploy: Vercel + Supabase + Raspberry Pi

Ingen egen API-server i produksjon: timesjobb på Raspberry Pi → Python-modell → Supabase → Next.js på Vercel (`web/`).
Oppsettet av Pi-en står i [`drift/raspberrypi/README.md`](../drift/raspberrypi/README.md). GitHub Actions er reserve, startet av Supabase Cron når Pi-en har stoppet.

## Database og timesjobb

Prosjektets Supabase-URL er `https://nmiydpcmfxkhtztzgzfx.supabase.co`.
Kontroller anvendte migrasjoner mot de ti filene i `supabase/migrations/` før en ny installasjon.
V2 krever `20261030090000_modell_v2.sql`, som legger til `modelltilstand` og arkivmetadata.
Ikke kjør gamle migrasjoner blindt på nytt.
`20261030180000_vaer_og_rydding.sql` legger til `vaer`, `lagre_vaer()`, `rydd_arkiv()` og cron-jobben
`rydd-arkiv`. Kjør den før koden som skriver `vaer` deployes; uten den får timesjobben `vaer_feil` per felt,
men varselet publiseres likevel. Prøv nye migrasjoner lokalt først (README, «Lokal Supabase»).
`20261031210000_bones_maling.sql` legger til `bones_maling` for målingene fra Bønes værstasjon
([vurderingen](BONES_STASJON.md)). Uten den får timesjobben en advarsel i `_bones`, og varselet publiseres som før.
`20261105150000_parquet_arkiv.sql` legger til `arkiv_eksport`, den private Storage-bøtta `arkiv` og en
`rydd_arkiv()` som bare sletter døgn som er eksportert til Parquet ([Parquet-arkivet](ARKIV.md)).
`20261113120000_varsel_p_tort.sql` legger til kolonnen `varsel.p_tort` (MEPS-andelen). Kjør den før koden som
skriver `p_tort` deployes: uten kolonnen avviser PostgREST arkivradene, og timesjobben feiler for alle felt.

Tabeller: `varsel_siste`, `varsel`, `observasjoner`, `stasjon_varsel`, `stasjon_maling`, `modelltilstand`, `vaer`,
`bones_maling`, `arkiv_eksport`. Storage: den private bøtta `arkiv` (Parquet-arkivet).
RPC-er: `treffsikkerhet(text)`, `statistikk()`, `lagre_vaer(jsonb)`, `rydd_arkiv(integer)` og `tidligere_varsel(text, timestamptz, timestamptz)`.
RLS begrenser tilgangen til service role.

Timesjobben trenger disse verdiene, i `.env` på Pi-en og som GitHub Actions-secrets for reserven:

| Navn | Bruk |
|---|---|
| `SUPABASE_URL` | Prosjektets URL |
| `SUPABASE_SERVICE_ROLE_KEY` | Servernøkkel for lagring |
| `KLATREFORHOLD_CONTACT` | Kontaktadresse/nettside i MET User-Agent |
| `FROST_CLIENT_ID` | Valgfri innsamling for stasjonskontroll |

Pi-en kjører `python scripts/publish_forecast.py` fra `modeling/` med en systemd-timer ved :07 hver time,
henter siste kode fra `main` før hver kjøring og har 15 minutters tidsgrense. Reserven, workflowen
«Oppdater varsel», gjør det samme med Python 3.12, men startes bare for hånd eller av reserven. MET Nordic foretrekkes, Open-Meteo gir reserve/historikk, Nowcast gir nærnedbør, og MEPS
gir valgfri usikkerhet. Manglende ensemble skal ikke stoppe hovedvarselet.

Start én jobb manuelt (`sudo systemctl start klatreforhold-varsel.service`) og kontroller deretter en
ordinær planlagt kjøring. Planlagte kjøringer i Actions ble flyttet til Pi-en fordi
[GitHub kan forsinke dem](https://docs.github.com/en/actions/how-tos/troubleshoot-workflows).
`supabase/valgfritt/cron_starter_github_jobb.sql` (satt opp i produksjon som `start-varsel-jobb`) er reserven:
hver time ved :05 starter den Actions bare hvis nyeste `generert` i `varsel_siste` er eldre enn 90 minutter.
Til Pi-en kjører, står den i overgangsmodus og starter Actions hver time; se «Bytt til reservemodus» i
[Pi-oppsettet](../drift/raspberrypi/README.md).

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
over tre timer gamle; kontroller Pi-en (`journalctl -u klatreforhold-varsel`) og lagring før årsaken konkluderes.

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
`rydd_arkiv()` kjører søndager 04:00 UTC: etter 30 dager beholdes ledetid 0, 3, 6, 12, 24 og 48 i `varsel`
og `stasjon_varsel`, pluss alle ledetider ±3 t rundt ekte observasjoner. Den sletter bare døgn som Pi-en har
eksportert til Parquet og kontrollert (`arkiv_eksport`), så alle rader finnes fortsatt i
[Parquet-arkivet](ARKIV.md). Storage-gratisnivået (1 GB) er en egen kvote ved siden av databasen. `modelltilstand` beholder
midnattstilstander i 30 dager. Anslått vekst etterpå er ca. 135 MB/år, så gratisnivået holder i 3-4 år.
Postgres gir ikke plassen tilbake til disken av seg selv, men gjenbruker den, så databasen slutter å vokse.
Se hva som ville blitt slettet uten å slette: `begin; select public.rydd_arkiv(); rollback;`.
