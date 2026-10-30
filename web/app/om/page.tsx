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
  { tittel: 'Vær for akkurat dette feltet', tekst: 'Temperatur, luftfuktighet, nedbør, vind, skydekke og solinnstråling hentes for feltets egne koordinater. De nærmeste timene bruker vi MET Nordic med 1 × 1 km oppløsning, med Open-Meteo som reserve og ECMWF for dagene lenger fram. Når radardata er tilgjengelige, dekker de de neste to timene.' },
  { tittel: 'Regn som treffer veggen', tekst: 'En loddrett vegg blir våt når vinden blåser regnet inn mot den. Ut fra vindretning, vindstyrke og hvilken vei veggen vender, regner vi ut hvor mye som faktisk treffer. Sva heller bakover og får i tillegg mye av regnet rett ovenfra.' },
  { tittel: 'Temperaturen i berget', tekst: 'Vi fører et energiregnskap for overflaten: sol på veggen (med skygge fra terrenget rundt), varmestråling til og fra himmelen, vind og varme fra berget innenfor. Det gir bergtemperaturen time for time, og den styrer hvor fort vannet fordamper.' },
  { tittel: 'Vannet på veggen', tekst: 'Vannet føres i tre lagre: den tynne filmen på overflaten, vann som blir liggende på hyller, i tak og i sprekker, og et sakte sigereservoar. Regn og kondens fyller på, fordampning tømmer.' },
  { tittel: 'Tørt, fuktig eller vått', tekst: 'Til slutt oversettes vannmengden til tørt, fuktig eller vått for hovedveggen. Enkeltruter kan avvike. Vann, is og snø følges hver for seg: frysing frigir varme, og smelting bruker varme før smeltevannet kan tørke. Is og snø på veggen vises som vått.' },
]

