# Overlevering: klatreforhold

Status per 27. oktober 2026. Dette dokumentet er for den som tar over (menneske eller agent): hva som er
bygget, hva vi har funnet ut, hvilke valg som er tatt og hvorfor, hva som gikk galt underveis, og hva som
gjenstår. Detaljene om modellen står i [`MODEL.md`](MODEL.md), litteraturen i [`RESEARCH.md`](RESEARCH.md)
og oppsettet i [`DEPLOY.md`](DEPLOY.md). For agenter: se også [`../CLAUDE.md`](../CLAUDE.md).

---

## 1. Kort fortalt

- **Mål:** si om fjellet på et klatrefelt i Bergen er tørt, fuktig, vått eller islagt, nå og time for time
  framover, bare fra offentlige data. Brukerne sier fra om varselet stemte, og det blir treningsdata.
- **Felt:** Ekstraveggen (Bønes), Sandviken og Helleneset, de mest brukte feltene.
- **Kjernen** er en fysisk modell (vannbalanse + energibalanse for bergflaten, time for time), ikke en
  ML-modell. ML (scikit-learn og PyTorch) ligger klart oppå, men trenes først når det finnes ekte tilbakemeldinger.
- **Drift:** GitHub Actions kjører modellen hver time og skriver til Supabase. Next.js-siden på Vercel leser
  derfra. Ingen egen API-server i produksjon.
- **Avgrensning:** eget prosjekt. Ingen kobling til nettføreren (egen database, eget repo) før det er besluttet.
- **Det viktigste som mangler:** tilbakemeldinger fra brukerne. Uten dem vet vi at modellen oppfører seg
  fornuftig, men ikke hvor treffsikker den er.

## 2. Status nå

| Del | Status |
|---|---|
| Fysisk modell, tre felt med geometri fra Kartverket DOM1 | ✅ i drift |
| Varsel 48 t fram + 24 t bak, med forklaringer | ✅ |
| Nettside (Vercel, gratisnivå): forside, feltside, «Om modellen», tilbakemeldingsskjema | ✅ i drift |
| Supabase (tabeller, RLS, funksjoner) | ✅ 4 migrasjoner kjørt |
| Timesjobb (GitHub Actions) | ⚠️ fungerer når den startes for hånd, men den planlagte kjøringen har ikke startet av seg selv. Per 27.10 kveld: 3 kjøringer i arkivet |
| Frost-kontroll i timesjobben | ⚠️ koden er klar, men `stasjon_varsel` og `stasjon_maling` er tomme. Sjekk at `FROST_CLIENT_ID` er lagt inn som secret i GitHub |
| Flerårig kontroll mot Frost (2023-2026) | ✅ kjørt lokalt, resultater i MODEL.md |
| Fuktighetskorreksjon (måned + døgn) | ✅ laget, testet og committet. Brukes fra neste timesjobb etter push |
| Tilbakemeldinger i `observasjoner` | ❌ 0 rader (testradene er fjernet) |
| Kalibrering per felt | ❌ venter på ~150-400 tilbakemeldinger |
| Trente ML-modeller (`modeling/models/`) | ❌ tom med vilje (ingen ekte etiketter ennå) |
| PyTorch (GRU) | ✅ koden kjører og er testet på CPU. GPU-trening på RTX 5070 er ikke testet ennå |
| Docker (api + web) | ✅ |
| Integrasjon i nettføreren | ❌ ikke påbegynt (bevisst) |

`web/data/modellstatistikk.json` (grafene på «Om modellen») er laget **før** fuktighetskorreksjonen. Kjør
`python scripts/export_site_stats.py` på nytt og commit filen.

## 3. Arkitektur

```
GitHub Actions  (cron 7 * * * *, + manuell start)        modeling/scripts/publish_forecast.py
  1. Open-Meteo (MET Nordic 1 km, metno_seamless): 7 døgn bak + 3 døgn fram per felt
  2. fysikkmodell (+ ML hvis modellfil finnes) -> varsel per time
  3. Frost (hvis FROST_CLIENT_ID): varsel for stasjonens punkt + stasjonens målinger  (kontroll)
             │ SUPABASE_SERVICE_ROLE_KEY
             ▼
Supabase  nmiydpcmfxkhtztzgzfx  (org "klatreforhold", eu-north-1, gratisnivå)
  varsel_siste    siste varsel per felt (jsonb)                         <- nettsiden leser
  varsel          arkiv: én rad per felt × kjøring × time (ledetid)     <- treffsikkerhet per ledetid
  observasjoner   brukernes tilbakemeldinger (status, tid, predikert_status, riktig, kilde)
  stasjon_varsel  varsel for Frost-stasjonens koordinater (kontroll)
  stasjon_maling  stasjonens målinger
  treffsikkerhet(felt), statistikk()  SQL-funksjoner for nettsiden
  RLS på, ingen policies -> bare service role har tilgang. pg_cron: rydd-cron-historikk (søndager)
             ▲ service role key, kun på serveren
             │
Vercel  (Hobby/gratis, root directory = web)     Next.js 16
  /                forside med feltene
  /felt/[slug]     status nå, timestripe (5 t bak, nå, 19 t fram), graf, «Stemte varselet?»
  /om              hvordan modellen virker, med grafer
  POST /api/felt/[slug]/observasjoner   lagrer tilbakemelding (validert på serveren)
```

