# Overlevering: klatreforhold

## Kodegrunnlaget

[README](../README.md) er inngangen for oppsett, [MODELL_V2](MODELL_V2.md) beskriver modellen og
[DEPLOY](DEPLOY.md) beskriver drift.

- Ni felt er definert i `modeling/config/`. V2-geometri og bergart er lagt inn; helninger fra
  bratthetskategorier er fortsatt anslag. Se felttabellen i modellguiden.
- Timesjobben lager 120 timer fremover og sju døgn bakover; arkivet beholder ledetider til 48 timer.
  Direkte MET Nordic foretrekkes over Open-Meteo, med fersk Nowcast-nedbør. Open-Meteo gir også innkjøring.
- Databaseskjemaet har åtte migrasjoner, inkludert `modelltilstand`, v2-metadata og støtte for isobservasjoner.
  `vaer_og_rydding` legger til værinput til trening (`vaer`) og ukentlig arkivrydding. Den siste,
  `bones_maling`, lagrer målinger fra Bønes værstasjon. `parquet_arkiv` gjør at ryddingen bare sletter
  døgn som er eksportert til Parquet ([Parquet-arkivet](ARKIV.md)), og ryddingen tynner etter 30 dager.
  Kjørt i produksjon 6.11.2026; Pi-en eksporterer hver natt også i testmodus.
  Se [deployguiden](DEPLOY.md).
- MEPS gir valgfri, ukalibrert `p_tort` og toppnivå `ensemble` i sistevarselet. Verdien arkiveres ikke
  i `varsel` og vises ikke som prosent på nettsiden.
- Nettsiden viser tørt/fuktig/vått og omgjør modellens is/snø til vått. Skjemaet har tre valg.
- Kalibrering tilpasser én fordampningsparameter, med minst 50 observasjoner og ti regnepisoder.
  ML-kandidater fra `train.py --save` må valideres separat før de kan aktiveres.
- FastAPI og Docker støtter lokal utvikling; produksjonen bruker Raspberry Pi (systemd-timer) → Supabase → Vercel. Actions er reserve via Supabase Cron.
  `KLATREFORHOLD_DATAKILDE=api` velger lokalt API også når Supabase-nøkler finnes.

## Gjenstående arbeid

1. Kontroller siste ordinære timesjobb, datakilder og Frost-innsamling i produksjon.
2. Samle faktiske observasjoner fra uavhengige regnepisoder og valider tørketid, geometri og vinterfysikk.
3. Kalibrer ved tilstrekkelig grunnlag; hold dev/test-data og syntetiske etiketter utenfor aktivering.
4. Vurder arkivering og kalibrering av MEPS-usikkerhet før prosentvis visning. Dette krever eget arbeid.
5. Kjør `vaer_og_rydding`-migrasjonen i produksjon og følg med på databasestørrelsen.
   Lagringstiden (30 dager, deretter ledetid 0/3/6/12/24/48) står i [deployguiden](DEPLOY.md).
6. Kjør `bones_maling`-migrasjonen i produksjon (reserve for Bønes-regnet). `regnmaler_bruk: erstatt` er på for
   Ekstraveggen fra 1.11.2026; følg med på `_bones` i timesjobben og evaluer mot observasjoner til våren,
   se [Bønes værstasjon](BONES_STASJON.md).
7. Vurder resterende forskningsforslag fra [RESEARCH_2](RESEARCH_2.md): delvis pooling, ordinal modell,
   pålitelighetsdiagrammer og faste feltobservasjoner.
8. **Før utvidelse fra 9 til ~135 felt** (nettføreren, 1.11.2026). Erfaringene fra oktober 2026 (hyllelager,
   horisont på Bymuren, sig på Ekstraveggen, Bønes-stasjonen) peker på tre ting som bør på plass først:
   - *Modellparametre per felttype, ikke per felt.* YAML-ene bør bare ha geometri (koordinater, asimut,
     helning, horisont, regnsikkert); parametrene arves fra en profil etter bratthet × regnsikkert × kyst/innland.
     Da justeres fem–seks profiler, ikke 135 filer. Sva (≈35 av feltene) trenger trolig større hyllelager enn de
     0,3 mm som nå er standard, og det samme gjør skyggefulle vegger med overheng: Ekstraveggen var 2.11.2026
     fuktig hele dagen uten regn, også under overhenget, og bruker 0,6 mm / 0,5 i stedet for større sig
     (en jevn film, ikke striper fra sprekker, og et reservoar på toppen når ikke ned over 35 m vegg).
     Kystfeltene i Øygarden/Sotra/Askøy (≈60) trenger trolig høyere `wind_exposure` enn 0,4–0,5.
   - *Én kontrollstasjon per feltklynge.* MET Nordic er verifisert bare mot Florida og Bønes. Nedbøren varierer
     mye mellom Øygarden, Bergen og innlandet; finn Frost-/private stasjoner nær klyngene og kjør samme analyse som
     `evaluer_bones.py`. Sig-nedslagsfeltet over veggen kan trolig estimeres fra DTM i stedet for å settes for hånd.
   - *Nære trær mangler i DOM-horisonten* (beregningen starter 10 m ut). Be om «første sol på veggen»-observasjoner
     i tilbakemeldingsskjemaet; `scripts/plot_horizon.py` viser hva som må rettes.
   Observasjoner blir flaskehalsen; de fleste av 135 felt blir aldri kalibrert hver for seg.

Integrasjon med nettføreren er fortsatt separat, fremtidig arbeid. Ikke endre dens database eller repo.

## Fallgruver

- **GitHub startet ikke alltid planlagte kjøringer.** Derfor kjører timesjobben nå på en Raspberry Pi
  ([`drift/raspberrypi/`](../drift/raspberrypi/README.md)). Supabase Cron (`start-varsel-jobb`) starter
  workflowen bare når varselet er over 90 minutter gammelt. Legg ikke tilbake `schedule`, ellers publiseres hver time to ganger.
- **Ryddingen sletter bare eksporterte døgn.** Stopper den nattlige eksporten på Pi-en, slettes ingenting og
  databasen vokser med ca. 2 MB/døgn. Sjekk `journalctl -u klatreforhold-arkiv` og spørringene i [ARKIV](ARKIV.md).
  Skriv aldri en kvittering i `arkiv_eksport` for hånd.
- **PostgREST gir maks 1000 rader per kall.** `limit=5000` hjelper ikke. Spør etter færre rader (f.eks.
  `ledetid_timer=in.(22,23,24,25,26)`) eller bla med `Range`.
- **Tilbakemeldinger før og etter 2026-10-29 må vurderes hver for seg.** Fra da viser skjemaet modellens
  status på timeknappene, noe som kan gi forankring. Før det var varselet skjult.
- **Gamle observasjoner mangler `predikert_status`** fordi de er eldre enn varselarkivet. `predikertFra`
  faller tilbake til `varsel_siste`.
