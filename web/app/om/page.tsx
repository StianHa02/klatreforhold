import type { Metadata } from 'next'
import { FeltForklaring, MaanedLinjer, MaanedStolper, Simulering, Spenn } from '@/components/om/Diagrammer'
import VeggSnitt, { FORKLARING } from '@/components/om/VeggSnitt'
import { dag, klokke } from '@/lib/api'
import { hentStatistikk } from '@/lib/kilde'
import statistikk from '@/data/modellstatistikk.json'

export const dynamic = 'force-dynamic'
export const metadata: Metadata = {
  title: 'Om modellen · Klatreforhold',
  description: 'Hvordan vi regner ut om fjellet er tørt, og hva vi vil med prosjektet.',
}

type FeltData = (typeof statistikk.felt)[keyof typeof statistikk.felt]
const felt = Object.entries(statistikk.felt as Record<string, FeltData>).map(([slug, d]) => ({ slug, ...d }))
const prosent = (v: number) => `${Math.round(v * 100)} %`

function Seksjon({ id, tittel, children }: { id: string; tittel: string; children: React.ReactNode }) {
  return (
    <section id={id} aria-labelledby={`${id}-tittel`} className="flex flex-col gap-md">
      <h2 id={`${id}-tittel`} className="font-mabry text-xl leading-tight">{tittel}</h2>
      {children}
    </section>
  )
}

function Kort({ tittel, tekst, children }: { tittel: string; tekst?: string; children: React.ReactNode }) {
  return (
    <figure className="flex flex-col gap-sm kort p-md">
      <figcaption className="flex flex-col gap-xs">
        <span className="h3">{tittel}</span>
        {tekst && <span className="byline max-w-[65ch]">{tekst}</span>}
      </figcaption>
      {children}
    </figure>
  )
}

const STEG = [
  { tittel: 'Vær for akkurat dette feltet', tekst: 'Vi henter temperatur, luftfuktighet, nedbør, vind, skydekke og solinnstråling for feltets koordinater. MET Nordic (1 × 1 km) brukes nærmest i tid, med Open-Meteo som reserve og ECMWF for dagene lenger fram. Fersk nedbørradar dekker de neste to timene når data er tilgjengelige.' },
  { tittel: 'Regn som treffer veggen', tekst: 'Ut fra vindretning, vindstyrke og hvilken vei veggen vender, regner vi ut hvor mye av regnet som faktisk treffer fjellet. På sva treffer mer av det vanlige regnet direkte.' },
  { tittel: 'Temperaturen i berget', tekst: 'Et energiregnskap for overflaten: sol på veggen (med terrenget rundt fra Kartverket), varmestråling, vind og varme fra berget innenfor. Det gir bergtemperaturen time for time.' },
  { tittel: 'Vannet på veggen', tekst: 'Vi holder regnskap med vannfilmen, vannet i tak og sprekker og et sakte sigereservoar. Kondens legger til vann, fordampning tar det bort.' },
  { tittel: 'Tørt, fuktig eller vått', tekst: 'Tørt gjelder den representative hovedveggen; enkeltruter kan avvike. Vi følger vann, is og snø hver for seg. Frysing frigir varme, og smelting bruker varme før smeltevannet kan tørke. Is og snø på veggen vises som vått.' },
]

const VIDERE = [
  { status: 'ferdig', tittel: 'Fysisk modell for ni felt', tekst: 'Hvert felt har eget vær, egen retning, bratthet og horisont. Varselet oppdateres hver time.' },
  { status: 'pågår', tittel: 'Samle tilbakemeldinger', tekst: 'Hver gang noen sier hvordan fjellet faktisk var, sammenligner vi med varselet for samme time. Det er dette alt videre bygger på.' },
  { status: 'neste', tittel: 'Kalibrere modellen per felt', tekst: 'Vi tilpasser først én parameter for tørkeeffektivitet. Tilpasningen må bli bedre på andre regnepisoder og ikke gi flere feilvarsler om tørt før den tas i bruk.' },
  { status: 'senere', tittel: 'Maskinlæring oppå fysikken', tekst: 'Modeller i scikit-learn og PyTorch som får fysikkmodellens anslag som utgangspunkt og lærer det fysikken ikke fanger, som trær, sigestriper og lav. De tas bare i bruk hvis de slår fysikken på nye data.' },
  { status: 'senere', tittel: 'En fasit som ikke avhenger av hvem som drar', tekst: 'Et kamera eller en enkel fuktsensor på én vegg ville gitt en observasjon hver time, også når ingen klatrer.' },
  { status: 'senere', tittel: 'Inn i nettføreren', tekst: 'Varselet vist på feltsidene i BKKs nettfører, og et spørsmål om forholdene når du logger en bestigning.' },
]
const STATUSFARGE: Record<string, string> = {
  ferdig: 'bg-forhold-tort text-white',
  pågår: 'bg-forhold-fuktig text-text-default',
  neste: 'bg-accent-surface-default text-accent-text-default',
  senere: 'bg-surface-tinted text-text-tinted',
}

