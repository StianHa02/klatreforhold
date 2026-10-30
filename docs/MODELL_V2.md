# Modell v2: undersøkelse, endringer og feltkontroll

Status 30. oktober 2026. Implementert på `feat/bergen-conditions-v2`, basert på `main` ved `9db616c`.
Alle ni felt fra main er med. Dette dokumentet beskriver den nye modellen; eldre resultater i
`MODEL.md` og `OVERLEVERING.md` gjelder v1. Migrasjonen ble kjørt i Supabase 30. oktober 2026.

## Sammenligningen med 8a.nu / Vertical-Life

[Lanseringen av Conditions](https://www.8a.nu/news/new-on-vertical-life-web-conditions-2ib6b) beskriver
tørking, vind, luftfuktighet, sol og læring fra bestigningsdager. Undersøkelsen av den offentlige
klienten viste også vær fra Open-Meteo og utdata for bergtemperatur, fuktighet/frost og sol/skygge.
Dette viser hvilke størrelser tjenesten bruker, men avslører ikke beregningene på serveren.
Ligninger, parametre, treningsdata og uavhengige feilrater er ikke offentlig dokumentert i materialet
som ble undersøkt. Vi kan derfor sammenligne innhold og fysisk rimelighet, men ikke fastslå at vår
modell er like treffsikker eller bedre. Bestigningsdager er heller ikke direkte målinger av vått berg.

Vår modell har et etterprøvbart regnskap for nedbør, kondens, fordampning, siging, is og snø.
Den gir et godt grunnlag for lokale forbedringer. Treffsikkerheten må måles mot faktiske forhold,
helst også når folk vanligvis lar være å klatre.

## Retning, bratthet og sol

Asimut er veggens utadrettede normal, med grader fra sann nord. Helning måles fra vannrett:
90° er vertikalt, større verdier er overheng. Kilden er den offentlige BKK-nettføreren, med dato og
URL i hver YAML-fil. Kartverkets DTM ble brukt til å kontrollere veggfot og geometri; DOM inkluderer
trær og bygninger i horisonten. Kartdata representerer ikke nødvendigvis dagens løvverk.

| Felt | Retning | Helning | Bratthet fra nettføreren |
|---|---:|---:|---|
| Ekstraveggen | 322° | 90° | vertikalt |
| Helleneset | 274° | 70° | sva |
| Sandviken | 195° | 90° | vertikalt |
| Neseveggen | 195° | 100° | overheng |
| Bolstadøyri | 213° | 90° | vertikalt |
| Trollkona | 225° | 110° | meget overhengende |
| Loddefjord | 266° | 110° | meget overhengende |
| Bymuren | 218° | 100° | overheng |
| Fabrikkveggen | 193° | 90° | vertikalt |

70°, 100° og 110° er foreløpige kategorianslag, ikke oppmålte helninger. Sandviken har også vestvendte
sektorer. Ett representativt plan kan ikke beskrive alle rutene på et felt.

Ekstraveggens retning er korrigert fra 300° til 322°, Helleneset fra 270° til 274° og Sandviken fra
270° til 195°. Horisontberegningen bruker nå geodetiske stråler, ikke kartgridets nord som sann nord.
Forskjellen er rundt 8,4° ved Bergen. Hele horisonten beholdes, og overheng behandles gjennom den
faktiske flatenormalen. Diffus solstråling beregnes fra synlig himmel, mens reflektert stråling beregnes
én gang. Den samme himmelfaktoren brukes i langbølget stråling.

Rapporten om sol kl. 09–15 på Ekstraveggen kan ikke forklares med en sommertidsfeil alene; den flytter
klokken én time. En vertikal nordvestvendt hovedvegg får heller ikke direkte sol fra kl. 12 med denne
geometrien. [BKKs feltartikkel](https://bergenklatreklubb.no/manedens-klatrefelt-ekstraveggen/) beskriver
sen ettermiddagssol og vertikal klatring med sva til høyre. Kontrollberegningen for 21. juni 2026 gir
geometrisk mulig sol omtrent kl. 16:20–21:00. Den 30. oktober er det bare et kort mulig vindu rundt
kl. 16:10. Dette er klarværsgeometri, ikke en lovnad om sol gjennom skyene.

`sol_mulig` beskriver geometrien. `sol_pa_veggen` krever i tillegg mer enn 20 W/m² direkte stråling på
flaten. Produksjonen vurderer midten av hver foregående time; svært korte solvindu kan falle mellom
tidspunktene. Det opprinnelige avviket er ikke entydig forklart uten dato og angitt del av veggen.
Bruk feltkontrollen under før retningen endres igjen.

## Regn, tørking og vinter

- Sva tar imot mer fallende nedbør. Overheng reduserer direkte regn og slagregn; kategori 3 og 4 har
  foreløpige faktorer 0,2 og 0,05. `rain_sheltered` gir ytterligere skjerming. Dette er anslag som må
  prøves mot observasjoner. Siging og kondens kan fortsatt gjøre en skjermet vegg våt.
- Avrenning ovenfra har en egen inngang. `overhang_runoff_factor` kan overstyres uten å endre hvor
  mye vinddrevet regn som treffer flaten. Nedbørsmagasinet for siging tømmes kontinuerlig; vann over
  terskelen er ikke lenger et brått av/på-utslipp.
- Vindeksponering for de tre opprinnelige feltene er foreløpig 0,4 / 0,8 / 0,5 for Ekstraveggen /
  Helleneset / Sandviken. Mer vind gir både mer slagregn og raskere tørking. Verdiene er lokale
  terrenganslag, ikke tilpasset managerens generelle inntrykk som om det var måledata.
- Flytende vann, is og snø har egne lagre. Frysing frigjør smeltevarme; smelting bruker varme og gir
  flytende vann som senere må tørke. Rim og sublimasjon bruker metning over is. Drenering fra
  sigereservoaret låses ved frost, og snø ovenfor kan tilføre smeltevann. Dette er en enkel temperaturmodell,
  ikke en detaljert snø- eller grunnvannsmodell.
- Kaldt, tørt berg får ikke automatisk status `is`. Statusen krever modellert is/snø på flaten.
  Som resten av modellen er dette et anslag for hovedveggen, ikke en vurdering av hver rute.
- Starttilstanden bruker bare tidligere vær. Gyldige lagrede tilstander videreføres mellom kjøringer;
  ellers brukes rundt 30 døgn innkjøring, utvidet mot 90 døgn ved kulde innenfor leverandørens grense
  på 92 døgn bakover. Oppstart uten lagret tilstand merkes usikker. Historiske grafer utelater de
  første 90 døgnene.

Hvis leverandøren mangler de eldste timene i en utvidet innkjøring, brukes den sammenhengende
tilgjengelige starten bare når det fortsatt er minst 30 døgn før visningshistorikken. Bolstadøyri
hadde dette avviket i livekontrollen. Hull inne i serien eller for kort innkjøring stopper fortsatt
modellen; ukjent nedbør blir ikke gjort om til opphold.

[RoadSurf 1.1](https://gmd.copernicus.org/articles/17/4837/2024/) støtter valget av energibalanse,
terrengskjerming og separate vann-/vinterprosesser. En klatrevegg har andre vannveier enn en vei;
parametrene kan ikke overføres direkte. Bergtemperaturen er fortsatt en forenklet overflate med et
langsomt temperaturledd innenfor, ikke en full varmeledningsmodell gjennom fjellet.

## Bergart

NGUs offentlige [berggrunnstjeneste](https://geo.ngu.no/mapserver/BerggrunnWMS3?SERVICE=WMS&REQUEST=GetCapabilities)
ble kontrollert ved koordinatene. Alle ni YAML-filene har karttolket bergart. Ekstraveggen ligger i
øyegneis/flasergneis, Helleneset i migmatitt/migmatittgneis, og Sandviken nær en grense mellom
gneisenheter. Loddefjord ligger også nær en kartgrense.

Bergart kan påvirke varmeledning og fukttransport, men kartnavnet forteller ikke sprekketetthet,
forvitring, ruhet, jordmagasin eller hvor vannet kommer ut. Standardverdiene for varmeledning
(2,5 W/mK) og volumetrisk varmekapasitet (2,2 MJ/m³K) er beholdt som plausible utgangspunkter for
krystallinsk berg. Det er ikke lagt inn vilkårlige forskjeller i porøsitet eller tørking mellom
gneisvariantene. En studie av [granittens anisotrope fukttransport](https://link.springer.com/article/10.1007/s10064-024-03935-z)
illustrerer hvorfor lokale egenskaper må måles fremfor å avledes fra bergartsnavnet alene.

## Offentlige værkilder og sporbarhet

Direkte [MET Nordic](https://github.com/metno/NWPdocs/wiki/MET-Nordic-dataset) foretrekkes for den
korte prognosen og nylige analyser. Open-Meteo `metno_seamless` gir sammenhengende historikk og
reserve, samt ECMWF etter den korte MET-prognosen. Derved beholdes fem døgn fremover og sju døgn
visningshistorikk fra main. Nedbør fra fersk [MET Nowcast](https://docs.api.met.no/doc/nowcast/datamodel.html)
erstatter bare de delene av de neste to timene som faktisk dekkes. Utdaterte radardata brukes ikke.
Ingen av disse tre kildene trenger privat API-nøkkel.

Live MET-kontroll avdekket at prognosens strålingsfelt akkumulerer fra modellstart. De differensieres
og deles på 3600; analyser inneholder én time. Første ukjente prognoseintervall blir ikke tolket som
null regn eller null stråling. Manglende nedbør fylles aldri med null. Korte innvendige hull i temperatur,
fuktighet og vind kan interpoleres; vindretning behandles sirkulært. Udekkede nødvendige værdata
avbryter det aktuelle feltet slik at siste publiserte prognose beholdes.

Produksjonskontrollen viste små negative differanser i akkumulert solstråling ved skumring
(Bymuren: −0,14 W/m²). Inntil 1 W/m² negativ differanse settes til null; større negative sprang
avvises fortsatt som mulig nullstilling. Reserveloggen oppgir felt og konkret feilmelding.
THREDDS brukte mer enn 20 sekunder på et samlet prognoseuttrekk med ni variabler.
Prognosen hentes derfor i tre mindre uttrekk fra samme låste modellkjøring; livekontrollen brukte
8–10 sekunder per uttrekk. Tidsaksene må stemme før delene settes sammen. Tidsavbrudd gir fortsatt reserve.

Fuktighetskorreksjonen som ble tilpasset Open-Meteo mot Frost brukes bare på den kilden.
Den overføres ikke ukritisk til direkte MET. Hver time har vær- og nedbørskilde, og prognose,
arkiv, kalibrering og lagrede tilstander har modellversjon/konfigurasjonssignatur.
Open-Meteos [historiske prognoser](https://open-meteo.com/en/docs/historical-forecast-api) er sammensatte
serier, ikke et arkiv over hva vår tjeneste faktisk varslet. Arkivert treffsikkerhet må derfor bruke
prognosene som ble lagret ved utsendelse.

## Hva grafen om tørketid nå betyr

En episode krever minst 2 mm nedbør over 12 timer, fulgt av tre timer med mindre enn 0,2 mm/time.
Et felt som allerede er tørt etter regnet får null timer. Nytt regn før tørking, fortsatt vått etter
72 timer og manglende slutthistorikk telles som egne utfall. Is/snø-episoder telles separat.
Tidligere utelot grafen episoder med nytt regn, og kunne registrere uavsluttet tørking som 73 timer.

Median og kvartiler gjelder nå uttrykkelig episodene som tørker før nytt regn innen 72 timer.
Antall øvrige utfall og andel tørre innen 6/12/24 timer vises også. Kort betinget tørketid betyr ikke
at et felt oftere er tørt totalt. Alle ni felt har både lokalt vær og et kontrollforsøk med samme vær.

[Trinnvis sammenligning med v1](MODELL_V2_RESULTATER.md) bruker samme værår per felt.
I sluttmodellen har Ekstraveggen flere våte dagtimer enn Helleneset om vinteren (70,54 mot 67,54 %),
men litt færre om sommeren (31,48 mot 32,24 %). Dette er simulering, ikke validering av managerens
erfaring. Forskjellen er beholdt og må undersøkes med faktiske observasjoner.

## Feltkontroll på Ekstraveggen

Besøk omtrent annenhver dag er nyttige, særlig når besøkene også omfatter våte dager.
`Tørt` betyr at den representative hovedveggen er tørr; en enkelt tørr eller våt rute avgjør ikke status.

1. Velg en fast del av hovedveggen som kan sees ved hvert besøk. Noter ruter/sektor første gang.
2. Registrer faktisk lokal dato og klokkeslett og `tort`, `fuktig`, `vatt` eller `is` i nettsidens skjema.
   Se helst på veggen før du leser prognosen. Ikke gjett på timer du ikke har observert.
3. Ta samme oversiktsbilde og noter ved behov vannfilm, våte tak, aktive sigestriper og forskjeller
   mellom hovedveggen og svaet til høyre. En vurdering fra bilen må merkes som usikker i egne notater.
4. Etter noen regnvær: prøv ekstra besøk innen 6, 12 og 24 timer etter opphold, også når det fortsatt
   er vått. Siste våte og første tørre observasjon avgrenser tørketiden; de gir ikke et eksakt tørketidspunkt.
5. For solavviket: noter dato, klokkeslett, hvilken del av veggen som er belyst, og om solen er bak skyer.
   Bilder rundt kl. 12, 15 og senere ettermiddag er spesielt nyttige. Fravær av sol i overskyet vær kan
   ikke brukes som bevis for terrengskygge. Sammenlign gjerne med en fast del av Helleneset samme dag.

Kalibreringen tilpasser først bare `evaporation_efficiency`. Før en tilpasning kan tas i bruk kreves
minst 50 observasjoner fra ti uavhengige regnepisoder, begge tilstandsklasser i trening og kontroll, bedre Brier-score på
andre episoder og ingen økning i feilvarsler om tørt. Mange rapporter fra samme regnvær er ikke mange
uavhengige forsøk. Modellversjon og konfigurasjon må stemme. Gamle ML-/kalibreringsfiler aktiveres
ikke automatisk i v2. Ingen modell er trent på managerens generelle inntrykk eller syntetiske etiketter.

## Kontroll og utrulling

Gjennomført: 45 backendtester, frontendtester og TypeScript-kontroll. Testene dekker blant annet
masse-/overflateenergibalanse, frysing/tining, tidssteg, lagret tilstand, overheng, DST, manglende regn,
værreserver, radarintegrasjon og tørkeepisoder. Live kontroll har gitt 121 prognosetimer og 168
historikktimer, med direkte MET og reservekilde. Grafer er regenerert for alle ni felt.
En full test av timesjobben under MET-tidsavbrudd ga komplette prognoser for åtte felt med reservekilden.
Bolstadøyri avdekket den kortere innkjøringshistorikken; etter rettelsen ga en ny livekjøring også der
121 prognosetimer og 168 historikktimer. Ingen av disse kontrollene skrev til databasen.

Kommandoer fra `modeling/`:

```powershell
python -m pytest tests -q --disable-warnings
python scripts/check_model_v2.py --live --forecast
python scripts/compare_model_v2.py --baseline 9db616c
python scripts/export_site_stats.py
```

Fra `web/`: `npm test` og `npx tsc --noEmit`.

[`20261030090000_modell_v2.sql`](../supabase/migrations/20261030090000_modell_v2.sql) ble kjørt i
prosjektets Supabase 30. oktober 2026 før publisering av v2-koden. Den tillater isobservasjoner og legger til arkivmetadata og tabellen `modelltilstand`,
med tilgang bare for service role. Deretter kan grenen gjennomgås/merges, og én ordinær timesjobb
kontrolleres for ni felt, riktige kilder og modellversjon 2.0.0. Historiske arkivrader beholdes.
Databasemigrasjonen og en vellykket timesjobb må bekreftes ved utrulling; lokale tester alene
bekrefter ikke produksjonsstatus. Lokale Playwright-rapporter, agentinnstillinger, værdata og
byggecache holdes utenfor Git.