Lokalt finnes også en FastAPI-tjeneste (`modeling/app.py`) som Docker-oppsettet bruker. I produksjon brukes den
ikke. `web/lib/kilde.ts` velger Supabase når `SUPABASE_URL` og `SUPABASE_SERVICE_ROLE_KEY` er satt, ellers
Python-API-et.

Utvikling bruker **samme database som produksjon**, så treningsdata ligger ett sted. Observasjoner fra en
utviklermaskin merkes `kilde = 'dev'` og holdes utenfor trening.

### Kontoer og hemmeligheter (ingen verdier her)

| Hvor | Hva |
|---|---|
| GitHub `StianHa02/klatreforhold` → Settings → Secrets → Actions | `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `KLATREFORHOLD_CONTACT`, `FROST_CLIENT_ID` |
| Vercel-prosjektet (root `web`) | `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY` (aldri `NEXT_PUBLIC_`) |
| `.env` i repo-roten (ikke i git) | det samme + `KLATREFORHOLD_KILDE=dev`, `FROST_CLIENT_ID` |
| Frost | gratis klient-ID fra frost.met.no |
| Open-Meteo | ingen nøkkel. Gratis for ikke-kommersiell bruk, 10 000 kall/døgn |

Vercel-kontoen er på gratisnivå med ett ledig prosjekt brukt opp av denne siden.

## 4. Repoet

```
modeling/
  config/<felt>.yaml          geometri, horisont (DOM1), modellparametre, frost_station, frost_bruk
  config/kalibrert/<felt>.yaml  kalibrerte parametre (finnes ikke ennå), overstyrer feltfila
  config/stasjoner/rh_korreksjon.yaml   fuktighetskorreksjon per Frost-stasjon
  src/klatreforhold/
    config.py        Crag, load_config (+ kalibrert og fuktighetskorreksjon), leser .env
    physics/wetness.py   run_model: vannlagre, energibalanse, slagregn, status; rh_correction
    physics/solar.py     stråling på skrå/vertikal flate (pvlib), horisontmaske, langbølget
    data/openmeteo.py    MET Nordic via Open-Meteo (historikk fra 2022-11-15, varsel)
    data/metno.py        api.met.no Locationforecast (reserve)
    data/frost.py        Frost: stasjoner, målinger, siste timer
    data/metnordic_thredds.py  MET Nordic rett fra thredds (lang historikk fra 2012, ikke i bruk)
    ml/features.py, ml/train.py, ml/torch_model.py  sklearn HistGradientBoosting og PyTorch GRU (vindu 48 t)
    ml/evaluate.py   rettferdig evaluering per værsituasjon, enkle regler, treff per ledetid
    ml/calibrate.py  MAP-kalibrering av 3 parametre, vekter for skjeve observasjoner
    predict.py       varsel for ett felt; get_weather, predict, forklaringer på norsk
    publish.py       timesjobben
    storage.py       CsvStorage og SupabaseStorage
    verify.py        kontroll mot Frost: per ledetid, vinduer, sesong/år, fuktighetsanalyse og -korreksjon
    api.py           FastAPI (lokalt)
  scripts/           se tabellen under
  tests/             test_physics, test_fetchers, test_storage, test_bias_tools, test_verify
