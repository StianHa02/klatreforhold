# Legge til et klatrefelt

Oppskrift for agenter (og folk) som skal legge et nytt felt inn i varselet. Ett felt = én YAML-fil i
`modeling/config/`. Timesjobben, API-et og nettsiden finner feltet selv; det trengs ingen kodeendring.
Gjeldende kodeoversikt står i [overleveringen](OVERLEVERING.md).

Alle Python-kommandoer kjøres fra `modeling/`.

## 1. Hent feltdata fra nettføreren

Nettføreren (`https://ute.bergenklatreklubb.no/felt/<slug>`) viser bare kompassretning i teksten, men
sidekilden har tallene. Ikke rør nettfører-repoet eller databasen; les bare den offentlige siden:

```bash
curl -s https://ute.bergenklatreklubb.no/felt/<slug> -o felt.html
grep -oE '.{900}\\"slug\\":\\"<slug>\\",\\"kommentartype.{0,130}' felt.html | sed 's/\\"/"/g' \
  | grep -oE '"(orientering|bratthet_id|regnsikkert|koordinater)":("[^"]*"|[0-9.]+|true|false|\{[^}]*\})'
```

`felt_id` står i bildestiene (`/felt/<id>/topo/...`) og i feltlista i samme kilde
(`"id":<id>,"navn":"<Navn>","slug":"<slug>"`). Sjekk metoden mot et kjent felt først: Ekstraveggen skal gi
id 137, `60.334582, 5.312171`, orientering 322, bratthet 2.

Slugen er ikke alltid feltnavnet i ASCII: Bolstadøyri er `bolstadoeyri`. Finn den i oversikten
`https://ute.bergenklatreklubb.no/felt` hvis siden bare viser et tomt skall.

| Nettfører | YAML (`crag:`) |
|---|---|
| `koordinater.lat/lng` | `lat`, `lon` (full presisjon; avrundes til 4 desimaler i MET-kall) |
| `orientering` (grader, kompass) | `face_azimuth_deg` |
| `bratthet_id` 1 sva / 2 vertikalt / 3 overheng / 4 bratt overheng, tak | `face_tilt_deg` 70 / 90 / 100 / 110 (1, 3 og 4 er anslag; merk det i kommentaren) |
| `bratthet_id` | `steepness_id` (behold kategorien også når helningen er oppmålt; brukes til foreløpig regnskjerming) |
| `regnsikkert` | `rain_sheltered` |
| side-URL | `geometry_source`, og datoen i `geometry_checked` |

## 2. Lag YAML-fila

- **Filnavn = slug = ASCII, små bokstaver** (`bolstadoyri.yaml`). Filnavnet er nøkkelen i Supabase
  (`felt`-kolonnen), URL-en (`/felt/<slug>`) og tilbakemeldingene. Ikke bytt det senere.
- Kopier et eksisterende felt (f.eks. `helleneset.yaml`), så blokkene `horizon:` og `model:` med
  `sky_view_factor:` er med; `horizon_from_dem.py --write` krever at de finnes.
- Bare felt-YAML direkte i `config/`. Alt annet i en undermappe (`config/stasjoner/`, `config/kalibrert/`).
- Påkrevd: `name`, `lat`, `lon`, `face_azimuth_deg`. Resten har standardverdier (se `config.py`), men fyll
  inn `felt_id`, `elevation_m`, `face_tilt_deg`, `rain_sheltered`, `frost_station`, `geology`,
  `geometry_source`, `geometry_checked`.
- `elevation_m`: DTM-høyde i punktet. Raskest fra Kartverkets høyde-API:
  `curl "https://ws.geonorge.no/hoydedata/v1/punkt?koordsys=4258&nord=<lat>&ost=<lon>&geojson=false"`.
  Den brukes som bakkehøyde for horisonten, så den må være DTM (bakke), ikke DOM (trær og hus).
- **Sjekk at punktet er veggfoten.** Nettførerpunktet kan ligge midt i veggen eller 10–20 m ut fra den.
  Hent DTM i en linje gjennom punktet langs veggretningen (f.eks. −20, −10, −5, 0, 3, 6, 10, 20 m). Et sprang
  på titalls meter rundt punktet betyr at det ligger i veggen. Sett da `elevation_m` til bakken ved foten og
  bruk tilsvarende `--offset-m` i steg 4. Bolstadøyri: punktet er på 203 m, foten på ~169 m, 6 m ut.
  Ligger punktet ute foran veggen (flat bakke, så stiger det brått 10–20 m bak), står observatøren ute i
  skogen og får altfor lav `sky_view_factor`. Bruk negativ offset så den står 3 m fra foten:
  Trollkona `--offset-m=-10` (foten 13 m bak punktet), Loddefjord `--offset-m=-12` (15 m bak).
  En `sky_view_factor` under ~0.15 er et varsel om at noe er galt; sjekk med større `--min-dist-m` hvor mye
  som er trær helt inntil.
