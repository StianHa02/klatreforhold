# klatreforhold

Timevarsel for tørt, fuktig, vått eller is/snø på klatrefelt rundt Bergen, beregnet fra offentlige
værdata. Nettsiden viser tre tilstander; modellert is/snø vises som vått.

## Status og dokumentasjon

Kodegrunnlaget per 30. oktober 2026 bruker modell **2.0.0** og ni felt: Ekstraveggen, Sandviken,
Helleneset, Neseveggen, Bolstadøyri, Trollkona, Loddefjord, Bymuren og Fabrikkveggen.
Én YAML-fil direkte i `modeling/config/` definerer et felt. Nettsiden finner nye felt etter publisering.

- [Gjeldende modell, datakilder og valideringskrav](docs/MODELL_V2.md)
- [Overlevering: nåværende kode, gjenstående arbeid og historikk](docs/OVERLEVERING.md)
- [Deploy og driftskontroll](docs/DEPLOY.md)
- [Legge til et felt](docs/LEGG_TIL_FELT.md)
- Historisk grunnlag: [v1-modell og resultater](docs/MODEL.md), [første research](docs/RESEARCH.md),
  [oppfølgingsresearch](docs/RESEARCH_2.md), [v1/v2-sammenligning](docs/MODELL_V2_RESULTATER.md).

GitHub Actions kjører hver time ved :07 og skriver til Supabase. Next.js på Vercel leser databasen
på serveren. FastAPI brukes lokalt. Produksjonsstatus må kontrolleres i tjenestene; datoen over
bekrefter kodegrunnlaget, ikke siste vellykkede timesjobb.

Publisering gir 120 timer fremover (121 tidspunkt inkludert nå) og 168 historikktimer. Arkivet beholder
ledetider til 48 timer. Direkte MET Nordic foretrekkes, Open-Meteo gir historikk og reserve, og fersk
Nowcast supplerer nedbøren. MEPS kan gi ukalibrert `p_tort`; dette vises ennå ikke som prosent i UI-et.
Parametrene er foreløpige. Simulerte resultater er ikke målt treffsikkerhet på klatreveggen.

## Lokal utvikling

Bruk Python 3.12 (samme som CI) og Node.js 22 eller nyere. Kommandoene starter i repo-roten.
Ingen Supabase-nøkkel er nødvendig for lokalt API med CSV-lagring.

macOS/Linux:

```sh
cp .env.example .env
cp web/.env.example web/.env.local
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -r modeling/requirements-dev.txt
cd modeling
python scripts/serve.py
```

Windows/PowerShell:

```powershell
Copy-Item .env.example .env
Copy-Item web/.env.example web/.env.local
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r modeling/requirements-dev.txt
cd modeling
python scripts/serve.py
```

Start web i en annen terminal, fra repo-roten:

```sh
cd web
npm ci
npm run dev
```

Web: http://localhost:3000. API: http://localhost:8000/docs.
Alternativ fra repo-roten: `docker compose up --build` starter begge.

### Datakilde og miljø

Fyll inn `KLATREFORHOLD_CONTACT` i `.env`. Python leser `modeling/.env` før rotens `.env`;
eksisterende miljøvariabler vinner. Sett kommentarer på egne linjer.

Uten Supabase-nøkkel lagres observasjoner i `modeling/data/labels/`. Med prosjektets Supabase-nøkler
brukes samme database som produksjon. Behold `KLATREFORHOLD_KILDE=dev` i begge lokale miljøfiler;
dev/test-data utelates fra trening som standard. Service role-nøkkelen er kun for serveren.

Nettsiden velger Supabase når begge nøklene er satt. Sett `KLATREFORHOLD_DATAKILDE=api` i
`web/.env.local` for å bruke lokal modellkode også med nøkler; arkiv/statistikk leses fortsatt fra
Supabase. Docker bruker `api` som standard; sett variabelen i rotens `.env` for å overstyre det.

## Kontroller

Med aktivert Python-miljø, fra repo-roten:

```sh
cd modeling
python -m pytest tests -q
python scripts/check_model_v2.py
```

Fra `web/`:

```sh
npm test
npm run typecheck
npm run build
```

Bygging laster Google-font over nett. Typekontroll kan kjøres uten dette etter at avhengighetene
er installert. Det er ikke konfigurert en egen linter.

## API og modellarbeid

FastAPI tilbyr `GET /api/health`, `GET /api/felt`, `GET /api/felt/{slug}/varsel` og
`GET/POST /api/felt/{slug}/observasjoner`. Varselet har `sammendrag`, `timer` og `siste_timer`;
`timer`-parameteren er 1–120 (standard 24), historikken er sju døgn. Cache er 20 minutter.
`?na=2026-10-03T15:00` setter beregningstid for testing; tilgang til historisk vær begrenser bruken.
Nettsidens Supabase-modus kan bare klippe eksisterende lagrede data, ikke beregne et nytt gammelt varsel.

Python-API og databaseskjema tillater `tort`, `fuktig`, `vatt`, `is`; nettsidens skjema tilbyr de tre
første. Observasjoner kan være opptil 14 dager gamle. Se `/docs` lokalt for alle parametre.

Kjør verktøy fra `modeling/`. `predict_now.py` er en enkel Open-Meteo/Locationforecast-kontroll;
`check_model_v2.py --live --forecast` kontrollerer produksjonens værkjede uten databaseskriving.
`publish_forecast.py --dry-run` prøver alle felt uten å publisere (værhenting kan skrive lokal cache).

Kalibrering krever minst 50 observasjoner fra minst ti regnepisoder, begge klasser i trening/kontroll,
og forbedring på holdte-utenfor episoder. Bare `evaporation_efficiency` tilpasses.
Se [modellguiden](docs/MODELL_V2.md) for valideringskrav. `train.py --save` lagrer ML-kandidater med
`validated: false`; de aktiveres ikke automatisk. Ikke tren lagrede modeller på syntetiske etiketter.
Eksempler fra `modeling/` (erstatt `data/raw/<vaer>.csv` med feltets historikk):

```sh
python scripts/evaluate.py --config config/ekstraveggen.yaml --weather 'data/raw/<vaer>.csv' --labels supabase
python scripts/calibrate.py --config config/ekstraveggen.yaml --weather 'data/raw/<vaer>.csv' --labels supabase --write
python scripts/train.py --config config/ekstraveggen.yaml --weather 'data/raw/<vaer>.csv' --labels supabase --save
```

PyTorch er valgfritt og installeres separat for lokal trening (`--torch`); timesjobben bruker sklearn.

## Repoet og kreditering

`modeling/`: Python, feltkonfigurasjon og tester. `web/`: Next.js 16, React 19 og Tailwind 4.
`supabase/migrations/`: databaseskjema. `.github/workflows/varsel.yml`: timesjobben.
Værhistorikk, modellresultater og cache ligger utenfor Git. Eksisterende statistikk ble generert
30. oktober 2026 for alle ni felt med modell v2 og 90 døgn oppvarming.

Værdata fra MET Norway (CC BY 4.0 / NLOD) og Open-Meteo (CC BY 4.0). Høydedata © Kartverket (CC BY 4.0).
Prosjektet er separat fra BKKs nettfører; nettførerens repo og database skal ikke endres herfra.
