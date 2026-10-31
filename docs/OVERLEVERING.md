# Overlevering: klatreforhold

## Kodegrunnlaget

[README](../README.md) er inngangen for oppsett, [MODELL_V2](MODELL_V2.md) beskriver modellen og
[DEPLOY](DEPLOY.md) beskriver drift.

- Ni felt er definert i `modeling/config/`. V2-geometri og bergart er lagt inn; helninger fra
  bratthetskategorier er fortsatt anslag. Se felttabellen i modellguiden.
- Timesjobben lager 120 timer fremover og sju døgn bakover; arkivet beholder ledetider til 48 timer.
  Direkte MET Nordic foretrekkes over Open-Meteo, med fersk Nowcast-nedbør. Open-Meteo gir også innkjøring.
- Databaseskjemaet har seks migrasjoner, inkludert `modelltilstand`, v2-metadata og støtte for isobservasjoner.
  Den siste, `vaer_og_rydding`, legger til værinput til trening (`vaer`) og ukentlig arkivrydding.
  Se [deployguiden](DEPLOY.md).
- MEPS gir valgfri, ukalibrert `p_tort` og toppnivå `ensemble` i sistevarselet. Verdien arkiveres ikke
  i `varsel` og vises ikke som prosent på nettsiden.
- Nettsiden viser tørt/fuktig/vått og omgjør modellens is/snø til vått. Skjemaet har tre valg.
- Kalibrering tilpasser én fordampningsparameter, med minst 50 observasjoner og ti regnepisoder.
  ML-kandidater fra `train.py --save` må valideres separat før de kan aktiveres.
- FastAPI og Docker støtter lokal utvikling; produksjonen bruker Actions → Supabase → Vercel.
  `KLATREFORHOLD_DATAKILDE=api` velger lokalt API også når Supabase-nøkler finnes.

## Gjenstående arbeid

1. Kontroller siste ordinære timesjobb, datakilder og Frost-innsamling i produksjon.
2. Samle faktiske observasjoner fra uavhengige regnepisoder og valider tørketid, geometri og vinterfysikk.
3. Kalibrer ved tilstrekkelig grunnlag; hold dev/test-data og syntetiske etiketter utenfor aktivering.
4. Vurder arkivering og kalibrering av MEPS-usikkerhet før prosentvis visning. Dette krever eget arbeid.
5. Kjør `vaer_og_rydding`-migrasjonen i produksjon og følg med på databasestørrelsen.
   Lagringstiden (120 dager, ledetid 0/3/6/12/24/48) står i [deployguiden](DEPLOY.md).
6. Vurder resterende forskningsforslag fra [RESEARCH_2](RESEARCH_2.md): delvis pooling, ordinal modell,
   pålitelighetsdiagrammer og faste feltobservasjoner.

Integrasjon med nettføreren er fortsatt separat, fremtidig arbeid. Ikke endre dens database eller repo.

## Fallgruver

- **GitHub starter ikke alltid planlagte kjøringer.** Sjekk Actions-fanen. Alternativet er
  `supabase/valgfritt/cron_starter_github_jobb.sql` (Supabase Cron kaller `workflow_dispatch` med et
  GitHub-token i Vault som `github_dispatch_token`).
- **PostgREST gir maks 1000 rader per kall.** `limit=5000` hjelper ikke. Spør etter færre rader (f.eks.
  `ledetid_timer=in.(22,23,24,25,26)`) eller bla med `Range`.
- **Tilbakemeldinger før og etter 2026-10-29 må vurderes hver for seg.** Fra da viser skjemaet modellens
  status på timeknappene, noe som kan gi forankring. Før det var varselet skjult.
- **Gamle observasjoner mangler `predikert_status`** fordi de er eldre enn varselarkivet. `predikertFra`
  faller tilbake til `varsel_siste`.