- `model:`: behold standardverdiene. Sett `wind_exposure` etter terrenget (skjermet skog ~0.4–0.5,
  åpen kyst ~0.8) og skriv at det er et anslag. Ikke legg inn kalibrerte verdier for hånd.

**Gotcha:** `fetch_history.py` navngir filer etter `name.lower()`, mens
`verify_forecast.py` og `export_site_stats.py` bruker filnavnet. For felt med æøå i navnet
(Bolstadøyri) må historikk-CSV døpes om til slugen. I v2 bruker `calibrate.py` samme filnavn og
konfigurasjonsmappe som `load_config`, også når feltnavnet har æøå.

## 3. Frost-stasjon

```python
from klatreforhold.data.frost import nearby_stations   # krever FROST_CLIENT_ID
print(nearby_stations(lat, lon, 8))
```

- Bergen: bruk `SN50540` (Bergen - Florida, MET). Den har ferdig tilpasset fuktighetskorreksjon i
  `config/stasjoner/rh_korreksjon.yaml`.
- Utenfor Bergen: nærmeste stasjon med lav høyde og helst samme dal. En ny stasjon har ingen
  fuktighetskorreksjon (korreksjonen blir 0) før noen kjører
  `python scripts/verify_forecast.py --historikk --skriv-rh`.
- `frost_bruk: kontroll` alltid. `erstatt` bare for stasjoner 1–2 km fra feltet.

## 4. Horisont fra Kartverket

```powershell
python scripts\download_dom.py --config config\<slug>.yaml             # DOM1, ±3 km
python scripts\horizon_from_dem.py --config config\<slug>.yaml --dem data\raw\dom1_<slug>.tif --write
```

- `download_dom.py` finner alle 15 km-ruter som overlapper utsnittet, laster ned de som mangler
  (~1.2 GB hver, CC BY 4.0 © Kartverket) og setter dem sammen. Felt nær en rutekant trenger to–tre ruter.
  Ruter som allerede ligger i `data/raw/` brukes på nytt; `--tile` tar en liste med ruter, og `--raw-dir`
  peker på en annen `data/raw` (f.eks. fra en git worktree). Rutene kan slettes etterpå; utsnittet holder.
  Spør eieren før du laster ned mange GB.
- `--write`, `physics/terrain.py` og 360°-horisonten finnes nå på main med fysikkmodell v2.
- `horizon_from_dem.py --write` skriver `horizon:` (sann nord, alle retninger, DOM med trær) og
  `sky_view_factor` inn i YAML-fila. Den feiler hvis mindre enn 95 % av en stråle ligger i rasteret; da er
  utsnittet for lite eller mangler en rute.
- Se over horisonten: høye verdier mot veggretningen betyr som regel at veggen selv eller trær rett foran
  er med (prøv `--offset-m`), og 0 overalt betyr at rasteret er tomt.
- I v2 beregnes himmelfaktoren fra helning og horisont under kjøring. Et overheng har mindre synlig
  himmel også uten terreng, så en lav verdi er ikke alene bevis på feil. Behold de kontrollerte
  veggfot-offsettene for Bolstadøyri/Fabrikkveggen (+6 m), Trollkona (−10 m) og Loddefjord (−12 m).
  Ikke erstatt dem med standarden +3 m uten ny terrengkontroll.

## 5. Sjekk

```powershell
python -c "from klatreforhold.predict import list_crags; print(list_crags())"
python scripts\predict_now.py --config config\<slug>.yaml
python scripts\publish_forecast.py --dry-run
python -m pytest tests
```

Status og soltimer skal virke rimelige for veggretningen (sørvendt får sol midt på dagen, nordvendt nesten
ikke om vinteren).

## 6. Etterpå

- Feltet vises på nettsiden når timesjobben har skrevet raden i `varsel_siste`. Ingen kodeendring.
- Plass: hvert felt legger ~90 MB/år til arkivtabellen `varsel` (49 ledetimer × 24 kjøringer/døgn × ~210 B
  per rad med indekser). Sjekk [gjeldende Supabase-grenser](https://supabase.com/pricing) og faktisk forbruk; modelltilstander
  og stasjonsdata kommer i tillegg, og retensjon må planlegges separat.
- Valgfritt: legg til en farge i `FELTFARGE` (`web/components/om/Diagrammer.tsx`); ellers brukes tekstfargen.
- Valgfritt: `python scripts\export_site_stats.py` (krever historikk-CSV, se gotcha over) for «Om modellen».
- Oppdater feltoversikten i README og geometritabellen i `docs/MODELL_V2.md`.
- Eieren committer selv. Gi kommandoene og list filene du har endret.
