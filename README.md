# klatreforhold

Predikerer om fjellet på et klatrefelt er **vått eller tørt**, time for time, bare fra offentlige
værdata. Felt: **Ekstraveggen** (Bønes), **Sandviken** og **Helleneset** (Bergen). Ett felt = én fil i `modeling/config/`;
timesjobben og nettsiden plukker opp nye filer automatisk.

- Hvordan modellen fungerer: [`docs/MODEL.md`](docs/MODEL.md)
- Research bak valgene (fysikk, analoge modeller, datakilder): [`docs/RESEARCH.md`](docs/RESEARCH.md)
- Deploy (Vercel + Supabase + GitHub Actions, uten eget API): [`docs/DEPLOY.md`](docs/DEPLOY.md)

## Status (oktober 2026)

| Del | Status |
|---|---|
| Fysisk modell (regn mot veggen, sol, bergtemperatur, kondens, fordampning, siging) | ✅ fungerer, enkle tester OK |
| Datahenting: Open-Meteo (MET Nordic), api.met.no, Frost, MET Nordic thredds | ✅ Open-Meteo-historikk kjørt (2023–2026, ingen hull). De andre er testet med falske svar, ikke mot ekte API-er |
| Varsel nå + hver time neste 24 t, med forklaringer | ✅ `src/klatreforhold/predict.py` |
| API (FastAPI) med tilbakemeldinger | ✅ testet |
| Web-UI (Next.js) med 24-timers stripe og "stemmer varselet?" | ✅ bygget og testet |
| Docker (api + web) | ✅ skrevet, ikke kjørt (ingen Docker der det ble laget) |
| Supabase (siste varsel, varselarkiv, observasjoner) | ✅ prosjekt opprettet og migrert |
| Timesjobb (GitHub Actions → Supabase) | ⏳ klar, trenger secrets i GitHub, se docs/DEPLOY.md |
| Vercel (kun Next.js-siden) | ⏳ klar til deploy, se docs/DEPLOY.md |
| Trening/sammenligning: fysikk vs regler vs scikit-learn vs PyTorch (GRU) | ✅ kjørt (PyTorch på CPU). GPU-trening ikke testet på 5070 ennå |
| Horisont/sol fra Kartverket DOM1 | ✅ kjørt (scripts/download_dom.py + horizon_from_dem.py). Sol på veggen fra ca. kl 16–17 april–august, ingen direkte sol oktober–februar. Himmelsynsfaktor 0.36 |
| Kalibrering | ❌ venter på ekte observasjoner av tørt/vått |

Alle modellparametre er startverdier fra litteraturen (se `modeling/config/ekstraveggen.yaml`). Kalibrerte verdier havner i `modeling/config/kalibrert/`.

## Repoet

```
modeling/   Python: fysikkmodell, datahenting, kalibrering, trening, timesjobb, lokalt API
web/        Next.js-nettsiden (Vercel, root directory = web)
supabase/   database-migrasjoner
docs/       modell, research, deploy
.github/    timesjobben (GitHub Actions, kjører i modeling/)
```

**Alle Python-kommandoer under kjøres fra `modeling\`** (`cd modeling`). `.env` ligger i repo-roten.

## Kom i gang

### Miljøvariabler (gjør dette først)

Utvikling bruker **samme Supabase-database som produksjon**, så du har brukernes tilbakemeldinger
lokalt og kan trene direkte på dem.

```powershell
copy .env.example .env               # fyll inn SUPABASE_SERVICE_ROLE_KEY og KLATREFORHOLD_CONTACT
copy web\.env.example web\.env.local # samme nøkkel
```

Observasjoner du registrerer lokalt merkes `kilde = dev` og tas ikke med i trening
(med mindre du ber om det med `--med-dev`). Nøkkelen gir full tilgang til databasen, så den skal aldri
committes eller brukes i kode som kjører i nettleseren.

Tren rett fra databasen:

```powershell
python scripts\fetch_history.py --start 2023-01-01 --end 2026-10-26
python scripts\evaluate.py  --config config\ekstraveggen.yaml --weather data\raw\ekstraveggen_openmeteo_metno_2023-01-01_2026-10-26.csv --labels supabase
python scripts\calibrate.py --config config\ekstraveggen.yaml --weather data\raw\ekstraveggen_openmeteo_metno_2023-01-01_2026-10-26.csv --labels supabase --write
python scripts\train.py --weather data\raw\ekstraveggen_openmeteo_metno_2023-01-01_2026-10-26.csv --labels supabase --torch --save
```

### Alt-i-ett med Docker (anbefalt for utvikling)

```powershell
cd $HOME\Documents\klatreforhold
docker compose up --build
```
- Web-UI: http://localhost:3000 (gå til Ekstraveggen)
- API + dokumentasjon: http://localhost:8000/docs

Uten Supabase-variabler lagres tilbakemeldinger i `modeling\data\labels\`, og modeller du trener lokalt i
`modeling\models\` blir brukt av API-et automatisk.

### Uten Docker

```powershell
cd modeling
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements-dev.txt
$env:PYTHONPATH = "src"; python scripts\serve.py          # API på :8000

