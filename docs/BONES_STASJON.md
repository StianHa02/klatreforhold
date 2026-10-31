# Bønes værstasjon som datakilde

Vurdering 31.10.2026 av om den private værstasjonen på Bønes kan brukes av modellen, særlig for Ekstraveggen.
Tallene kommer fra `modeling/scripts/evaluer_bones.py` (se [Kjøre på nytt](#kjøre-på-nytt)).

## Sammendrag

Bønes værstasjon (Davis Vantage Pro2 Plus, [weather.kippenbroeck.no](https://weather.kippenbroeck.no/))
er en privat stasjon som vi ikke drifter. Vi har bare det som er offentlig: API-et med siste måling
(`/api/naa.php`), [databasedokumentasjonen](https://weather.kippenbroeck.no/database.md) og en kopi av databasen
fra 31.10.2026. Vi kan ikke endre stasjonen, sensorene eller nettsiden. Stasjonen står 1,3 km fra Ekstraveggen og 5,1 km fra Loddefjord. Florida (SN50540), som Ekstraveggen kontrolleres mot i dag,
står 5,6 km unna. Stasjonen har målt hver femte minutt siden 2013 og hadde data i 99,9 % av timene
2023–2026.

| Bruk | Anbefaling |
|---|---|
| Kontroll for Ekstraveggen | **Ja, for nedbør og temperatur.** Nærmeste stasjon, stabil drift, og regnet følger Florida tettere enn MET Nordic gjør. Krever en historikkkilde (se under). |
| `erstatt` for nedbør | **Kanskje, etter test.** Stasjonen kan gi bedre tidspunkt for når regnet slutter, men måler 20–30 % mindre enn modellen vinter og vår. |
| `erstatt` for temperatur, fuktighet og vind | **Nei.** Vinden er 2 m/s lavere enn både Florida og modellen, og fuktighetssensoren viser for høyt i tørr luft. |
| Fuktighetskorreksjonen | **Behold den.** Bønes er 5,5 prosentpoeng fuktigere enn Florida, mest i tørr, blåsende luft. Det peker mot sensoren, ikke mot at Ekstraveggen er fuktigere. |

## Data og metode

- **Stasjonen**: kopi av weewx-databasen (`weewx.sdb`, 31.10.2026), 2023-01-01 – 2026-10-30, 402 612
  femminuttsrader. Databasen er i US-enheter og regnes om. En rad er slutten av intervallet, så timen som
  slutter kl. T er radene i (T−1 t, T], samme regel som modellen bruker. Timer med færre enn 10 av 12 rader
  er manglende. Vindretningen er et vektorsnitt vektet med fart.
- **Modellen**: MET Nordic fra Open-Meteos historiske varsler (`metno_seamless`) ved stasjonen, Ekstraveggen
  og Loddefjord, samme kilde som `verify_forecast.py --historikk`.
- **Mål**: samme funksjoner som Frost-kontrollen i `verify.py` (`scores`, `rain_windows`, `rh_bias_table`).
  Regntime er minst 0,2 mm. Fortegn er alltid varsel − målt.
- **Kontroll av innlesingen**: snittemperatur januar 2026 (−1,33 °C), nedbør 2020 (2 179 mm) og
  regnintensitetsrekorden (215,1 mm/t 26.08.2023 16:30) stemmer med stasjonens egen
  [databasedokumentasjon](https://weather.kippenbroeck.no/database.md). Oktober 2026 (240,3 mm) er sjekket
  direkte i databasen.
- **Frost**: Florida (SN50540) time for time fra Frost, samme periode, 33 552 timer. Brukes til å sammenligne
  stasjonene direkte og til å skille sensorfeil fra ekte forskjeller mellom stedene.

## Resultater

### Drift

Data i 99,9 % av timene. Ett lengre avbrudd: 05.03.2025 23:00 – 06.03.2025 20:00 (21 timer). I tillegg mangler
én time hver høst når klokka stilles tilbake (f.eks. 25.10.2026 02:00–03:00): Davis-loggeren lagrer på lokal tid
og hopper over den doble timen. Det er ufarlig, men må ikke fylles med null nedbør.

API-et (`/api/naa.php`) svarte med en måling som var 104–126 sekunder gammel. Det gir bare siste måling, ikke historikk.

### Hele perioden, time for time

| Værserie mot Bønes | Temp MAE / skjevhet (°C) | RH MAE / skjevhet (pp) | Vind MAE / skjevhet (m/s) | Treff regn | Falsk regn | mm-forhold |
|---|---|---|---|---|---|---|
| MET Nordic ved Bønes | 0,74 / −0,42 | 5,8 / −2,5 | 1,84 / +1,81 | 0,625 | 0,336 | 1,18 |
| MET Nordic ved Ekstraveggen | 0,57 / −0,18 | 5,9 / −2,7 | 1,78 / +1,76 | 0,625 | 0,336 | 1,18 |
| MET Nordic ved Loddefjord | 0,59 / −0,16 | 6,0 / −1,6 | 1,74 / +1,72 | 0,616 | 0,339 | 1,15 |

33 576 timer, 6 980 målte regntimer. MET Nordic gir samme nedbør ved Bønes og Ekstraveggen: avstanden er
mindre enn det modellen skiller. Over 6 og 24 timer treffer modellen 78 % og 91 % av vinduene med regn
(falsk 20 % og 10 %), og døgnsummene korrelerer med 0,85.

### Per sesong (MET Nordic ved Bønes)

| Sesong | Temp skjevhet | RH skjevhet | Treff regn | Falsk regn | mm-forhold | Treff 24 t |
|---|---|---|---|---|---|---|
| Vinter | −1,01 | −3,1 | 0,639 | 0,356 | 1,40 | 0,915 |
| Vår | −0,25 | −1,7 | 0,659 | 0,347 | 1,26 | 0,923 |
| Sommer | +0,18 | −3,0 | 0,591 | 0,321 | 0,96 | 0,859 |
| Høst | −0,67 | −2,1 | 0,616 | 0,318 | 1,13 | 0,939 |

### Nedbørmengde

Over 46 hele måneder ga MET Nordic 7 757 mm og stasjonen 6 601 mm (forhold 1,18). Forskjellen er størst
om vinteren (1,40; enkeltmåneder opptil 1,92 i januar 2025) og forsvinner om sommeren (0,96). Det passer med
at en uoppvarmet vippekarmåler fanger for lite i vind og snø. Om sommeren måler stasjonen like mye eller mer, så
modellen gir ikke for mye regn generelt. Vintertallene fra stasjonen er for lave til å brukes direkte.

### Når starter og slutter regnet?

For tørking teller når regnet slutter. 729 regnepisoder på minst 1 mm ved Bønes (opphold opptil 2 timer
slått sammen), mot MET Nordic innen ±3 timer:

| Værserie | Funnet | Start innen ±1 t | Slutt innen ±1 t | Median slutt-feil (abs) |
|---|---|---|---|---|
| Ved Bønes / Ekstraveggen | 91 % | 53 % | 50 % | 1 t |
| Ved Loddefjord | 91 % | 54 % | 49 % | 2 t |

Modellen har ingen fast forsinkelse (median 0 timer), men i halvparten av episodene bommer slutten med mer enn
en time. Største episode siste 90 dager, 04.10.2026 (74,9 mm målt, 78,6 mm varslet): modellen sluttet sju timer
for tidlig. Det er her en lokal regnmåler kan gjøre mest nytte.

### Luftfuktighet

MET Nordic er 2,5 prosentpoeng **tørrere** enn Bønes over alle timer, mest om morgenen (−4,4 kl. 06–12) og
om vinteren. Fordelingen er ellers lik (median 83 mot 87 %, p95 97 mot 97 %), så stasjonen ser ikke ut til
å henge seg opp nær metning.

Korreksjonen i `config/stasjoner/rh_korreksjon.yaml` er tilpasset mot Florida, der MET Nordic var for
**fuktig**, og gjelder alle felt med `frost_station: SN50540`, også Ekstraveggen. Ved Bønes gjør den
avviket større:

| | Uten korreksjon | Med SN50540-korreksjon |
|---|---|---|
| Alle timer | −2,5 | −4,4 |
| Kl. 12–18 | −2,5 | −6,4 |
| Juli | −3,5 | −6,3 |

Sammenligningen med Florida (under) viser at det mest er sensoren på Bønes, ikke stedet. Korreksjonen beholdes.

### Bønes mot Florida

Målt mot målt, Bønes − Florida, 5,6 km mellom stasjonene:

| Utvalg | Timer | Temp (°C) | RH (pp) | Duggpunkt (°C) | RH median Bønes / Florida |
|---|---|---|---|---|---|
| Alle timer | 33 527 | −0,01 | +5,5 | +1,1 | 86,7 / 81,0 |
| Vind ≥ 6 m/s, oppholdsvær | 2 787 | −0,26 | +9,6 | +2,0 | 71,9 / 61,0 |
| Regn begge steder (≥ 0,5 mm) | 3 577 | −0,08 | +4,1 | +0,6 | 94,8 / 91,0 |
| Rolig natt (< 2 m/s, kl. 00–06) | 3 377 | +0,40 | +1,0 | +0,6 | 89,8 / 88,0 |
| Ettermiddag (kl. 12–18) | 8 382 | −0,03 | +7,3 | +1,6 | 78,6 / 70,0 |

Etter fuktighetsnivået hos Florida er forskjellen +9,6 under 60 %, +4,5 ved 80–90 % og +0,5 ved 95 % og over.

Temperaturen er den samme på de to stedene. Fuktigheten er det ikke, og forskjellen er størst i blåsende
oppholdsvær. Da er lufta godt blandet, og duggpunktet bør være nesten likt over noen km. Her er det 2 °C høyere på
Bønes. Forskjellen er nesten borte nær metning og i rolige netter. Det passer med en sensor som viser for høyt i tørr
luft og riktig når lufta er mettet, noe aldrende Davis-sensorer er kjent for. En ekte forskjell mellom stedene ville
vært størst i rolig vær, ikke i vind. Florida er en offisiell MET-stasjon og regnes som riktig.

MET Nordic ser også Bønes som litt fuktigere enn Florida, men bare 1,2 prosentpoeng (+3,0 mot +1,8 i skjevhet mot
Florida). Korreksjonen fra Florida er derfor fortsatt det beste for Ekstraveggen. Fuktigheten fra Bønes bør ikke brukes, verken til kontroll eller `erstatt`. Eieren kan få beskjed om sensoren,
men vi kan ikke regne med at den blir byttet.

Nedbør, time for time mot Florida:

| Mot Florida | Treff regn | Falsk regn | mm-forhold | Treff 6 t / falsk 6 t | Korr. døgnsum |
|---|---|---|---|---|---|
| Bønes målt | 0,767 | 0,211 | 0,70 | 0,860 / 0,095 | 0,946 |
| MET Nordic ved Florida | 0,669 | 0,314 | 0,90 | 0,810 / 0,161 | 0,887 |
| MET Nordic ved Bønes | 0,638 | 0,303 | 0,82 | 0,782 / 0,153 | 0,873 |

Regnmåleren på Bønes, 5,6 km unna, følger timene med regn hos Florida bedre enn MET Nordic gjør på Floridas egne
koordinater. Regnet treffer de to stedene stort sett samtidig, og vippekarmåleren registrerer når det regner godt.
Bønes får 30 % mindre regn enn Florida. Det er dels mindre regn mot vest, dels at måleren fanger for lite.

Vinden er 2,05 m/s lavere på Bønes enn hos Florida, mens MET Nordic treffer Florida (skjevhet 0,01). Det
bekrefter at anemometeret står skjermet.

### Påvirker det modellen?

Modellen kjørt for Ekstraveggen 2023–2026 to ganger: med MET Nordic-regn, og med Bønes-regn der stasjonen har
målinger (som `with_observations()` gjør). Alt annet er likt. Det sier hvor mye stasjonen endrer varselet, ikke hvilken
av de to som har rett.

- Dagtid (kl. 08–20) gir de samme status i 88 % av timene. Tørt i 49,7 % av timene med MET Nordic-regn og 52,6 % med
  Bønes-regn, fordi stasjonen måler mindre regn.
- Etter 477 regnepisoder flytter Bønes-regnet tidspunktet veggen blir tørr i 86 % av episodene, like ofte tidligere (41 %)
  som senere (44 %). I 43 % av episodene er forskjellen mer enn tre timer.
- Om vinteren sier modellen is med MET Nordic-regn, men tørt med Bønes-regn, i 300 timer på dagtid. Det er snø som
  vippekarmåleren ikke fanger, så Bønes-regn kan ikke brukes alene når det kan være snø.

Forskjellen er stor nok til at det er verdt å finne ut hvilken av dem som treffer veggen best.

### Vind

MET Nordic blåser 1,8 m/s mer enn stasjonen, hele året. Anemometeret står trolig lavere enn 10 m og mer
skjermet. Retningen avviker med en fast median på +19° (91 % innen 45°). Det kan skyldes hvordan vindfanen er rettet inn,
eller terrenget. Vindstyrken fra stasjonen kan ikke erstatte modellens: `wind_exposure` og slagregnet er tilpasset 10 m-vind.

## Begrensninger

- Ett målepunkt, ikke på veggen. Stasjonens plassering og høyde over havet er ikke kjent i dette arbeidet.
- Vippekarmåleren fanger for lite i vind og snø, og snø kan bli registrert først når den smelter.
- Fuktighetssensoren på Bønes viser for høyt i tørr luft (se over). Florida er referansen.
- API-et har bare siste måling, og vi kan ikke legge til et historikk-endepunkt. Live bruk krever at timesjobben
  lagrer hver måling selv. Da blir det ingen historikk før den starter, og hull når Actions-jobben kommer sent
  eller ikke kjører. Nedbør per time må regnes som differansen i `nedbor_i_dag_mm` mellom to kjøringer, og gjelder
  bare når de ligger omtrent en time fra hverandre.

## Bønes-regn i modellen

Det er lavsesong, og det kommer neppe 50 observasjoner fra Ekstraveggen før neste år. Regnmåleren er likevel
det beste vi har for når regnet starter og slutter ved veggen, så den er bygd inn, men står av til den er prøvd.

- **Innsamling.** Timesjobben henter siste måling fra `/api/naa.php` og lagrer den i `bones_maling`
  (`publish.collect_bones()`), når minst ett felt har `regnmaler: bones`. Bare ferske målinger lagres. Feil gir en
  advarsel i `_bones` og stopper aldri varselet. Én henting i timen er godt innenfor API-ets ønske om høyst hvert 5. minutt.
- **Timeverdier** (`data/bones.py`). Nedbør per time er differansen i `nedbor_i_dag_mm` mellom to målinger 45–75
  minutter fra hverandre i samme døgn. Timen over midnatt, timer etter en kjøring som falt ut, og en teller som går
  ned blir ukjent, ikke null.
- **Bytte av regn.** Med `regnmaler_bruk: erstatt` bytter `with_rain()` modellens nedbør i passerte timer der
  Bønes har målt og det er over +2 °C (ellers kan det være snø). Varseltimene, temperatur, fuktighet, vind og
  stråling kommer fortsatt fra MET Nordic. Byttede timer får `precipitation_source = "bones"` i `vaer`, og
  `kilde` i varselet krediterer stasjonen.
- **Signatur.** Regnmåleren tas med i `config_hash` bare med `erstatt`. Å slå på innsamling endrer ikke lagret
  modelltilstand. Å slå på `erstatt` starter Ekstraveggen på nytt med 30 døgns innkjøring én gang.

Ekstraveggen har `regnmaler: bones` og `regnmaler_bruk: av`. Før `erstatt` slås på:

1. Kjør migrasjonen `20261031210000_bones_maling.sql` i produksjon.
2. La innsamlingen gå gjennom vinteren, og sammenlign Bønes-regnet med `vaer` (radar og MET Nordic) for samme timer.
3. Legg til Bønes værstasjon (CC BY 4.0) i kildene på nettsiden (`web/app/layout.tsx` og om-siden).
4. Sett `regnmaler_bruk: erstatt` i `config/ekstraveggen.yaml`.

Når det finnes nok observasjoner, er testen fortsatt den samme: kjør modellen med begge regnkildene mot
observasjonene, med en ny kopi av databasen fra eieren.

## Kjøre på nytt

Fra `modeling/`, med en kopi av databasen (se «Ta en kopi av databasen» i stasjonens dokumentasjon):

```sh
python scripts/evaluer_bones.py --db ~/Desktop/weewx-2026-10-31.sdb   # med Florida når FROST_CLIENT_ID er satt
python scripts/evaluer_bones.py --db weewx.sdb --start 2024-01-01 --slutt 2026-10-30 --uten-api
```

Databasen åpnes skrivebeskyttet. MET Nordic-hentingen lagres i `data/raw` og `data/cache`, og tabellene i
`outputs/bones_*.csv`.

Data: Bønes værstasjon, weather.kippenbroeck.no (CC BY 4.0). MET Norway via Open-Meteo (CC BY 4.0).