web/                 Next.js-siden
supabase/migrations/ kjørt mot databasen. supabase/valgfritt/ er IKKE kjørt
docs/                MODEL, RESEARCH, RESEARCH_2 (tørking, usikkerhet, fasit, historikkvisning), DEPLOY, OVERLEVERING
.github/workflows/varsel.yml   timesjobben
docker-compose.yml   api (modeling/) + web
```

### Skriptene (kjøres fra `modeling/`)

| Skript | Hva |
|---|---|
| `publish_forecast.py [--dry-run]` | timesjobben |
| `predict_now.py --config ...` | varsel for ett felt i terminalen |
| `fetch_history.py --config ... --start --end` | værhistorikk til `data/raw/` |
| `run_history.py` | kjør modellen over en periode, figur + CSV |
| `download_dom.py --config ... [--tile]` | Kartverket DOM1 rundt feltet |
| `horizon_from_dem.py --config ... --dem ... [--min-dist-m 10]` | horisontprofil og himmelsynsfaktor |
| `evaluate.py --labels supabase` | rettferdig evaluering mot tilbakemeldinger |
| `calibrate.py --labels supabase --write [--vekter]` | kalibrer per felt, skriver `config/kalibrert/` |
| `train.py --labels supabase --torch --save` | tren sklearn + PyTorch, lagre i `models/` |
| `export_observations.py` | tilbakemeldinger fra Supabase til CSV |
| `simulate_bias.py`, `simulate_sweep.py` | simulering av skjeve tilbakemeldinger |
| `verify_forecast.py` | varselarkivet mot Frost (per ledetid, og per måned når arkivet er langt nok) |
| `verify_forecast.py --historikk [START SLUTT] [--skriv-rh]` | flere år mot Frost, sesong/år/døgn, skriver fuktighetskorreksjon |
| `export_site_stats.py` | statistikk til «Om modellen» (`web/data/modellstatistikk.json`) |
| `serve.py` | lokalt API på :8000 |

## 5. Modellen kort

Detaljer og formler i `MODEL.md`. Hovedtrekk:

- **Vann inn:** slagregn mot veggen `α·U·R^0.88·cos(D−θ)` (α = 0.12), ganget med sin(helning); direkte regn på
  tak og hyller (`direct_rain_fraction` + cos(helning) for sva); avrenning ovenfra; kondens når berget er
  kaldere enn duggpunktet; siging fra et sakte reservoar (tømmetid 120 t).
- **Vann ut:** fordampning styrt av vanndampforskjellen mellom bergflaten og lufta (Lewis-relasjonen,
  `h_c = 5.7 + 3.8·U`). Tak og sprekker tørker saktere enn filmen.
- **Bergtemperatur:** energibalanse med sol på flaten (pvlib, horisont fra DOM1), langbølget fra himmel og
  terreng (himmelsynsfaktor), konveksjon, ledning til dypere berg.
- **Lagre:** film 0.1 mm, tak/sprekker 0.6 mm (0.4 i Sandviken), sigereservoar.
- **Status:** `vatt` ≥ 0.05 mm, `fuktig` ≥ 0.01 mm, ellers `tort`; `is` når det er vann og berget er under 0 °C.
- **Fuktighetskorreksjon:** MET Nordics luftfuktighet justeres per måned og time på døgnet før energibalansen (se 7.6).
- **ML:** hybrid oppå fysikken (features fra modellens tilstand). sklearn i produksjon (timesjobben installerer
  ikke torch), PyTorch GRU lokalt. Begge faller tilbake til ren fysikk hvis modellfila mangler.

### Feltene

| | Ekstraveggen | Sandviken | Helleneset |
|---|---|---|---|
| felt_id | 137 | 33 | 5 |
| Koordinater | 60.3346, 5.3122 | 60.4166, 5.3190 | 60.4343, 5.2806 |
| Høyde (DOM1) | 66 m | 78 m | 3 m |
| Veggretning | 300° (VNV) | 270° (V) | 270° (V) |
| Helning | 90° (vertikal) | 90° | 70° (sva, anslått) |
| Himmelsynsfaktor | 0.37 | 0.34 | 0.6 |
| Sol på veggen, juni / desember (t/døgn) | 3.5 / 0 | 3.75 / 0.7 | 5.4 / 0.7 |
| Regn på veggen / nedbør (mm/år) | 418 / 2027 | 515 / 2204 | 1143 / 1989 |
| Tørketid etter regn, median sommer / vinter | 7 t / 20 t | 7 t / 14 t | 11 t / 20.5 t |
| Andel tørre timer juni / desember | 67 % / 28 % | 65 % / 35 % | 60 % / 28 % |
| Frost-stasjon | SN50540 Florida, `kontroll` | samme | samme |

Tallene er fra `export_site_stats.py` (2023-2026, før fuktighetskorreksjonen). Ekstraveggen får ingen direkte
sol oktober-februar og sol fra ca. kl 16-17 april-august. Helleneset fanger mye mer regn fordi svaet tar imot
vanlig regn, ikke bare slagregn.

## 6. Hva som skjer i nettsiden

- **Dag for dag** (`components/DagBokser.tsx`, logikk i `lib/dager.ts`): fem bokser, Nå, I morgen og tre
  dager til, farget etter status. På forsiden for hvert felt, og øverst på feltsiden. Folk planlegger og
  avtaler med partnere opptil fire dager fram. En dag er «tørt» med et tørt vindu på minst 3 t i klatretiden
  kl 08-21 («kl 13–21», «hele dagen»), ellers «fuktig» («beste kl 12–17»), «is» eller «vått» (regn i mm).
  Dager over 60 t fram (etter MET Nordic, ECMWF 9 km) merkes «usikkert».
- Feltsiden viser så tilbakemeldingsskjemaet, en timestripe fra 5 t bak til 19 t fram (valgt etter testing av
  ±12 og 2/22), og grafer med vann på veggen og regn mot veggen, og bergtemperatur mot duggpunkt, med en stiplet
  «nå»-linje. **Vann på veggen har fast skala 0–2 mm** (vann i mm og regn i mm/t på samme akse; modellens maks
  er film + sprekker, 0.7 mm på Ekstraveggen). **Mellom berg og duggpunkt** er det grønt når berget er
  varmere, blått når det er kaldere (kondens), sterkere jo større avstand (full ved 4 °C). Begge etter innspill
  fra lederen.
- **Neste 4 døgn** og **Siste 7 døgn** (`components/NesteDogn.tsx`, `Historikk.tsx`, felles
  `Ukerutenett.tsx`): én rad per døgn med 24 timer, uten sideveis rulling. Sol på veggen som strek øverst,
  status per time (bokstav i tillegg til farge), regn som søyler under (full søyle 2 mm/t), sum til høyre
  (regn, soltimer, snittvind). Trykk på en dag for tabell time for time (status, varslet dagen før, regn,
  sol, vind med retning, fukt). «Siste 7 døgn» har oppsummering («Sist regn … tørt igjen etter 9 t») og en
  bryter **I etterkant** (modellen kjørt på været slik det ble) / **Varslet dagen før** (arkivet, ledetid
  nærmest 24 t). Tilbakemeldingene vises som prikker med ✓/✗ mot det som vises, og treffet telles per visning.
- Kildene: `varsel_siste` har 7 døgn bakover og ut dag +4 fram (timesjobben henter 14 døgn bakover, så
  vannlagrene er varmet opp, og 6 døgn fram). `vinduFraNa` gir `timer` (neste døgn), `framover` og `historikk`.
  Døgn regnes fra timens start i norsk tid (tidsstempelet er slutten av timen); sommertidsdøgnet med 25 timer
  slår sammen den doble timen.
- Banner om varselet er mer enn 3 timer gammelt (timesjobben har stoppet).
- **Tilbakemelding:** datovelger (opptil 13 dager bak), klokkeslett 06-23, status tørt/fuktig/vått og valgfri
  kommentar. **Fra 2026-10-29 har timeknappene en strek i fargen modellen mener timen hadde** (eierens valg, se 8).
  Serveren slår opp hva varselet sa for den timen (`predikertFra`: arkivet først, så `varsel_siste`) og lagrer
  `predikert_status` og `riktig`.
- «Om modellen» forklarer modellen med et snitt av veggen og grafer fra `modellstatistikk.json` og `statistikk()`.
- Styling og fonter (Work Sans + Mabry) er laget i en egen frontend-økt. Samme design-tokens som nettføreren,
  så komponentene kan flyttes over senere.

## 7. Hva vi har funnet ut

### 7.1 Fra litteraturen (`RESEARCH.md`)

- Gneis og granitt holder nesten ikke vann inne i steinen (porøsitet ~0.5 %). Vått berg er et spørsmål om en
  **vannfilm på ~0.1 mm** på overflaten, vann i sprekker og tak, og siging.
- Regn treffer en vertikal vegg nesten bare via vinden. Slagregnkoeffisienten er den mest usikre parameteren
  (0.02-0.26 på vegger, 0.188 i fritt felt i Bergen). Vi starter på 0.12.
- **Tørkingen kollapser når luftfuktigheten nærmer seg 90 %**: en film som tørker på drøye timen ved 50 % RH
  kan bli liggende et døgn ved 90 %. Derfor er fuktighet, sol og vind viktigere enn eksakt regnmengde.
- «Svett» fjell kommer mest av kaldt berg som møter mild, fuktig luft, ikke av klar-natt-dugg.
- Veivær-modeller (METRo, RoadSurf) og bladfukt-modeller har samme oppbygning og gir startverdier.
- Det finnes **ingen fasit** for noen naturlig fjellvegg. Lokale observasjoner er det som avgjør kvaliteten.

### 7.2 Lokalt vær (MET Nordic 1 km)

- Timesnedbøren på Ekstraveggen og Sandviken korrelerer bare 0.86. I 22 % av regntimene regner det bare det
  ene stedet.
- Kjører vi Ekstraveggen-modellen på byvær i stedet for feltets eget, blir statusen en annen i 5 % av timene.
- Konklusjon: hvert felt bruker sitt eget gridpunkt. Målestasjoner brukes til kontroll, ikke som erstatning.

### 7.3 Skjeve tilbakemeldinger

Folk drar når de tror det er tørt, snur når det er vått og rapporterer det som overrasker. Simulering
(`simulate_sweep.py`, balansert treff etter regn):

| Tilbakemeldinger | Startverdier | Kalibrert | Kalibrert + vekter |
|---|---|---|---|
| 150 | 0.79 | 0.84 | 0.85 |
| 400 | 0.78 | 0.93 | 0.91 |

Kalibrering hjelper tydelig fra noen hundre, selv med skjeve data. Vekting gir lite og er av som standard.
Evaluering må gjøres per situasjon (`under_regn`, `etter_regn`, `torkeperiode`). Total treffprosent lyver.
Et tidsforløpskamera eller en fuktsensor på én vegg ville gitt data uten skjevhet.

### 7.4 Regn: MET Nordic mot Florida (SN50540), 2023-2026, 33 456 timer

| | Time | 6 timer | Døgn |
|---|---|---|---|
| Regn truffet, ved stasjonen | 67 % | 81 % | 91 % |
| Regn truffet, ved feltene | 64-66 % | 77-80 % | 90-91 % |
| Varslet regn som uteble, ved stasjonen | 31 % | 16 % | 8 % |
| Korrelasjon døgnsum | | | 0.87-0.89 |
| mm-forhold (varsel/målt) | 0.80-0.90 | | |

- Usikkerheten ligger i **når** regnet kommer (noen timer), ikke **om**. Overganger vått/tørt bør leses ± 2 t.
- **Vinteren treffes best** (97 % av regndøgn), **sommeren dårligst** (87 %, og bare 79 % av mengden: små lokale byger).
- Stabilt fra år til år (døgn truffet 87-93 %).
- Feltpunktene er nesten like gode som stasjonspunktet mot stasjonen, så på disse skalaene er forskjellen i
  griddet liten (med forbehold om at griddet glatter ut lokale forskjeller).

### 7.5 Temperatur og vind

Temperatur: MAE 0.17 °C ved stasjonen, ingen skjevhet, hele året. Feltpunktene avviker 0.7-0.8 °C fra Florida
(høyde og nærhet til sjøen, ikke feil). Vind: MAE ~1.1 m/s, ingen skjevhet.

### 7.6 Luftfuktighet (det viktigste funnet)

- Sortert etter hva **varselet** sa, ser varselet for fuktig ut i fuktige timer (+6 ved ≥ 95 %) og for tørt i
  tørre. Sortert etter hva som ble **målt**, snur fortegnet (−4 ved målt ≥ 95 %). Det er altså mest tilfeldig
  feil (MAE ~8), ikke skjevhet. **En korreksjon må tilpasses på alle timer**, aldri på timer valgt ut fra varselet.
  Vårt første forsøk gjorde nettopp den feilen og ga −5.7 i mai.
- Det som er systematisk og går igjen hvert år:
  - **Døgnsvingning:** varselet er 3-5 prosentpoeng for fuktig på ettermiddag og kveld (topp kl 16-18 i alle
    måneder) og litt for tørt før soloppgang. Det er når folk klatrer og veggen tørker.
  - **Sesong:** for fuktig februar-oktober (+2 til +4, mest vår og forsommer), litt for tørt desember-januar.
    Enkeltmåneder varierer mye fra år til år, så månedsverdiene glattes.
- Florida måler nesten aldri 99-100 % (0.01 % av timene mot 3.9 % i varselet). Typisk for en bystasjon og
  fuktighetsfølere, så korreksjonen prøver ikke å fjerne de fuktigste timene.
- **2026 er fuktigere enn tidligere år** (+3.2 mot +1.1 til +1.6). Kan være endring i MET Nordic eller på
  stasjonen. Følg med i arkivkontrollen.
- **Korreksjonen** (`config/stasjoner/rh_korreksjon.yaml`): månedsnivå + døgnsvingning per måned, fra alle timer.
  Etterpå er skjevheten under 0.5 i alle sesonger og døgnperioder, og MAE på ettermiddagen går fra 8.0 til 6.7.
  Eksempel: juli kl 15-18 −5.6, april kl 18 −7.0, januar kl 06 +2.5.
- **Virkning:** andel våte dagtimer april-september går ned 1.5-2.5 prosentpoeng (Ekstraveggen 32.5 → 30.0 %).
  Dugg om natta og vinterstid er uendret. En fast −2 hele døgnet fjernet en tredel av kondensen og var feil.
- **Forbehold:** Florida er en bystasjon. Feltene ligger i skog og ved sjøen og kan være fuktigere.
  `rh_korreksjon_styrke` (standard 1) kan senere kalibreres mot tilbakemeldinger: formen fra stasjonen, styrken fra feltet.

### 7.7 Open-Meteo-arkivet

MET Nordic finnes i Open-Meteo Historical Forecast fra 2022-11-15, uten hull 2023-2026. Lengre historikk (fra
2012) finnes på thredds (`metnordic_thredds.py`), men er ikke tatt i bruk.

## 8. Beslutninger og hvorfor

| Beslutning | Hvorfor |
|---|---|
| Fysikk først, ML oppå | Ingen ekte etiketter. ML på syntetiske etiketter lærer bare regelen tilbake. Fysikken gir forklarbare svar fra dag én og trenger få observasjoner for kalibrering |
| MET Nordic via Open-Meteo | Eneste gratis kilde med alt (1 km, timesverdier, stråling, historikk). Enkel JSON |
| Ingen egen API i produksjon | Vercel gratis (ett prosjekt igjen). Timesjobb + Supabase dekker behovet. FastAPI beholdt for lokal bruk og senere nettfører |
| GitHub Actions som timesjobb | Gratis, Python-miljø, ingen server. Ulempe: planlagte kjøringer er upålitelige (se 9) |
| Dev mot produksjonsdatabasen | Rask tilgang til ekte treningsdata. `kilde=dev` holder testdata utenfor trening |
| RLS uten policies | All tilgang går via serveren med service role. Ingen offentlig nøkkel å misbruke |
| Frost `kontroll`, ikke `erstatt` | Bergen-været er lokalt; Florida ligger 4-6 km fra feltene. Kontroll måler varselets feil uten å gjøre feltets vær dårligere |
| 3 parametre i kalibreringen | `wind_exposure` og slagregnkoeffisienten kan ikke skilles (bare produktet er identifiserbart) |
| Vekting av skjeve data av som standard | Simuleringen viste liten gevinst |
| Fuktighetskorreksjon fra stasjonen, ikke fra tilbakemeldinger | ~33 000 målte timer er et sikrere grunnlag enn noen hundre rapporter. Styrken kan kalibreres senere |
| Timestripe 5 t bak / 19 t fram | Gir sammenheng bakover uten å skyve varselet ut av skjermen |
| Varselet skjult i tilbakemeldingsskjemaet (til 2026-10-28) | Unngår at brukerne svarer det varselet sa |
| Fra 2026-10-29: modellens status som strek på timeknappene | Eierens valg etter innspill fra klubben. Kan gi flere «det stemte»-rapporter (bra mot skjevheten i 7.3), men også forankring. **Vurder rapporter før og etter datoen hver for seg** |
| Dagbokser og 4 døgn fram | Folk planlegger og avtaler med partnere opptil fire dager fram. MET Nordic rekker ~2.5 døgn, resten er ECMWF (`metno_seamless`), merket «usikkert» |
| Arkivet lagrer bare ledetid ≤ 48 t | Varselet går 120 t fram, men arkivet ville vokst 2.5 ganger. «Varslet dagen før» trenger bare ~24 t |
| Monorepo `modeling/` + `web/` | Tydelig skille mellom Python og Next.js; Vercel bruker root `web` |

## 9. Feil og fallgruver vi har gått i

- **`.vercelignore` må ha rot-ankrede mønstre** (`/modeling`, `/docs`). Et uankret `data` fjernet `web/data` og
  ga «Can't resolve '@/data/modellstatistikk.json'». `vercel.json` er fjernet; Vercel finner Next.js via root `web`.
- **GitHub-planen startet ikke.** Alle kjøringer så langt er startet for hånd. Mulige årsaker: GitHub forsinker
  eller hopper over cron-jobber, og nye repo/workflows kan bruke tid. Alternativ: `supabase/valgfritt/cron_starter_github_jobb.sql`
  (Supabase Cron kaller workflow_dispatch med et GitHub-token i Vault). Ikke kjørt; eieren må gjøre det selv.
- **Utvalgsskjevhet i fuktighetsanalysen** (se 7.6). Generelt: tilpass aldri en korreksjon på et utvalg valgt
  ut fra varselet.
- **Alle `*.yaml` direkte i `modeling/config/` blir lest som felt.** Andre YAML-filer legges i undermapper.
- **PyYAML leser `2.2e6` som tekst.** `config._num()` gjør om. Bruk alltid `load_config`.
- **Tidsstempler:** nedbør og stråling gjelder timen *før* tidsstempelet. Nettsiden leser klokkeslett uten
  tidssone som Oslo-tid.
- **Asimut:** pvlib bruker kompass (300°), Open-Meteo GTI bruker 0 = sør. Ikke bland.
- **Sandvikens horisont** ble 55° fordi en hindring 3 m unna kom med. Løst med `--min-dist-m 10`.
- **Gamle observasjoner uten `predikert_status`** fantes fra før varselarkivet. `predikertFra` faller nå tilbake
  til `varsel_siste`.
- **`next/font/google` trenger nett ved bygging.** I miljøer uten nett: typesjekk med `npx tsc --noEmit`.
- **PostgREST gir maks 1000 rader per kall.** `limit=5000` hjelper ikke. Spør etter færre rader (f.eks.
  `ledetid_timer=in.(22,23,24,25,26)`) eller bla med `Range`.
- **Kommentar på samme linje i `.env` blir med i verdien** for Python-lesingen (`config._read_env`), f.eks.
  `SUPABASE_SERVICE_ROLE_KEY=... # →` gir «'latin-1' codec can't encode» når API-et kaller Supabase. Docker
  leser fila riktig. Legg kommentarer på egne linjer.
