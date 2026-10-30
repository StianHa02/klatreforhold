# Modellen: hvordan vi regner ut om veggen er våt

Oppdatering 30. oktober 2026: se [modell v2](MODELL_V2.md) for ny solgeometri, bratthet, værkilder,
vinterfysikk og tørkestatistikk, og [sammenligningen med v1](MODELL_V2_RESULTATER.md).
Resultatene nedenfor beskriver den tidligere modellen.

Vi har ingen sensor på veggen og ingen pålitelige observasjoner av "tørt/vått". Derfor starter vi
med en **fysisk modell** som bare trenger offentlige værdata. Den kan kalibreres og forbedres med
ML når vi får ekte observasjoner.

Prinsippet er det samme som i modeller for veibaneføre (METRo, Environment Canada) og bladfukt
i landbruket: en energibalanse gir temperaturen på overflaten, og en vannbalanse holder styr på
hvor mye vann som ligger på den.

## Hva gjør fjellet vått?

| Prosess | Hvordan modellen tar det med | Viktigste input |
|---|---|---|
| Regn rett på veggen | Slagregn på vertikal flate (Lacy / ISO 15927-3-familien): `R_vegg = α · U · R^0.88 · cos(D − θ)` når vinden blåser mot veggen. α = 0.12 som start (0.188 er målt i fritt felt i Bergen, vegger ligger på 0.02–0.26) | nedbør, vindstyrke, vindretning, veggens retning (300°) |
| Regn som treffer tak og hyller uansett vind | Fast andel av nedbøren (`direct_rain_fraction`) | nedbør |
| Vann som renner ned ovenfra | Fast andel av nedbøren (`runoff_from_above`) | nedbør |
| Kondens ("svett" fjell) | Når bergflaten er kaldere enn duggpunktet, kondenserer vanndamp på den. Bergtemperaturen beregnes med energibalanse, så modellen fanger at kaldt fjell henger etter når varm, fuktig luft kommer inn | lufttemp, luftfuktighet, stråling, skydekke |
| Siging | Et sakte reservoar fylles av nedbør og tømmes over dager; over en terskel gir det vann i sprekker | nedbør over flere døgn |

## Hva gjør fjellet tørt?

Fordampning fra flaten styres av forskjellen i vanndamp mellom en mettet bergoverflate og lufta:

`E = h_c / (ρ·c_p) · (ρ_v,mettet(T_berg) − ρ_v,luft)`,  med `h_c = 5.7 + 3.8·U` (W/m²K)

Det betyr at fjellet tørker raskere når:
- **sola står på veggen** (varmere berg → høyere metningstrykk). Ekstraveggen får sol først etter ca. kl 15:30–17.
- **det blåser** (større `h_c`).
- **lufta er tørr** (lavt duggpunkt).

Vann i tak og sprekker tørker saktere enn vannfilmen på flaten (`holds_drying_factor`).

## Energibalanse for bergflaten

`C · dT_berg/dt = (1−albedo)·SW_vegg + ε·(LW_inn − σ·T_berg⁴) − h_c·(T_berg − T_luft) − k/d·(T_berg − T_dyp) − L·E`

- `SW_vegg`: solstråling på en vertikal flate mot 300°, beregnet med pvlib (Erbs-dekomponering og
  isotropisk himmel), med horisontmaske for direkte sol.
- `LW_inn`: halvparten himmel (Brutsaert + skykorreksjon hvis vi ikke har målt langbølget stråling),
  halvparten terreng på lufttemperatur.
- `T_dyp`: glidende snitt av lufttemperaturen over ca. 5 døgn (fjellets termiske treghet).

## Vannlagre og status

| Lager | Kapasitet | Fylles av | Tømmes av |
|---|---|---|---|
| Vannfilm | 0.1 mm (vertikal flate holder ~0.08 mm) | regn på veggen, kondens | fordampning, avrenning |
| Tak/sprekker | 0.6 mm | overløp fra filmen, siging | sakte fordampning |
| Sigereservoar | – | nedbør × fangstfaktor | tømmes over ca. 120 t |

Status: `vått` hvis film + tak ≥ 0.05 mm, `fuktig` hvis ≥ 0.01 mm, ellers `tørt`.

**Alle parametre er startverdier fra litteratur og skjønn** (se `config/ekstraveggen.yaml` og
`docs/RESEARCH.md`). De må kalibreres mot ekte observasjoner.

## Sammenligningsgrunnlag

