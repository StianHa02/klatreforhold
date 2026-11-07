import type { Metadata } from 'next'
import { Simulering } from '@/components/om/Diagrammer'
import ApneVedAnker from '@/components/om/ApneVedAnker'
import FeltStatistikk, { type FeltStat, Figur } from '@/components/om/FeltStatistikk'
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

// Sammenleggbar seksjon: tittel og én linje om innholdet, resten vises når den åpnes.
// `id` står på <details>, så /om#id kan åpne den (ApneVedAnker).
function Seksjon({ id, tittel, kort, children }: { id: string; tittel: string; kort: string; children: React.ReactNode }) {
  return (
    <details id={id} className="group kort">
      <summary className="focus flex cursor-pointer list-none items-center justify-between gap-sm p-sm hover:bg-background-tinted sm:p-md [&::-webkit-details-marker]:hidden">
        <div className="flex flex-col gap-[2px]">
          <h2 className="font-mabry text-xl leading-tight">{tittel}</h2>
          <span className="text-sm text-text-subtle">{kort}</span>
        </div>
        <Pil />
      </summary>
      <div className="flex flex-col gap-md border-t border-border-subtle p-sm sm:p-md">{children}</div>
    </details>
  )
}

// Pil ned, som i nettførerens Accordion og Ukerutenett. Snur når seksjonen er åpen.
function Pil() {
  return (
    <svg aria-hidden viewBox="0 0 24 24" width={22} height={22} fill="none" stroke="currentColor" strokeWidth={1.5}
         className="shrink-0 text-text-subtle transition group-open:rotate-180 motion-reduce:transition-none">
      <path strokeLinecap="round" strokeLinejoin="round" d="m19.5 8.25-7.5 7.5-7.5-7.5" />
    </svg>
  )
}

const STEG = [
  { tittel: 'Vær for akkurat dette feltet', tekst: 'MET Nordic (1 × 1 km) for feltets koordinater, radar de neste to timene og ECMWF lenger fram.' },
  { tittel: 'Regn som treffer veggen', tekst: 'Vindretning og -styrke mot veggens retning avgjør hvor mye regn som treffer. Sva får også regnet ovenfra.' },
  { tittel: 'Temperaturen i berget', tekst: 'Et energiregnskap med sol, skygge fra terrenget, varmestråling og vind gir bergtemperaturen.' },
  { tittel: 'Vannet på veggen', tekst: 'Vannet føres i tre lagre: overflatefilm, hyller og sprekker, og sakte siging.' },
  { tittel: 'Tørt, fuktig eller vått', tekst: 'Vannmengden blir til en status for hovedveggen. Is og snø vises som vått.' },
]

const VIDERE = [
  { status: 'ferdig', tittel: 'Fysisk modell for alle feltene', tekst: 'Eget vær, retning, bratthet og horisont per felt, oppdatert hver time.' },
  { status: 'pågår', tittel: 'Samle tilbakemeldinger', tekst: 'Hver melding sammenlignes med varselet for samme time.' },
  { status: 'neste', tittel: 'Kalibrere per felt', tekst: 'Tilpasse hvor fort veggen tørker, bare hvis det treffer bedre på nye regnvær.' },
  { status: 'senere', tittel: 'Maskinlæring oppå fysikken', tekst: 'Lære det fysikken ikke ser, som trær, siging og lav.' },
  { status: 'senere', tittel: 'Sensor eller kamera', tekst: 'En fasit hver time, også når ingen er på feltet.' },
  { status: 'senere', tittel: 'Inn i nettføreren', tekst: 'Varselet på feltsidene i BKKs nettfører.' },
]
const STATUSFARGE: Record<string, string> = {
  ferdig: 'bg-forhold-tort',
  pågår: 'bg-forhold-fuktig',
  neste: 'bg-accent-surface-default',
  senere: 'bg-surface-active',
}