const VIDERE = [
  { status: 'ferdig', tittel: 'Fysisk modell for ni felt', tekst: 'Hvert felt har eget vær og egen retning, bratthet og horisont. Varselet oppdateres hver time.' },
  { status: 'pågår', tittel: 'Samle tilbakemeldinger', tekst: 'Hver gang noen melder hvordan fjellet faktisk var, sammenligner vi med varselet for samme time. Alt det neste bygger på dette.' },
  { status: 'neste', tittel: 'Kalibrere modellen per felt', tekst: 'Først tilpasser vi én parameter: hvor effektivt veggen tørker. Den nye verdien tas bare i bruk hvis den treffer bedre på regnepisoder den ikke er tilpasset, uten å gi flere falske varsler om tørt.' },
  { status: 'senere', tittel: 'Maskinlæring oppå fysikken', tekst: 'Modeller i scikit-learn og PyTorch som får fysikkmodellens anslag som utgangspunkt og lærer det fysikken ikke fanger, som trær, sigestriper og lav. De tas bare i bruk hvis de slår fysikken på nye data.' },
  { status: 'senere', tittel: 'En fasit som ikke avhenger av hvem som drar', tekst: 'Et kamera eller en enkel fuktsensor på én vegg ville gitt en observasjon hver time, også når ingen er der.' },
  { status: 'senere', tittel: 'Inn i nettføreren', tekst: 'Varselet på feltsidene i BKKs nettfører, og et spørsmål om forholdene når du logger en bestigning.' },
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
          Det sitter ingen sensorer på veggene. Varselet er et regnestykke: værdata fra MET, terreng fra Kartverket og
          fysikken for hvordan vann treffer berget, blir liggende og forsvinner igjen. Tilbakemeldingene fra dere som
          klatrer skal gjøre det mer treffsikkert over tid.
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
          Det er samme prinsipp som brukes til å varsle glatte veier og fuktige blader i landbruket. Parametrene er
          foreløpige anslag. Retning, bratthet og terreng kommer fra kart og nettfører, mens hvor utsatt veggen er for
          vind er vurdert lokalt. Overheng er skjermet mot regnet, men kan likevel bli våte av siging og kondens.
        </p>
      </Seksjon>

      <Seksjon id="feltene" tittel="Hva modellen sier om feltene">
        <p className="max-w-[65ch] text-text-tinted">
          Vi har kjørt modellen gjennom værhistorikken fra {periode ? `${periode[0].slice(0, 4)} til ${periode[1].slice(0, 4)}` : 'de siste årene'} for hvert felt.
          Tallene under er modellens anslag, ikke målinger.
        </p>
        <FeltForklaring felt={felt} />
        <Kort tittel="Andel tørre timer på dagtid (kl 08–20)"
              tekst="Beregnet med feltets eget vær. Sva fanger mer av regnet, mens vind, skygge og vann i sprekker avgjør hvor lenge veggen blir våt. En vegg som ofte er våt, kan likevel tørke fort når været først tillater det.">
          <MaanedLinjer serier={felt.map((f) => ({ slug: f.slug, navn: f.navn, verdier: f.tort_dagtid_per_maned }))}
                        maks={1} steg={0.25} enhet={prosent} label="Andel tørre timer på dagtid per måned for hvert felt" />
        </Kort>
        <Kort tittel="Timer med sol på veggen, per døgn"
              tekst="For at sola skal treffe veggen, må den stå foran bergflaten og over terrenget rundt, og skyene må slippe gjennom nok lys. Ekstraveggen vender mot nordvest, Helleneset mot vest og Sandvikens hovedvegg mot sør.">
          <MaanedStolper serier={felt.map((f) => ({ slug: f.slug, navn: f.navn, verdier: f.soltimer_per_dogn }))}
                         maks={solMaks} steg={2} enhet={(v) => `${v} t`} label="Timer med direkte sol på veggen per døgn, per måned" />
        </Kort>
        <Kort tittel="Tørketid i episodene som fullføres"
              tekst="Hvor lenge veggen er våt etter minst 2 mm regn på 12 timer, regnet fra tre timer opphold. Prikken er medianen, streken den midterste halvparten. Bare episoder som tørker innen 72 timer og før neste regnvær er med. Tabellen under teller alle episodene, også de med snø og is.">
          <Spenn
            maks={36}
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
          <p className="byline">Andelene regnes bare av episodene der utfallet er kjent på det tidspunktet. Nytt regn teller som avbrutt tørking, og episoder med hull i historikken er med så langt de kan vurderes.</p>
        </Kort>
        <Kort tittel="Feltene sammenlignet med samme vær"
              tekst="Et kontrollforsøk der alle feltene får været fra Ekstraveggen. Da er det bare retning, bratthet, skygge og de foreløpige lokale parametrene som skiller dem. Dette er altså ikke feltenes faktiske vær.">
          <MaanedLinjer serier={Object.entries(statistikk.felles_vaer.felt).map(([slug, f]) => ({ slug, navn: f.navn, verdier: f.tort_dagtid_per_maned }))}
                        maks={1} steg={0.25} enhet={prosent} label="Modellberegnede tørre dagtimer ved identisk vær" />
        </Kort>
      </Seksjon>

      <Seksjon id="data" tittel="Det vi har samlet så langt">
        {live && live.length > 0 ? (
          <>
            <p className="max-w-[65ch] text-text-tinted">
              {totalt === 0
                ? 'Ingen tilbakemeldinger ennå. Den første kan komme fra deg.'
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
              Tilbakemeldinger fra utviklingen er holdt utenfor. «Varselet stemte» skiller bare mellom tørt og ikke tørt,
              og sammenligner med varselet slik det så ut før den aktuelle timen.
            </p>
          </>
        ) : (
          <p className="max-w-[65ch] text-text-subtle">Tallene hentes fra databasen og er ikke tilgjengelige akkurat nå.</p>
        )}
      </Seksjon>

      <Seksjon id="skjevhet" tittel="Folk er mest på feltet når det er tørt">
        <p className="max-w-[65ch] text-text-tinted">
          Tilbakemeldingene blir skjeve: folk drar når de tror det er tørt, og blir hjemme når det er vått. Alle de
          enkle, tørre dagene gjør at en samlet treffprosent ser bedre ut enn den er. Vi måler derfor treff i timene
          rett etter regn for seg. Det er der det vises om modellen forstår tørking.
        </p>
        <p className="max-w-[65ch] text-text-tinted">
          Vi teller også regnepisoder, ikke bare meldinger, og tester alltid på andre episoder enn dem modellen er
          tilpasset. Flere meldinger fra samme regnvær er nyttige, men de er ikke uavhengige forsøk.
        </p>
        {sim.length > 0 && (
          <Kort tittel="Treff i timene etter regn, simulert"
                tekst="Lys søyle: modellen med startverdier. Mørk søyle: kalibrert på tilbakemeldinger. Søylen er snittet av tre simuleringer, og den røde streken viser beste og dårligste. Alt er testet på en sesong modellen ikke har sett.">
            <Simulering rader={sim} label="Treff etter regn med startverdier og kalibrert modell, ved 150 og 400 tilbakemeldinger" />
          </Kort>
        )}
        <p className="max-w-[65ch] text-sm leading-relaxed text-text-subtle">
          Også «det var tørt» er nyttig, særlig rett etter regn: det forteller hvor fort veggen tørker. Vi trenger
          meldinger både når varselet stemmer og når det bommer, for å kunne måle hvor godt modellen virker.
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
          <li>Tørt, fuktig og vått gjelder hovedveggen på hvert felt. Modellen ser ikke enkeltruter, trær rett foran veggen, sigestriper eller lav. Noen ruter tørker raskere enn resten av veggen, andre saktere.</li>
          <li>Parametrene for hvert felt, som hvor fort veggen tørker, er foreløpige og ikke kalibrert mot tilbakemeldinger ennå.</li>
          <li>Koordinatene for feltene er kartpunkter, ikke nøyaktig foten av veggen. Det kan forskyve når sola beregnes å treffe.</li>
        </ul>
        <p className="byline">
          Værdata: MET Nordic direkte fra MET Norway, med Open-Meteo som reserve og for historikk (CC BY 4.0). Historikkgrafene bruker arkiverte modellvarsler,
          ikke målt bergfuktighet. Terreng: Kartverket DOM/DTM (CC BY 4.0).
          Modell {statistikk.modellversjon}, beregnet {statistikk.generert}; de første {statistikk.oppvarming_dogn} døgnene er utelatt som oppvarming.
        </p>
      </Seksjon>
    </article>
  )
}
