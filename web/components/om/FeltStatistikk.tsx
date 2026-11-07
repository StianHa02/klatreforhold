'use client'

import { type ReactNode, useState } from 'react'
import {
  FeltStrek, Kompass, MaanedLinjer, MaanedStolper, RegnPaVeggen, type Serie, Spenn, Varmekart, VenteStolper,
} from '@/components/om/Diagrammer'
import { kompass } from '@/lib/dager'

type Tid = { median: number; q25: number; q75: number; n: number }
type Innen = Record<'6' | '12' | '24', { andel: number | null }>
export type FeltStat = {
  slug: string
  navn: string
  orientering: number
  helning: number
  tort_dagtid_per_maned: (number | null)[]
  soltimer_per_dogn: (number | null)[]
  torketid_timer: { sommer?: Tid | null; vinter?: Tid | null }
  torkeepisoder: Record<'sommer' | 'vinter', { innen_timer: Innen }>
  regn_pa_veggen_mm_per_ar: number
  nedbor_mm_per_ar: number
}

const START = ['ekstraveggen', 'helleneset', 'sandviken'] // ulike retninger: nordvest, vest og sør
const prosent = (v: number) => `${Math.round(v * 100)} %`

export function Figur({ tittel, tekst, children }: { tittel: string; tekst?: string; children: ReactNode }) {
  return (
    <figure className="flex flex-col gap-sm kort p-sm sm:p-md">
      <figcaption className="flex flex-col gap-[2px]">
        <span className="h3">{tittel}</span>
        {tekst && <span className="byline max-w-[65ch]">{tekst}</span>}
      </figcaption>
      {children}
    </figure>
  )
}