- **DOM1-flisa er 1.2 GB** og ligger i `modeling/data/raw/` (ikke i git). Én flis (33-104-120) dekker alle tre felt.
- **Torch-installasjon** fyller disken raskt (cache). Bruk CUDA 12.8-hjulene for RTX 50-serien.

## 10. Vanlige oppgaver

**Legge til et felt** (utfyllende oppskrift for agenter i `docs/LEGG_TIL_FELT.md`)
1. Kopier en `modeling/config/<felt>.yaml`, sett navn, `felt_id`, koordinater (maks 4 desimaler), veggretning,
   helning og `frost_station`.
2. `python scripts/download_dom.py --config config/<felt>.yaml` (eller `--tile` hvis flisa finnes).
3. `python scripts/horizon_from_dem.py --config config/<felt>.yaml --dem data/raw/<dom>.tif --min-dist-m 10`
   og lim inn horisonten og himmelsynsfaktoren i YAML-fila.
4. `python scripts/fetch_history.py --config config/<felt>.yaml --start 2023-01-01 --end <i går>` og
   `python scripts/run_history.py ...` for å se at det ser fornuftig ut.
5. Commit og push. Timesjobben og nettsiden plukker opp feltet automatisk. Kjør `export_site_stats.py` for «Om modellen».

**Kalibrere når tilbakemeldingene kommer** (per felt, fra ~150)
```powershell
cd modeling
python scripts\evaluate.py  --config config\ekstraveggen.yaml --weather data\raw\<vær>.csv --labels supabase
python scripts\calibrate.py --config config\ekstraveggen.yaml --weather data\raw\<vær>.csv --labels supabase --write
python scripts\evaluate.py  ...                       # sammenlign før og etter, særlig etter_regn
git add config\kalibrert; git commit -m "Kalibrert Ekstraveggen"; git push
```