export default async function OmModellen() {
  const live = await hentStatistikk()
  const navn = Object.fromEntries(felt.map((f) => [f.slug, f.navn]))
  const totalt = live?.reduce((n, f) => n + f.observasjoner, 0) ?? 0
  const sim = (statistikk.simulering ?? []) as { n: number; modell: string; snitt: number; min: number; maks: number }[]
  const periode = felt[0]?.periode
  const solMaks = Math.max(2, Math.ceil(Math.max(...felt.flatMap((f) => f.soltimer_per_dogn)) / 2) * 2)

  return (
    <article className="flex flex-col gap-xl">
      <header className="flex flex-col gap-md">
        <h1 className="font-mabry text-[32px] leading-tight">Hvordan vi regner ut om fjellet er tørt</h1>
        <p className="max-w-[62ch] text-lg leading-relaxed text-text-tinted">
          Det sitter ingen sensor på veggene. Varselet er et regnestykke: værdata fra MET, terrenget fra Kartverket og
          fysikken for hvordan vann treffer, blir liggende på og forsvinner fra berg. Etter hvert skal tilbakemeldingene
          deres gjøre det mer treffsikkert.
        </p>
      </header>

      <Seksjon id="vann" tittel="Hva som gjør fjellet vått, og hva som tørker det">
        <div className="kort p-md">
          <VeggSnitt />
        </div>
        <ol className="grid gap-md sm:grid-cols-2">
          {FORKLARING.map((f) => (
            <li key={f.n} className="flex gap-sm">
              <span aria-hidden className="mt-[2px] flex h-[22px] w-[22px] shrink-0 items-center justify-center rounded-full border border-text-default text-xs font-semibold">
                {f.n}
              </span>
              <span className="flex flex-col gap-xs">
                <span className="h3">{f.tittel}</span>
                <span className="text-sm leading-relaxed text-text-tinted">{f.tekst}</span>
              </span>
            </li>
          ))}
        </ol>
      </Seksjon>

      <Seksjon id="regnestykket" tittel="Regnestykket, hver time">
        <ol className="flex flex-col gap-md border-l-2 border-border-tinted pl-md">
          {STEG.map((s, i) => (
            <li key={s.tittel} className="flex flex-col gap-xs">
              <span className="h3">
                <span className="mr-sm tabular-nums text-text-subtle">{i + 1}.</span>
                {s.tittel}
              </span>
              <span className="max-w-[65ch] text-sm leading-relaxed text-text-tinted">{s.tekst}</span>
            </li>
          ))}
        </ol>
        <p className="max-w-[65ch] text-sm leading-relaxed text-text-subtle">
          Modellen bygger på det samme prinsippet som brukes for å varsle glatte veier og bladfuktighet i landbruket.
          Parametrene er foreløpige anslag. Retning, bratthet og terreng er hentet fra kart og nettfører;
          vindeksponering er vurdert lokalt. Overheng skjermer mot regn, men kan fortsatt få siging og kondens.
        </p>
      </Seksjon>

      <Seksjon id="feltene" tittel="Hva modellen sier om feltene">
        <p className="max-w-[65ch] text-text-tinted">
          Vi har kjørt modellen over all værhistorikk fra {periode ? `${periode[0].slice(0, 4)} til ${periode[1].slice(0, 4)}` : 'de siste årene'} for hvert felt.
          Tallene er modellens anslag, ikke målinger.
        </p>
        <FeltForklaring felt={felt} />
        <Kort tittel="Andel tørre timer på dagtid (kl 08–20)"
              tekst="Modellberegning med feltets eget vær. Sva fanger mer direkte nedbør, mens vind, skygge og vann i sprekker påvirker hvor lenge det blir vått. En våtere vegg kan ha korte tørkeepisoder når været først tillater det.">
          <MaanedLinjer serier={felt.map((f) => ({ slug: f.slug, navn: f.navn, verdier: f.tort_dagtid_per_maned }))}
                        maks={1} steg={0.25} enhet={prosent} label="Andel tørre timer på dagtid per måned for hvert felt" />
        </Kort>
        <Kort tittel="Timer med sol på veggen, per døgn"
              tekst="Direkte sol krever at solen står foran bergflaten og over terrenghorisonten, og at skyene slipper gjennom nok lys. Ekstraveggen vender mot nordvest, Helleneset mot vest og Sandvikens hovedvegg mot sør.">
          <MaanedStolper serier={felt.map((f) => ({ slug: f.slug, navn: f.navn, verdier: f.soltimer_per_dogn }))}
                         maks={solMaks} steg={2} enhet={(v) => `${v} t`} label="Timer med direkte sol på veggen per døgn, per måned" />
        </Kort>
        <Kort tittel="Tørketid i episodene som fullføres"
              tekst="Modellanslag etter minst 2 mm nedbør på 12 timer, fulgt av tre timer opphold. Prikken er medianen og streken den midterste halvparten, bare for episoder som tørker innen 72 timer før nytt regn. Snø/is vises separat i antallene under.">
          <Spenn
            maks={72}
            label="Tørketid etter regn for hvert felt, sommer og vinter"
            rader={[
              { gruppe: 'Sommer (april–september)', spenn: felt.filter((f) => f.torketid_timer.sommer).map((f) => ({ slug: f.slug, navn: f.navn, ...f.torketid_timer.sommer! })) },
              { gruppe: 'Vinter (oktober–mars)', spenn: felt.filter((f) => f.torketid_timer.vinter).map((f) => ({ slug: f.slug, navn: f.navn, ...f.torketid_timer.vinter! })) },
            ]}
          />
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm tabular-nums">
              <caption className="sr-only">Alle kvalifiserende regnepisoder, også de som ikke tørker</caption>
              <thead><tr>
                <th scope="col" className="p-sm">Felt og sesong</th>
                <th scope="col" className="p-sm">Tørket</th>
                <th scope="col" className="p-sm">Nytt regn</th>
                <th scope="col" className="p-sm">Vått etter 72 t</th>
                <th scope="col" className="p-sm">Ufullstendig</th>
                <th scope="col" className="p-sm">Snø/is</th>
                <th scope="col" className="p-sm">Tørt innen 6 / 12 / 24 t</th>
              </tr></thead>
              <tbody>{felt.flatMap((f) => (['sommer', 'vinter'] as const).map((sesong) => {
                const s = f.torkeepisoder[sesong]
                return <tr key={`${f.slug}-${sesong}`} className="border-t border-border-subtle">
                  <th scope="row" className="p-sm font-normal">{f.navn}, {sesong}</th>
                  <td className="p-sm">{s.utfall.tort}</td><td className="p-sm">{s.utfall.nytt_regn}</td>
                  <td className="p-sm">{s.utfall.fortsatt_vatt}</td><td className="p-sm">{s.utfall.ufullstendig}</td>
                  <td className="p-sm">{s.vinterpaavirket}</td>
                  <td className="p-sm">{(['6', '12', '24'] as const).map((h) => s.innen_timer[h].andel === null ? '–' : prosent(s.innen_timer[h].andel)).join(' / ')}</td>
                </tr>
              }))}</tbody>
            </table>
          </div>
          <p className="byline">Andelene gjelder episoder der utfallet er kjent ved hvert tidspunkt. Nytt regn teller som avbrutt tørking; ufullstendig historikk inngår bare så lenge den kan vurderes.</p>
        </Kort>
        <Kort tittel="Feltene sammenlignet med samme vær"
              tekst="Et kontrollforsøk med identisk vær fra Ekstraveggen. Det viser betydningen av veggretning, bratthet, skygge og de foreløpige lokale parametrene. Dette er ikke feltenes faktiske værhistorikk.">
          <MaanedLinjer serier={Object.entries(statistikk.felles_vaer.felt).map(([slug, f]) => ({ slug, navn: f.navn, verdier: f.tort_dagtid_per_maned }))}
                        maks={1} steg={0.25} enhet={prosent} label="Modellberegnede tørre dagtimer ved identisk vær" />
        </Kort>
      </Seksjon>

      <Seksjon id="data" tittel="Det vi har samlet så langt">
        {live && live.length > 0 ? (
          <>
            <p className="max-w-[65ch] text-text-tinted">
              {totalt === 0
                ? 'Ingen tilbakemeldinger ennå. Den første kommer fra deg.'
                : `${totalt} ${totalt === 1 ? 'tilbakemelding' : 'tilbakemeldinger'} så langt. Vi trenger noen hundre per felt før vi kan kalibrere.`}
            </p>
            <div className="overflow-x-auto kort">
              <table className="w-full text-left text-sm tabular-nums">
                <thead className="text-text-subtle">
                  <tr className="border-b border-border-subtle">
                    <th scope="col" className="p-sm font-normal">Felt</th>
                    <th scope="col" className="p-sm font-normal">Tilbakemeldinger</th>
                    <th scope="col" className="p-sm font-normal">Tørt / fuktig / vått</th>
                    <th scope="col" className="p-sm font-normal">Varselet stemte</th>
                    <th scope="col" className="p-sm font-normal">Varsler i arkivet</th>
                  </tr>
                </thead>
                <tbody>
                  {live.map((f) => (
                    <tr key={f.felt} className="border-b border-border-subtle last:border-0">
                      <th scope="row" className="p-sm font-medium">
                        <a className="lenke" href={`/felt/${f.felt}`}>{navn[f.felt] ?? f.felt}</a>
                      </th>
                      <td className="p-sm">{f.observasjoner}</td>
                      <td className="p-sm">{f.tort} / {f.fuktig} / {f.vatt + (f.is ?? 0)}</td>
                      <td className="p-sm">{f.andel_riktig === null ? '–' : `${Math.round(f.andel_riktig * 100)} % av ${f.vurdert}`}</td>
                      <td className="p-sm">{f.kjoringer} siden {dag(f.forste_varsel)} kl {klokke(f.forste_varsel)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <p className="max-w-[65ch] text-sm leading-relaxed text-text-subtle">
              Tilbakemeldinger fra utviklere er holdt utenfor. «Varselet stemte» skiller bare mellom tørt og ikke tørt,
              og sammenligner med varselet slik det så ut før timen.
            </p>
          </>
        ) : (
          <p className="max-w-[65ch] text-text-subtle">Tallene hentes fra databasen og er ikke tilgjengelige akkurat nå.</p>
        )}
      </Seksjon>

      <Seksjon id="skjevhet" tittel="Folk er mest på feltet når det er tørt">
        <p className="max-w-[65ch] text-text-tinted">
          Tilbakemeldingene blir skjeve: folk drar når de tror det er tørt, og snur når det er vått. Det gjør at en total
          treffprosent ser bedre ut enn den er. Vi måler derfor treff for timene rett etter regn for seg, fordi det er der
          det avgjøres om modellen kan tørking.
        </p>
        <p className="max-w-[65ch] text-text-tinted">
          Derfor teller vi uavhengige regnepisoder og tester på andre episoder enn dem vi tilpasser modellen til.
          Meldinger fra samme regnvær gir nyttig informasjon, men teller ikke som uavhengige forsøk.
        </p>
        {sim.length > 0 && (
          <Kort tittel="Treff i timene etter regn, simulert"
                tekst="Lys søyle: startverdiene. Mørk søyle: kalibrert på tilbakemeldingene. Søylen er snittet av tre simuleringer, den røde streken viser beste og dårligste. Testet på en sesong modellen ikke har sett.">
            <Simulering rader={sim} label="Treff etter regn med startverdier og kalibrert modell, ved 150 og 400 tilbakemeldinger" />
          </Kort>
        )}
        <p className="max-w-[65ch] text-sm leading-relaxed text-text-subtle">
          Også «det var tørt» er nyttig, særlig rett etter regn: det forteller hvor fort veggen tørker.
          Vi trenger meldinger når varselet stemmer og når det bommer, før vi kan måle hvor godt modellen virker.
        </p>
      </Seksjon>

      <Seksjon id="videre" tittel="Veien videre">
        <ol className="flex flex-col gap-sm">
          {VIDERE.map((v) => (
            <li key={v.tittel} className="flex flex-col gap-xs kort p-md sm:flex-row sm:gap-md">
              <span className={`h-fit w-fit shrink-0 rounded-full px-sm py-[2px] text-xs font-medium ${STATUSFARGE[v.status]} sm:w-[5.5rem] sm:text-center`}>
                {v.status === 'pågår' ? 'Pågår' : v.status[0].toUpperCase() + v.status.slice(1)}
              </span>
              <span className="flex flex-col gap-xs">
                <span className="h3">{v.tittel}</span>
                <span className="max-w-[62ch] text-sm leading-relaxed text-text-tinted">{v.tekst}</span>
              </span>
            </li>
          ))}
        </ol>
      </Seksjon>

      <Seksjon id="forbehold" tittel="Forbehold">
        <ul className="flex max-w-[65ch] list-disc flex-col gap-xs pl-lg text-sm leading-relaxed text-text-tinted">
          <li>Varselet er et anslag. Sjekk alltid fjellet selv før du klatrer, særlig etter mye regn og om vinteren.</li>
          <li>Modellen ser ikke enkeltruter, trær rett foran veggen, sigestriper eller lav. Noen ruter tørker raskere enn andre.</li>
          <li>Feltenes koordinater er kartpunkter, ikke nøyaktig foten av veggen. Det påvirker når sola beregnes å treffe.</li>
        </ul>
        <p className="byline">
          Værdata: MET Norway direkte og via Open-Meteo (CC BY 4.0). Historikkgrafene bruker arkiverte modellvarsler,
          ikke målt bergfuktighet. Terreng: Kartverket DOM/DTM (CC BY 4.0).
          Modell {statistikk.modellversjon}, beregnet {statistikk.generert}; de første {statistikk.oppvarming_dogn} døgnene er utelatt som oppvarming.
        </p>
      </Seksjon>
    </article>
  )
}