`scripts/train.py` rapporterer alltid to enkle bladfukt-regler som fysikkmodellen må slå:
RH ≥ 90 % (eller regn) og duggpunktsdifferanse < 2 °C (eller regn).

## Hvorfor fysikk først, og ikke ML direkte?

- Vi har ingen pålitelige etiketter. Syntetiske etiketter laget med en nedbørsregel gjør at en
  ML-modell bare lærer regelen tilbake (en modell "uten fysikk" treffer slike etiketter nesten
  perfekt fordi de er laget av de samme kolonnene).
- Fysikkmodellen gir fornuftige svar fra dag én og kan forklares ("8 mm regn mot veggen i natt,
  ingen sol før kl 16").
- Når vi får observasjoner, brukes de til å (1) kalibrere parametrene og (2) trene en ML-modell som
  får fysikkmodellens tilstand som input (hybridmodell), som trenger langt færre etiketter.

## Skjeve data: folk er mest på feltet når det er tørt

Tilbakemeldingene blir skjeve. Folk drar når de tror det er tørt (ofte fordi varselet sier det),
snur når det er vått, og rapporterer det som overrasker dem. Det håndterer vi slik:

**1. Rettferdig evaluering** (`modeling/scripts/evaluate.py`). Total treffprosent lyver: i lange
tørkeperioder treffer alle modeller. Vi deler opp etter situasjon og måler treff på vått og tørt hver
for seg:

| Situasjon | Hva den sier |
|---|---|
| `under_regn` | det regner nå: lett |
| `etter_regn` | 0–48 t etter regn: **her avgjøres det om modellen kan tørking** |
| `torkeperiode` | mer enn 48 t etter regn: lett, sier lite |

Med observasjoner fra Supabase vises også treff etter ledetid (hvor godt varselet var 6, 12, 24 t før).

**2. Kalibrering som tåler skjevheten** (`modeling/scripts/calibrate.py`). Hver observasjon er et
vitnesbyrd om hvor mye vann det burde vært på veggen akkurat da ("tørt 8 t etter 5 mm regn" setter en
grense for tørketiden). Vi tilpasser tre parametre (slagregnkoeffisient, vann i tak/sprekker og hvor
fort de tørker) med en prior mot litteraturverdiene. Observasjoner i tørkeperioder påvirker nesten
ikke resultatet, så det er ikke et problem at det er mange av dem. `wind_exposure` kalibreres ikke
fordi den ikke kan skilles fra slagregnkoeffisienten. Valgfritt (`--vekter`): vekt observasjonene etter
hvor sannsynlig det var å bli observert (helg, dagtid, nylig regn).

**3. Simulering** (`modeling/scripts/simulate_bias.py`, `simulate_sweep.py`). En "sann" vegg som
tørker saktere enn startverdiene, og brukere som drar på dagtid, mest i helger og mest når vårt varsel
sier tørt, og som sjeldnere rapporterer når det er vått. Resultat (balansert treff etter regn, testet på
jevnt fordelte observasjoner neste sesong, 3 frø):

| Observasjoner | Startverdier | Kalibrert | Kalibrert + vekter |
|---|---|---|---|
| 150 | 0.79 | 0.84 (0.78–0.92) | 0.85 (0.81–0.87) |
| 400 | 0.78 | 0.93 (0.91–0.95) | 0.91 (0.87–0.95) |

Kalibrering hjelper tydelig fra noen hundre observasjoner, selv med skjeve data. Vektingen gir lite og
er derfor av som standard. Forbehold: simuleringen bruker samme modellstruktur som "sannheten", så den
viser et beste tilfelle. Med 150 observasjoner kan parametrene veksle mot hverandre (mer slagregn ↔ mer
vann i sprekker) selv om varselet blir bedre.

**4. Det som virkelig fjerner skjevheten** er data som ikke avhenger av hvem som drar: et tidsforløpskamera
eller en billig fuktsensor på én vegg ville gitt en observasjon hver time. Et par måneder på Ekstraveggen
er verdt mer enn et år med brukerrapporter.

## Kontroll mot målestasjoner (Frost)

Været i Bergen er svært lokalt. I MET Nordic-dataene (1 km) korrelerer timesnedbøren på Ekstraveggen og
Sandviken bare 0.86, og i 22 % av regntimene regner det bare det ene stedet. Kjører vi Ekstraveggen-modellen
på byvær i stedet for sitt eget, blir svaret et annet i 5 % av timene (mest «tørt» der det egentlig er vått).

Derfor bruker vi målestasjoner til å **kontrollere** varselet, ikke til å erstatte feltets vær:

- `frost_bruk: kontroll` (standard): timesjobben lagrer varselet for **stasjonens egne koordinater** og
  stasjonens målinger (`stasjon_varsel`, `stasjon_maling`). Da måler vi varselets feil, ikke forskjellen
  mellom to steder. Modellen kjører fortsatt på MET Nordic for feltet, som allerede bruker stasjonene,
  radar og Netatmo.
- `frost_bruk: erstatt`: målingene erstatter historikken modellen kjører på. Bare for stasjoner 1–2 km
  fra feltet.

`modeling/scripts/verify_forecast.py` viser treff på regntimer, temperatur, fuktighet og vind per ledetid
(fra arkivet), eller med `--historikk START SLUTT` for flere år: modellen ved stasjonen mot målingene, og
hvert felts vær mot samme stasjon. Krever `FROST_CLIENT_ID` i `.env` (lokalt) og som secret i GitHub.

### Første resultat: MET Nordic mot Bergen–Florida (SN50540), 2025-01-01 til 2026-10-26

| Værserie | Temp. feil (°C) | RF feil / skjevhet (%-poeng) | Regntimer truffet | Varslet regn som uteble | Nedbør, andel av målt |
|---|---|---|---|---|---|
| MET Nordic ved stasjonen | 0.19 | 8.4 / +2.2 | 66 % | 32 % | 0.89 |
| ved Ekstraveggen (5.5 km) | 0.65 | 7.6 / +3.2 | 63 % | 31 % | 0.82 |
| ved Helleneset (6.4 km) | 0.78 | 7.7 / +2.0 | 62 % | 30 % | 0.80 |
| ved Sandviken (3.8 km) | 0.76 | 8.2 / +2.2 | 65 % | 32 % | 0.88 |

Hva vi lærer:
- **Regn time for time er usikkert selv ved stasjonen** (66 % truffet). Usikkerheten i modellen er større enn
  forskjellen mellom feltpunktene, så for regn hjelper det lite å velge et annet gridpunkt. Rutenettet glatter
  likevel ut lokale byger, så de ekte lokale forskjellene kan være større enn dette viser.
- **Temperaturen er lokal, men forskjellene er små** (under 1 °C).
- **Modellen er for fuktig** (+2–3 %-poeng relativ fuktighet). Det betyr at den trolig tørker berget litt for sakte.
  Kalibreringen tar delvis opp dette.
- **Over lengre vinduer er regnet godt fanget**, og det er det tørkingen avhenger av:

  | | Time | 6 timer | Døgn |
  |---|---|---|---|
  | Regn truffet, ved stasjonen | 66 % | 80 % | 92 % |
  | Regn truffet, ved feltene | 62–65 % | 76–79 % | 91–92 % |
  | Varslet regn som uteble | 30–32 % | 16–18 % | 6–9 % |
  | Korrelasjon døgnsum | | | 0.89–0.90 |

  Usikkerheten ligger mest i *når* regnet kommer (noen timer), ikke *om* det kommer. Overgangene mellom vått
  og tørt i varselet bør derfor leses som ± et par timer.
- Om stasjonsmålinger er bedre enn feltets eget gridpunkt kan bare avgjøres mot tilbakemeldinger fra feltet:
  kalibrer med begge og se hvilken som forutsier rapportene best.

## Sesong og år: MET Nordic mot Florida 2023-2026

`python scripts/verify_forecast.py --historikk` sammenligner hele perioden fra 2023-01-01 til i går (33 456 timer),
også per sesong, år, måned og tid på døgnet. Hentingene lagres i `data/raw`, så neste kjøring går raskt.

### Regn

| | Time, truffet | Time, falsk | 6 t, truffet | Døgn, truffet | Døgn, falsk | Korr. døgnsum | mm-forhold |
|---|---|---|---|---|---|---|---|
| Vinter | 72 % | 28 % | 87 % | 97 % | 5 % | 0.93 | 0.95 |
| Vår | 69 % | 34 % | 80 % | 91 % | 9 % | 0.91 | 1.02 |
| Sommer | 61 % | 34 % | 78 % | 87 % | 8 % | 0.81 | 0.79 |
| Høst | 65 % | 31 % | 80 % | 90 % | 8 % | 0.90 | 0.87 |

Vinterregnet (fronter fra havet) treffes best. Sommeren er svakest: byger er små og lokale, og MET Nordic får bare
79 % av mengden. Tallene er stabile fra år til år (døgn truffet 87-93 %), så dette er ikke ett uvanlig år.
Sommervarselet bør derfor leses med litt større slingringsmonn.

Temperaturen treffer svært godt hele året (MAE 0.17 °C ved stasjonen). Vinden er også uten skjevhet.

### Luftfuktighet

Varselet ser ut til å være for fuktig når det er fuktig (+6 ved varslet ≥ 95 %) og for tørt når det er tørt. Men
sorterer man etter det som ble *målt*, snur fortegnet (−4 ved målt ≥ 95 %). Det meste av det mønsteret er altså
tilfeldig feil (MAE ~8), ikke skjevhet, og skal ikke rettes. Spredningen i varsel og måling er nesten lik (std 16.3 og 16.0).

Det som er systematisk, og som går igjen hvert år:

- **Døgnsvingning.** Varselet er 3-5 prosentpoeng for fuktig på ettermiddag og kveld (topp rundt kl 16-18 i alle
  måneder) og litt for tørt før soloppgang. Det er akkurat når folk klatrer og veggen tørker.
- **Sesong.** For fuktig februar-oktober (+2 til +4, mest vår og forsommer), litt for tørt desember-januar.
  Enkeltmåneder varierer mye fra år til år (februar: +7 i 2023, −2 i 2025), så månedsverdiene glattes.
- 2026 er fuktigere enn de andre årene (+3.2 mot +1.1 til +1.6). Kan være en endring i MET Nordic eller på
  stasjonen. Arkivkontrollen viser om det fortsetter.

Florida måler nesten aldri 99-100 % (0.01 % av timene, varselet 3.9 %). Det er typisk for en bystasjon og for
fuktighetsfølere nær metning, og betyr ikke at feltene aldri har mettet luft. Korreksjonen prøver derfor ikke å
fjerne de fuktigste timene, bare å flytte nivået.

### Korreksjonen i modellen

Modellen legger til en korreksjon på fuktigheten før energibalansen: en verdi per måned (glatt langs året) pluss
en døgnsvingning per måned, tilpasset over **alle** timer. Den gjelder per Frost-stasjon og ligger i
`modeling/config/stasjoner/rh_korreksjon.yaml` (skrives av `--skriv-rh`). En verdi i feltets egen konfig vinner,
`rh_korreksjon_styrke` skalerer den, og timer der Frost-målinger har erstattet varselet korrigeres ikke.

Korreksjon den 15. i måneden (prosentpoeng):

| | kl 00 | kl 06 | kl 12 | kl 15 | kl 18 | kl 21 |
|---|---|---|---|---|---|---|
| Januar | +1.5 | +2.5 | +0.2 | −0.7 | −0.8 | +0.2 |
| April | −3.1 | +0.8 | −3.1 | −5.8 | −7.0 | −5.8 |
| Juli | −1.8 | 0.0 | −3.9 | −5.6 | −5.7 | −4.1 |
| Oktober | −0.2 | +2.2 | −2.2 | −4.3 | −4.5 | −2.9 |

Etter korreksjon er skjevheten under 0.5 i alle sesonger og døgnperioder, og MAE på ettermiddagen går fra 8.0 til 6.7.

Virkning på ett år med vær (okt 2024 - sep 2025), andel timer vått på dagtid (09-21):

| | Apr-sep, før → etter | Okt-mar, før → etter | Kondens (mm/år) |
|---|---|---|---|
| Ekstraveggen | 32.5 → 30.0 % | 68.1 → 67.4 % | 7.4 → 7.4 |
| Sandviken | 31.4 → 29.4 % | 60.0 → 59.8 % | 7.0 → 6.9 |
| Helleneset | 35.5 → 34.0 % | 67.3 → 67.2 % | 4.7 → 5.0 |

Modellen tørker raskere på sommerettermiddager, mens dugg om natta og vinterstid er som før. En fast korreksjon
på −2 hele døgnet (første forsøk) fjernet en tredel av kondensen, og var feil.

Florida er en bystasjon, og feltene ligger i skog og ved sjøen. Det er mulig feltene er fuktigere enn Florida på
ettermiddagen. `rh_korreksjon_styrke` kan kalibreres mot tilbakemeldinger når det finnes nok av dem: formen kommer
fra stasjonen, styrken fra feltet.

Kontrollen på arkivet (`verify_forecast.py` uten argumenter) viser også månedsvis når arkivet spenner over mer enn
to måneder, så sesongsjekken fortsetter av seg selv etter hvert som timesjobben samler data.
