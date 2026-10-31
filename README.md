# klatreforhold

Timevarsel for tørt, fuktig eller vått på klatrefelt rundt Bergen, beregnet fra offentlige værdata
(modellert is/snø vises som vått).

Modell **2.0.0**, ni felt: Ekstraveggen, Sandviken, Helleneset, Neseveggen, Bolstadøyri, Trollkona,
Loddefjord, Bymuren og Fabrikkveggen. Ett felt er én YAML-fil i `modeling/config/`.

GitHub Actions kjører hver time ved :07 og skriver til Supabase; Next.js på Vercel leser databasen.
Varselet går 120 timer frem og 168 timer tilbake. Parametrene er foreløpige og ikke målt mot veggene.

## Dokumentasjon

- [Modell, datakilder og valideringskrav](docs/MODELL_V2.md)
- [Overlevering: kode, gjenstående arbeid og fallgruver](docs/OVERLEVERING.md)
- [Deploy og drift](docs/DEPLOY.md)
- [Legge til et felt](docs/LEGG_TIL_FELT.md)
- Bakgrunn: [research](docs/RESEARCH.md), [oppfølging](docs/RESEARCH_2.md)

## Lokal utvikling

Krever Python 3.12 og Node.js 22+. Fra repo-roten:

```sh
cp .env.example .env
cp web/.env.example web/.env.local
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -r modeling/requirements-dev.txt
cd modeling && python scripts/serve.py
```

På Windows: `Copy-Item` i stedet for `cp`, `py -3.12 -m venv .venv` og `.\.venv\Scripts\Activate.ps1`.

I en annen terminal: `cd web && npm ci && npm run dev`.
Web: http://localhost:3000, API: http://localhost:8000/docs. Eller `docker compose up --build`.

### Miljø

Fyll inn `KLATREFORHOLD_CONTACT` i `.env`. Uten Supabase-nøkler lagres observasjoner i
`modeling/data/labels/`. Med nøkler brukes produksjonsdatabasen, så behold `KLATREFORHOLD_KILDE=dev`
i begge miljøfilene (dev-data holdes utenfor trening). Service role-nøkkelen er kun for serveren.

Nettsiden bruker Supabase når nøklene er satt. `KLATREFORHOLD_DATAKILDE=api` i `web/.env.local`
tvinger lokal modellkode (arkiv og statistikk leses fortsatt fra Supabase). Docker bruker `api`.

### Lokal Supabase

Prøv nye migrasjoner lokalt før produksjon. Krever Docker og Supabase CLI; porter 55321–55329.

```sh
supabase start                      # kjører alle migrasjoner på en tom database
supabase migration up --local       # ny migrasjon
supabase db reset --local           # alt på nytt (+ supabase/seed.sql hvis den finnes)
supabase status -o env              # verdier for SUPABASE_URL og SUPABASE_SERVICE_ROLE_KEY
```

Pek `SUPABASE_URL` og `SUPABASE_SERVICE_ROLE_KEY` hit for å kjøre timesjobben uten å røre produksjon.
Produksjonsdata (valgfritt, krever `supabase link`): `supabase db dump --linked --data-only -f supabase/seed.sql`.
Filen inneholder brukerkommentarer og er i `.gitignore`.

## Kontroller

Fra repo-roten:

```sh
(cd modeling && python -m pytest tests -q && python scripts/check_model_v2.py)
(cd web && npm test && npm run typecheck && npm run build)   # build henter Google-font over nett
```

`publish_forecast.py --dry-run` (fra `modeling/`) prøver alle felt uten å publisere.

## Modellarbeid

Fra `modeling/`, med feltets værhistorikk i `data/raw/<vaer>.csv`:

```sh
python scripts/evaluate.py --config config/ekstraveggen.yaml --weather supabase 'data/raw/<vaer>.csv' --labels supabase
python scripts/calibrate.py --config config/ekstraveggen.yaml --weather supabase 'data/raw/<vaer>.csv' --labels supabase --write
```

`--weather supabase` henter været timesjobben brukte (`vaer`-tabellen); CSV-en fyller bare tiden før
og hull over 72 t. Krav til kalibrering og trening står i [modellguiden](docs/MODELL_V2.md).

## Kreditering

Værdata fra MET Norway (CC BY 4.0 / NLOD) og Open-Meteo (CC BY 4.0). Høydedata © Kartverket (CC BY 4.0).
Prosjektet er separat fra BKKs nettfører; nettførerens repo og database skal ikke endres herfra.