**Trene ML** (fra noen hundre tilbakemeldinger, spredt over vær og årstider)
```powershell
python scripts\train.py --weather data\raw\<vær>.csv --labels supabase --torch --save
git add models; git commit -m "Ny modell"; git push     # timesjobben bruker sklearn-modellen
```

**Sjekke varselet mot Frost**
```powershell
python scripts\verify_forecast.py                          # arkivet (vokser hver time)
python scripts\verify_forecast.py --historikk --skriv-rh   # flere år, oppdaterer fuktighetskorreksjonen
```

**Sjekke drift i Supabase**
```sql
select felt, generert from public.varsel_siste;
select count(distinct generert) as kjoringer, max(generert) from public.varsel;
select * from public.observasjoner where kilde not in ('dev','test') order by registrert desc limit 20;
select count(*) from public.stasjon_maling;
```

## 11. Gjenstående, i prioritert rekkefølge

1. **Få timesjobben til å gå av seg selv.** Sjekk Actions-fanen. Hvis GitHub fortsatt ikke starter den, kjør
   `supabase/valgfritt/cron_starter_github_jobb.sql` (krever et fine-grained GitHub-token med Actions: Read and write, lagt i Supabase Vault som `github_dispatch_token`).
2. **Legg inn `FROST_CLIENT_ID` som secret i GitHub**, så arkivkontrollen (`stasjon_varsel`/`stasjon_maling`) begynner å fylles.
3. **Kjør `export_site_stats.py` på nytt** og commit `web/data/modellstatistikk.json`, så «Om modellen» viser tall med fuktighetskorreksjonen.
4. **Få inn tilbakemeldinger.** Spre siden i klubben. Mål: 150-400 per felt, også etter regn og i dårlig vær.
5. **Kalibrer per felt** (3 parametre) når det er nok, og vurder å kalibrere `rh_korreksjon_styrke`.
6. **Vis usikkerheten** i nettsiden: «Tørt fra ca. kl 14 (± 2 t)» eller myke overganger i timestripa. Sommervarsler
   er mer usikre enn vintervarsler.