// Statistikken per felt. Diagrammene med alle feltene viser én rad per felt; de med linjer og stolper
// blir uleselige med mange felt, så der velger man feltene med knappene (tre felt er valgt fra start).
export default function FeltStatistikk({ felt, fellesVaer, solMaks }: { felt: FeltStat[]; fellesVaer: Serie[]; solMaks: number }) {
  const [valgt, setValgt] = useState<string[]>(() => START.filter((s) => felt.some((f) => f.slug === s)))
  const [sesong, setSesong] = useState<'sommer' | 'vinter'>('sommer')
  const med = <T extends { slug: string }>(liste: T[]) => liste.filter((f) => valgt.includes(f.slug))
  const bytt = (slug: string) => setValgt((v) => (v.includes(slug) ? v.filter((s) => s !== slug) : [...v, slug]))

  return (
    <div className="flex flex-col gap-md">
      <Figur tittel="Når på året er feltet tørt?" tekst="Andel tørre timer på dagtid (kl 08–20) per måned. Mørkere er tørrere.">
        <Varmekart serier={felt.map((f) => ({ slug: f.slug, navn: f.navn, verdier: f.tort_dagtid_per_maned }))}
                   label="Andel tørre timer på dagtid per måned for hvert felt" />
        <Skala />
      </Figur>

      <Figur tittel="Hvor lenge må du vente etter regn?" tekst="Andel regnvær der veggen er tørr innen 6, 12 og 24 timer etter at det slutter. Nytt regn teller som ikke tørt.">
        <div className="flex border-b-2 border-border-subtle" role="group" aria-label="Sesong">
          <button type="button" className="fane" aria-pressed={sesong === 'sommer'} onClick={() => setSesong('sommer')}>Sommer</button>
          <button type="button" className="fane" aria-pressed={sesong === 'vinter'} onClick={() => setSesong('vinter')}>Vinter</button>
        </div>
        <VenteStolper
          label={`Andel regnepisoder som er tørre innen 6, 12 og 24 timer, ${sesong}`}
          rader={felt.map((f) => {
            const i = f.torkeepisoder[sesong].innen_timer
            return { slug: f.slug, navn: f.navn, innen: [i['6'].andel, i['12'].andel, i['24'].andel] }
          })}
        />
        <span className="flex flex-wrap gap-x-md gap-y-xs text-xs text-text-subtle">
          {([[1, '6 t'], [0.6, '12 t'], [0.3, '24 t']] as const).map(([op, t]) => (
            <span key={t} className="flex items-center gap-xs">
              <span aria-hidden className="inline-block h-[10px] w-[14px] bg-forhold-tort" style={{ opacity: op }} />
              innen {t}
            </span>
          ))}
        </span>
      </Figur>

      <Figur tittel="Hvor mye av regnet treffer veggen?" tekst="Lys stolpe: nedbør per år. Mørk: det som treffer veggen. Bratte og overhengende vegger er skjermet.">
        <RegnPaVeggen label="Regn som treffer veggen sammenlignet med all nedbør, per år"
                      rader={felt.map((f) => ({ slug: f.slug, navn: f.navn, vegg: f.regn_pa_veggen_mm_per_ar, totalt: f.nedbor_mm_per_ar }))} />
      </Figur>

      <Figur tittel="Hvilken vei vender feltene?" tekst="Østvegger får morgensol, vestvegger kveldssol.">
        <div className="flex flex-col items-center gap-md sm:flex-row sm:items-start">
          <div className="w-full sm:w-1/2">
            <Kompass felt={felt} label="Retningen hvert felt vender" />
          </div>
          <ul className="grid w-full grid-cols-1 gap-xs text-sm min-[400px]:grid-cols-2 sm:w-1/2 sm:grid-cols-1">
            {[...felt].sort((a, b) => a.orientering - b.orientering).map((f) => (
              <li key={f.slug} className="flex items-center gap-xs">
                <FeltStrek slug={f.slug} />
                <span>{f.navn}</span>
                <span className="text-text-subtle">{kompass(f.orientering, 8)}, {f.helning > 90 ? 'overheng' : f.helning < 90 ? 'sva' : 'loddrett'}</span>
              </li>
            ))}
          </ul>
        </div>
      </Figur>

      <div className="flex flex-col gap-xs">
        <span className="text-sm text-text-subtle">Velg felt å sammenligne i diagrammene under</span>
        <div className="-mx-md flex gap-xs overflow-x-auto px-md pb-xs sm:mx-0 sm:flex-wrap sm:px-0" role="group" aria-label="Felt i diagrammene">
          {felt.map((f) => (
            <button
              key={f.slug}
              type="button"
              aria-pressed={valgt.includes(f.slug)}
              onClick={() => bytt(f.slug)}
              className="focus flex shrink-0 cursor-pointer items-center gap-xs rounded-lg border-2 border-border-default bg-surface-default px-sm py-xs text-sm transition hover:bg-surface-tinted aria-pressed:border-accent-border-default aria-pressed:bg-surface-tinted aria-[pressed=false]:text-text-subtle"
            >
              <FeltStrek slug={f.slug} />
              {f.navn}
            </button>
          ))}
        </div>
      </div>

      {valgt.length === 0 ? (
        <p className="text-sm text-text-subtle">Velg minst ett felt.</p>
      ) : (
        <>
          <Figur tittel="Tørketid etter regn" tekst="Prikk: median. Strek: den midterste halvparten. Bare regnvær som tørker innen 72 timer.">
            <Spenn
              maks={36}
              label="Tørketid etter regn for valgte felt, sommer og vinter"
              rader={(['sommer', 'vinter'] as const).map((s) => ({
                gruppe: s === 'sommer' ? 'Sommer (apr–sep)' : 'Vinter (okt–mar)',
                spenn: med(felt).flatMap((f) => (f.torketid_timer[s] ? [{ slug: f.slug, navn: f.navn, ...f.torketid_timer[s]! }] : [])),
              }))}
            />
          </Figur>
          <Figur tittel="Timer med sol på veggen, per døgn" tekst="Sola må stå foran veggen og over terrenget, og skyene må slippe den gjennom.">
            <MaanedStolper serier={med(felt).map((f) => ({ slug: f.slug, navn: f.navn, verdier: f.soltimer_per_dogn }))}
                           maks={solMaks} steg={2} enhet={(v) => `${v} t`} label="Timer med direkte sol på veggen per døgn, per måned" />
          </Figur>
          <Figur tittel="Med samme vær" tekst="Alle feltene får været fra Ekstraveggen, så bare retning, bratthet og skygge skiller dem.">
            <MaanedLinjer serier={med(fellesVaer)} maks={1} steg={0.25} enhet={prosent}
                          label="Modellberegnede tørre dagtimer ved identisk vær" />
          </Figur>
        </>
      )}
    </div>
  )
}

function Skala() {
  return (
    <span className="flex items-center gap-xs text-xs text-text-subtle" aria-hidden>
      0 %
      <span className="h-[10px] w-[120px] bg-gradient-to-r from-forhold-tort/10 to-forhold-tort" />
      100 %
    </span>
  )
}