export default async function OmModellen() {
  const live = await hentStatistikk()
  const navn = Object.fromEntries(felt.map((f) => [f.slug, f.navn]))
  const totalt = live?.reduce((n, f) => n + f.observasjoner, 0) ?? 0
  const sim = (statistikk.simulering ?? []) as { n: number; modell: string; snitt: number; min: number; maks: number }[]
  const periode = felt[0]?.periode
  const solMaks = Math.max(2, Math.ceil(Math.max(...felt.flatMap((f) => f.soltimer_per_dogn)) / 2) * 2)
  const fellesVaer = Object.entries(statistikk.felles_vaer.felt).map(([slug, f]) => ({ slug, navn: f.navn, verdier: f.tort_dagtid_per_maned }))

  return (
    <article className="flex flex-col gap-lg">
      <ApneVedAnker />
      <header className="flex flex-col gap-sm">
        <h1 className="font-mabry text-[28px] leading-tight sm:text-[32px]">Hvordan vi regner ut om fjellet er tørt</h1>
        <p className="max-w-[60ch] text-md leading-relaxed text-text-tinted sm:text-lg">
          Ingen sensorer på veggene: varselet regnes ut fra værdata, terreng og fysikk. Tilbakemeldingene deres gjør det
          bedre over tid.
        </p>
      </header>

      <section aria-labelledby="vann-tittel" id="vann" className="flex flex-col gap-sm">
        <h2 id="vann-tittel" className="font-mabry text-xl leading-tight">Hva gjør fjellet vått, og hva tørker det?</h2>
        <div className="kort p-xs sm:p-md">
          <VeggSnitt />
        </div>
        <ol className="grid grid-cols-2 gap-x-sm gap-y-sm lg:grid-cols-4">
          {FORKLARING.map((f) => (
            <li key={f.n} className="flex gap-xs">
              <span aria-hidden className="mt-[1px] flex h-[22px] w-[22px] shrink-0 items-center justify-center rounded-full border border-text-default text-xs font-semibold">
                {f.n}
              </span>
              <span className="flex flex-col text-sm leading-snug">
                <span className="font-medium">{f.tittel}</span>
                <span className="text-text-tinted">{f.tekst}</span>
              </span>
            </li>
          ))}
        </ol>
      </section>

      <div className="flex flex-col gap-sm">
        <Seksjon id="regnestykket" tittel="Regnestykket, hver time" kort="Fem steg fra værdata til tørt, fuktig eller vått">
          <ol className="flex flex-col gap-sm border-l-2 border-border-tinted pl-md">
            {STEG.map((s, i) => (
              <li key={s.tittel} className="flex flex-col gap-[2px]">
                <span className="h3">
                  <span className="mr-xs tabular-nums text-text-subtle">{i + 1}.</span>
                  {s.tittel}
                </span>
                <span className="max-w-[65ch] text-sm leading-relaxed text-text-tinted">{s.tekst}</span>
              </li>
            ))}
          </ol>
          <p className="max-w-[65ch] text-sm text-text-subtle">
            Samme prinsipp brukes til å varsle glatte veier. Parametrene er foreløpige anslag.
          </p>
        </Seksjon>

        <Seksjon id="feltene" tittel="Feltene gjennom året" kort="Når de er tørre, hvor fort de tørker, sol og regn">
          <p className="max-w-[65ch] text-sm text-text-tinted">
            Modellen kjørt på været {periode ? `${periode[0].slice(0, 4)}–${periode[1].slice(0, 4)}` : 'de siste årene'}.
            Anslag, ikke målinger.
          </p>
          <FeltStatistikk felt={felt as FeltStat[]} fellesVaer={fellesVaer} solMaks={solMaks} />
        </Seksjon>

        <Seksjon id="data" tittel="Tilbakemeldinger og veien videre" kort={
          live && live.length > 0 ? `${totalt} ${totalt === 1 ? 'tilbakemelding' : 'tilbakemeldinger'} så langt` : 'Hva vi har samlet, og hva som kommer'
        }>
          {live && live.length > 0 ? (
            <>
              <p className="max-w-[65ch] text-sm text-text-tinted">
                {totalt === 0
                  ? 'Ingen tilbakemeldinger ennå. Den første kan komme fra deg.'
                  : 'Vi trenger noen hundre per felt før vi kan kalibrere.'}
              </p>
              <ul className="flex flex-col gap-xs sm:hidden">
                {live.map((f) => (
                  <li key={f.felt} className="kort p-sm text-sm tabular-nums">
                    <a className="lenke font-medium" href={`/felt/${f.felt}`}>{navn[f.felt] ?? f.felt}</a>
                    <dl className="mt-xs grid grid-cols-[auto_1fr] gap-x-md gap-y-[2px]">
                      <dt className="text-text-subtle">Meldinger</dt>
                      <dd>{f.observasjoner} ({f.tort} / {f.fuktig} / {f.vatt + (f.is ?? 0)})</dd>
                      <dt className="text-text-subtle">Stemte</dt>
                      <dd>{f.andel_riktig === null ? '–' : `${Math.round(f.andel_riktig * 100)} % av ${f.vurdert}`}</dd>
                    </dl>
                  </li>
                ))}
              </ul>
              <div className="kort max-sm:hidden">
                <table className="w-full text-left text-sm tabular-nums">
                  <thead className="text-text-subtle">
                    <tr className="border-b border-border-subtle">
                      <th scope="col" className="p-sm font-normal">Felt</th>
                      <th scope="col" className="p-sm font-normal">Meldinger</th>
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
              <p className="text-xs text-text-subtle">«Stemte» skiller tørt fra ikke tørt. Meldinger fra utviklingen er holdt utenfor.</p>
            </>
          ) : (
            <p className="text-sm text-text-subtle">Tallene hentes fra databasen og er ikke tilgjengelige akkurat nå.</p>
          )}

          <div className="flex flex-col gap-xs">
            <h3 className="h3">Folk drar når det er tørt</h3>
            <p className="max-w-[65ch] text-sm leading-relaxed text-text-tinted">
              Derfor blir en samlet treffprosent for god. Vi måler treff rett etter regn for seg, og tester på andre
              regnvær enn modellen er tilpasset. Meld også når det er tørt, særlig dagen etter regn.
            </p>
          </div>
          {sim.length > 0 && (
            <Figur tittel="Treff etter regn, simulert" tekst="Lys: startverdier. Mørk: kalibrert. Rød strek: beste og dårligste av tre kjøringer.">
              <Simulering rader={sim} label="Treff etter regn med startverdier og kalibrert modell, ved 150 og 400 tilbakemeldinger" />
            </Figur>
          )}

          <div className="flex flex-col gap-xs">
            <h3 className="h3">Veien videre</h3>
            <ol className="flex flex-col">
              {VIDERE.map((v) => (
                <li key={v.tittel} className="group/steg relative flex gap-sm pb-sm last:pb-0">
                  <span aria-hidden className="absolute top-[14px] bottom-0 left-[5px] w-[2px] bg-border-subtle group-last/steg:hidden" />
                  <span aria-hidden className={`relative mt-[5px] h-[12px] w-[12px] shrink-0 rounded-full ${STATUSFARGE[v.status]}`} />
                  <span className="flex flex-col text-sm leading-snug">
                    <span>
                      <span className="font-medium">{v.tittel}</span>
                      <span className="ml-xs text-xs text-text-subtle">{v.status}</span>
                    </span>
                    <span className="text-text-tinted">{v.tekst}</span>
                  </span>
                </li>
              ))}
            </ol>
          </div>
        </Seksjon>

        <Seksjon id="forbehold" tittel="Forbehold og kilder" kort="Sjekk alltid fjellet selv">
          <ul className="flex max-w-[65ch] list-disc flex-col gap-xs pl-lg text-sm leading-relaxed text-text-tinted">
            <li>Varselet er et anslag. Sjekk fjellet selv, særlig etter mye regn og om vinteren.</li>
            <li>Det gjelder hovedveggen, ikke enkeltruter, trær foran veggen, sigestriper eller lav.</li>
            <li>Parametrene er ikke kalibrert mot tilbakemeldinger ennå.</li>
            <li>Feltkoordinatene er kartpunkter, så soltidene kan være litt forskjøvet.</li>
          </ul>
          <p className="byline">
            Vær: MET Nordic fra MET Norway, Open-Meteo som reserve og historikk (CC BY 4.0). Regn ved Ekstraveggen:{' '}
            <a className="lenke" href="https://weather.kippenbroeck.no/">Bønes værstasjon</a> (CC BY 4.0). Terreng: Kartverket DOM/DTM (CC BY 4.0).
            Modell {statistikk.modellversjon}, statistikk beregnet {statistikk.generert}.
          </p>
        </Seksjon>
      </div>
    </article>
  )
}