7. **Følg med på 2026-fuktigheten** (7.6). Kjør `--historikk --skriv-rh` på nytt om et halvt år.
8. **Sjekk geometrien:** helningen på Helleneset (70° er anslått), om Ekstraveggen bør deles i bratt del og sva
   (høyre side er delvis sva), og bergarten via NGUs berggrunnskart. **Retningene i nettføreren er oppdatert**
   (2026-10-29, noen med store forskjeller). Fem nye felt er lagt til (2026-10-29): Neseveggen
   (felt_id 11), Bolstadøyri (64), Trollkona (114), Loddefjord (2) og Bymuren (1), med oppskrift i
   `docs/LEGG_TIL_FELT.md`. Gjenstår: `face_azimuth_deg` for de tre første feltene etter de nye retningene.
   Verdiene må komme fra eieren; nettførerens database skal ikke røres.
9. **Fargene for «is» og «vått»** (fiolett og blå) kan nesten ikke skilles for fargeblinde (protanopi, ΔE 2.7,
   målt med dataviz-validatoren), og gul «fuktig» har kontrast 1.4:1 mot hvitt. Nettsiden bruker derfor
   bokstaver og tabell i tillegg, men paletten bør vurderes (`globals.css`, `forhold-*`).
10. **Tren ML** når det er nok etiketter. Legg `torch` (CPU) i workflowen hvis PyTorch-modellen skal i produksjon.
11. **Data uten skjevhet:** tidsforløpskamera eller billig fuktsensor på én vegg i et par måneder.
12. **Rydd varselarkivet før det fyller gratisnivået.** Målt 210 byte per rad med indekser; med 8 felt × 49
    ledetider × 24 kjøringer blir det ca. 2 MB/døgn, ca. 720 MB/år, mot 500 MB i Supabase gratis (ca. 90 MB/år
    per felt). Slett rader eldre enn ca. 120 dager, eller lagre færre ledetider (`ARKIV_MAKS_LEDETID`;
    «Varslet dagen før» trenger bare ~24 t). (Bryteren `KLATREFORHOLD_DATAKILDE` er laget:
    Docker bruker `api` som standard, altså varselet fra API-containeren; sett `supabase` i `.env` for å lese
    `varsel_siste` som produksjon. Arkivet og statistikken leses fra Supabase uansett når nøklene finnes.)