cd web; npm install; npm run dev                            # UI på :3000 (i et nytt vindu)
```

### Trening med PyTorch på GPU (RTX 5070)

Trening kjøres utenfor Docker, rett på Windows, så GPU-en brukes uten ekstra oppsett:

```powershell
pip install torch --index-url https://download.pytorch.org/whl/cu128     # CUDA 12.8, støtter RTX 50-serien
python -c "import torch; print(torch.cuda.is_available())"             # skal gi True

python scripts\train.py --weather data\raw\ekstraveggen_openmeteo_metno_2023-01-01_2026-10-26.csv `
  --labels data\labels\ekstraveggen_observasjoner.csv --torch --save
```
`--save` legger `models\ekstraveggen_sklearn.joblib` og `models\ekstraveggen_torch.pt` der API-et finner dem.
Da viser UI-et også sannsynlighet for tørt per time. **Ikke tren med `--save` på syntetiske etiketter**
(f.eks. laget av en nedbørsregel): da lærer modellen bare regelen tilbake. Vent til det finnes ekte
tilbakemeldinger (grovt sett et par hundre, spredt over vær og årstider).

### Tester

```powershell
cd modeling
for %t in (tests\test_*.py) do python %t        # eller én og én: python tests\test_physics.py
```

## API (for nettføreren senere)

| Metode | Sti | Hva |
|---|---|---|
| GET | `/api/felt` | felt med konfig |
| GET | `/api/felt/{slug}/varsel` | `sammendrag` (tørt nå? tørt om 24 t? neste tørre time) + `timer` (nå + 24 timer) + `siste_timer` (12 t bakover) |
| POST | `/api/felt/{slug}/observasjoner` | `{"status": "tort"\|"fuktig"\|"vatt", "tid": ISO, "predikert_status": "...", "kommentar": "..."}` |
| GET | `/api/felt/{slug}/observasjoner` | observasjoner + andel der varselet stemte |

Varselet caches i 20 minutter (MET ber om at man ikke henter oftere enn nødvendig). For testing kan
du se en gammel dag med `?na=2026-10-03T15:00` (både på API-et og på UI-siden).

Veien inn i nettføreren: API-et kjøres som egen tjeneste (samme Docker-image), observasjonene flyttes til en
Supabase-tabell, og komponentene i `web/components` kan flyttes rett over (de bruker samme design-tokens
som nettføreren).

## Mappestruktur

```
modeling/config/<felt>.yaml             feltets geometri og modellparametre (kalibrert/ overstyrer)
modeling/src/klatreforhold/physics/     sol på veggen (solar.py) og vannbalanse/energibalanse (wetness.py)
modeling/src/klatreforhold/data/        henting fra Open-Meteo, api.met.no, Frost, thredds, stasjons-CSV
modeling/src/klatreforhold/ml/          features, evaluering (evaluate.py), kalibrering (calibrate.py),
                                        sklearn- og PyTorch-trening (torch_model.py)
modeling/src/klatreforhold/predict.py   varsel nå + 24 t
modeling/src/klatreforhold/publish.py   timesjobben (skriver til Supabase)
modeling/src/klatreforhold/api.py       lokalt HTTP-API
modeling/scripts/                       kommandolinjeverktøy
modeling/data/raw, modeling/data/labels data (raw ikke i git)
modeling/outputs/                       figurer og CSV fra kjøringer (ikke i git)
web/                                    Next.js-nettsiden
supabase/migrations/                    databaseskjema
docs/                                   modellbeskrivelse, research, deploy
docker-compose.yml                      API (modeling/) + web lokalt
```

## Første resultater (Open-Meteo 2023-01-01 → 2026-10-26)

- Open-Meteo stemmer godt med målte stasjonsdata nær feltet (jun–okt 2026): temperatur r = 0.98, luftfuktighet r = 0.96, vind r = 0.74. Nedbøren er ca. 20 % lavere enn stasjonen.
- Andel tørre timer i modellen: ca. 70–75 % i april–juli, 30–45 % i september–mars.
- Siging står for bare noen få prosentpoeng av de våte timene.
- Status `is` når det er vann på berg under 0 °C (ca. 3 % av timene).

## Viktige forbehold

- **Vi har ingen ekte fasit ennå.** Tallene over viser at modellen oppfører seg fornuftig, ikke hvor
  treffsikker den er. Det får vi først vite når tilbakemeldingene fra brukerne kommer inn.
- Neste viktige steg er å samle inn ekte observasjoner: en "tørt / fuktig / vått"-knapp i nettføreren,
  helst med klokkeslett for når man var på feltet.

## Kreditering

Værdata fra MET Norway (CC BY 4.0 / NLOD), via Open-Meteo (CC BY 4.0) der det er brukt.
Høydedata © Kartverket (CC BY 4.0).
