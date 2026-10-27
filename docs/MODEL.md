# Modellen: hvordan vi regner ut om veggen er våt

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
  ML-modell bare lærer regelen tilbake (testet i `scripts/train.py`: modellen "uten fysikk" treffer
  Kristians syntetiske etiketter nesten perfekt fordi de er laget av de samme kolonnene).
- Fysikkmodellen gir fornuftige svar fra dag én og kan forklares ("8 mm regn mot veggen i natt,
  ingen sol før kl 16").
- Når vi får observasjoner, brukes de til å (1) kalibrere parametrene og (2) trene en ML-modell som
  får fysikkmodellens tilstand som input (hybridmodell), som trenger langt færre etiketter.