13. **Modellforbedringer fra `RESEARCH_2.md`** (ikke gjort):
    - Kalibrer én tørkeparameter per felt (log-multiplikator på fordampningen), lagrene faste, delvis
      pooling mellom feltene (half-normal(0, 0.5)), ordinal likelihood for tørt/fuktig/vått. Tell regnbyger,
      ikke rapporter; 10-20 rapporter 2-30 t etter regn per felt flytter én parameter.
    - Ett-trykks «stemte»-knapp, så ikke bare overraskelser blir rapportert, og planlagte sjekker etter regn.
    - Evaluering: RPS/Brier, CORP-pålitelighetsdiagram, lag etter timer siden regn (0-6/6-24/24-72/>72),
      kryssvalidering per regnbyge, «timer siden regn > X» som grunnlinje.
    - Usikkerhet: Open-Meteo har ikke MEPS. Billigst: kjør modellen på varselet forskjøvet −3…+3 t (feilen er
      mest timing). Legg til `probability_of_precipitation` fra Locationforecast (MEPS). Kalibrer på arkivet.
    - Fasit uten skjevhet: solcelle-4G-kamera (ca. €200-280) mot én vegg, bilde hver 30. min, merket av 2-3
      medlemmer; valgfritt Dragino LMS01 bladfuktsensor (ca. €90, LoRaWAN).
    - Små ting: et lite slagregn-gulv for le-vegger; vurder en fjerde rapportklasse «siger».
14. **Senere:** integrasjon i nettføreren. FastAPI kan deployes som egen tjeneste, observasjonene kan flyttes til
    nettførerens database, og komponentene i `web/components` bruker samme design-tokens.

## 12. Kreditering

Værdata fra MET Norway (CC BY 4.0 / NLOD), via Open-Meteo (CC BY 4.0). Målinger fra Frost (MET Norway).
Høydedata © Kartverket (CC BY 4.0).
