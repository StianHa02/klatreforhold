'use client'

import { type ButtonHTMLAttributes, type ReactNode, useState } from 'react'
import { type Status, statusFarge } from '@/lib/api'
import { BOKSTAV, SKALA_MM, STATUS_TEKST, type UkeRad, biter, pad } from '@/lib/dager'

// Ukerutenett: én rad per døgn med 24 timer, uten sideveis rulling. Øverst i hver rad en strek når sola
// står på veggen, så status per time og regn som søyler under. Klatrernes meldinger er prikker.
// Trykk på en dag for time for time (tabellen er også den tilgjengelige versjonen av rutenettet).
// All tekst lages på serveren, så klienten formaterer ingen datoer selv.

// På mobil står navn, summer og pil på én linje og stripen i full bredde under; fra sm: fire kolonner
const RAD = 'grid grid-cols-[auto_minmax(0,1fr)_1.25rem] items-center gap-x-sm gap-y-[4px] sm:grid-cols-[6rem_minmax(0,1fr)_9rem_1.25rem]'
const STRIPE = 'max-sm:col-span-full max-sm:row-start-2' // stripen: egen rad på mobil
const MERKER = [6, 12, 18] // klokkeslett over stripene
const MANGLER = 'mangler' // «dagen før»-visning: timen finnes, men varselet ble ikke lagret
type Verdi = Status | typeof MANGLER
const BAND_TOPP = 5 // sol 3 px + 2 px luft
const BAND_H = 22
const REGN_H = 12
const pst = (h: number) => `${(h / 24) * 100}%`
const MORK = 'text-[color:var(--color-dark-900)]' // mørk tekst har nok kontrast på alle statusfargene

export default function Ukerutenett({ rader, bryter = false }: {
  rader: UkeRad[]
  bryter?: boolean // vis «Slik det ble | Slik det ble varslet»
}) {
  const [vis, setVis] = useState<'etter' | 'for'>('etter')
  const visFor = bryter && vis === 'for'
  return (
    <div>
      {bryter && (
        <div className="mb-xs flex flex-wrap border-b-2 border-border-subtle" role="group" aria-label="Hva fargene viser">
          <Fane valgt={!visFor} onClick={() => setVis('etter')}>Slik det ble</Fane>
          <Fane valgt={visFor} onClick={() => setVis('for')}>Slik det ble varslet</Fane>
        </div>
      )}

      <div className={`${RAD} mt-sm px-xs text-xs text-text-subtle`} aria-hidden>
        <span className="max-sm:hidden" />
        <span className="relative h-[16px] self-end max-sm:col-span-full">
          {MERKER.map((h) => (
            <span key={h} className="absolute top-0 -translate-x-1/2 text-text-tinted" style={{ left: pst(h) }}>{pad(h)}</span>
          ))}
        </span>
        <span className="grid grid-cols-3 text-right leading-tight max-sm:hidden">
          <span><span className="block font-medium text-text-default">Regn</span>mm</span>
          <span><span className="block font-medium text-text-default">Sol</span>timer</span>
          <span><span className="block font-medium text-text-default">Vind</span>m/s</span>
        </span>
        <span className="max-sm:hidden" />
      </div>
      <ul>
        {rader.map((r) => (
          <li key={r.id} className="border-t border-border-subtle first:border-t-0">
            <details className="group">
              <summary className={`${RAD} group/rad focus cursor-pointer list-none rounded-md px-xs py-[6px] hover:bg-background-tinted group-open:bg-surface-tinted [&::-webkit-details-marker]:hidden`}>
                <span className="whitespace-nowrap text-sm leading-tight">
                  {r.navn}
                  {r.merknad && <span className="block text-xs text-text-subtle">{r.merknad}</span>}
                </span>
                <Band rad={r} visFor={visFor} />
                <span aria-hidden className="text-right text-sm tabular-nums text-text-tinted sm:hidden">{r.sum.linje}</span>
                <span aria-hidden className="grid grid-cols-3 text-right text-sm tabular-nums max-sm:hidden">
                  <span>{r.sum.regn}</span>
                  <span>{r.sum.sol}</span>
                  <span>{r.sum.vind}</span>
                </span>
                <Pil />
                <span className="sr-only">{r.lang}</span>
              </summary>
              <Tabell rad={r} visVarslet={bryter} />
            </details>
          </li>
        ))}
      </ul>
      <Forklaring visFor={visFor} harMeldinger={rader.some((r) => r.meldinger.length > 0)} />
    </div>
  )
}

function Band({ rad, visFor }: { rad: UkeRad; visFor: boolean }) {
  const verdier = rad.celler.map((c): Verdi | null => (c ? (visFor ? (c.v ?? MANGLER) : c.s) : null))
  // «nå»-etiketten på den siden av streken der det ikke er timer
  const naHoyre = rad.na !== undefined && rad.celler.slice(Math.ceil(rad.na)).every((c) => !c)
  return (
    <span aria-hidden className={`relative block ${STRIPE}`} style={{ height: BAND_TOPP + BAND_H + 2 + REGN_H }}>
      <span className="absolute inset-x-0 top-0 grid h-[3px] grid-cols-24">
        {rad.celler.map((c, h) => (
          <span key={h} className={c?.sol ? 'bg-[var(--color-accent-red-400)]' : c?.solMulig ? 'bg-[var(--color-accent-red-200)]' : ''} />
        ))}
      </span>
      {biter(verdier).map((b) => {
        if (b.v === null) return null
        // Biten som starter eller slutter i timen med «nå» går helt inn til streken med rett kant,
        // så det ikke blir et hull mellom nå-streken og fargen
        const na = rad.na
        const starterVedNa = na !== undefined && !verdier[b.fra - 1] && na >= b.fra - 1 && na < b.fra + 1 // varselet: timene før nå mangler
        const slutterVedNa = na !== undefined && !starterVedNa && !verdier[b.til] && na > b.til - 1 && na <= b.til + 1 // historikken
        const fra = starterVedNa ? na! : b.fra
        const til = slutterVedNa ? na! : b.til
        const venstre = starterVedNa ? '0px' : '1px'
        const hoyre = slutterVedNa ? '0px' : '1px'
        const rund = `${starterVedNa ? 'rounded-l-none' : ''} ${slutterVedNa ? 'rounded-r-none' : ''}`
        return (
          <span
            key={b.fra}
            className={`absolute rounded-[3px] ${rund} ${b.v === MANGLER ? 'bg-surface-tinted' : statusFarge[b.v]}`}
            style={{ top: BAND_TOPP, height: BAND_H, left: `calc(${pst(fra)} + ${venstre})`, width: `calc(${pst(til - fra)} - ${venstre} - ${hoyre})` }}
          />
        )
      })}
      <span className="absolute inset-x-0 grid grid-cols-24" style={{ top: BAND_TOPP + BAND_H + 2, height: REGN_H }}>
        {rad.celler.map((c, h) => (
          <span key={h} className="px-[22%]">
            {c && c.regn >= 0.05 && (
              <span
                className="block rounded-b-[2px] bg-[var(--color-accent-blue-400)]"
                style={{ height: Math.max(2, (Math.min(c.regn, SKALA_MM) / SKALA_MM) * REGN_H) }}
              />
            )}
          </span>
        ))}
      </span>
      {rad.na !== undefined && (
        <>
          <span
            className="absolute w-[3px] -translate-x-1/2 bg-accent-surface-default"
            style={{ left: pst(rad.na), top: 0, height: BAND_TOPP + BAND_H + 2 + REGN_H }}
          />
          <span
            className={`absolute rounded-sm bg-accent-surface-default px-[5px] py-[2px] text-xs font-semibold leading-none text-accent-text-default ${
              naHoyre ? 'ml-[5px]' : '-ml-[5px]'
            }`}
            style={{ left: pst(rad.na), top: BAND_TOPP + BAND_H / 2, transform: `translateY(-50%)${naHoyre ? '' : ' translateX(-100%)'}` }}
          >
            nå
          </span>
        </>
      )}
      {rad.meldinger.map((m, i) => {
        const ok = visFor ? m.for : m.etter
        return (
          <span
            key={i}
            className={`absolute flex h-[18px] w-[18px] -translate-x-1/2 -translate-y-1/2 items-center justify-center rounded-full text-[11px] font-semibold ring-2 ring-white ${MORK} ${statusFarge[m.status]}`}
            style={{ left: pst(m.pos), top: BAND_TOPP + BAND_H / 2 }}
          >
            {BOKSTAV[m.status]}
            {ok !== null && <Treff ok={ok} />}
          </span>
        )
      })}
      <span className="absolute inset-0 grid grid-cols-24">
        {rad.celler.map((c, h) => <span key={h} title={c?.tittel} />)}
      </span>
    </span>
  )
}

// Klatretimene vises først; natta kan slås på. Kolonnene har faste bredder, så de står likt fra dag til dag.
// På mobil er kolonnene smalere, bergtemperaturen står under lufttemperaturen og sola vises bare som strek,
// så tabellen får plass uten sideveis rulling.
const KLATRETID = (h: number) => h >= 6 && h < 22

function Tabell({ rad, visVarslet }: { rad: UkeRad; visVarslet: boolean }) {
  const [heleDognet, setHeleDognet] = useState(false)
  const dag = rad.tabell.filter((t) => KLATRETID(t.h))
  const skjult = rad.tabell.length - dag.length
  const timer = heleDognet || dag.length === 0 ? rad.tabell : dag
  const th = 'py-xs align-bottom font-normal leading-tight'
  return (
    <div className="mb-sm overflow-x-auto px-xs">
      <table className="w-full table-fixed text-left text-sm tabular-nums sm:min-w-[30rem]">
        <caption className="sr-only">Time for time</caption>
        <colgroup>
          <col className="w-[1.5rem] sm:w-[3.5rem]" />
          <col className="w-[3.25rem] sm:w-[5.5rem]" />
          {visVarslet && <col className="w-[3.25rem] sm:w-[5.5rem]" />}
          <col className="w-[3rem] sm:w-[6.5rem]" />
          <col className="w-[2.5rem] sm:w-[4rem]" />
          <col className="w-[1.75rem] sm:w-[6.5rem]" />
          <col className="w-[2.5rem] sm:w-[5rem]" />
          <col className="w-[4.5rem] max-sm:hidden" />
        </colgroup>
        <thead className="text-xs text-text-subtle">
          <tr className="border-b border-border-default">
            <th scope="col" className={th}>Kl</th>
            <th scope="col" className={th}>Berget</th>
            {visVarslet && <th scope="col" className={th}>Dagen før</th>}
            <th scope="col" className={th} title="Lufttemperatur, og bergtemperaturen modellen regner ut">Temp °C</th>
            <th scope="col" className={`${th} pr-xs text-right sm:pr-md`}>Regn mm</th>
            <th scope="col" className={`${th} pl-xs sm:pl-0`}>Sol</th>
            <th scope="col" className={th}>Vind m/s</th>
            <th scope="col" className={`${th} text-right max-sm:hidden`} title="Luftfuktighet">Luftfukt.</th>
          </tr>
        </thead>
        <tbody>
          {timer.map((t) => (
            <tr key={t.kl} className={`border-b border-border-subtle last:border-0 ${t.na ? 'bg-surface-tinted font-medium' : ''}`}>
              <td className="py-[5px]">
                {t.kl}
                {t.na && <span className="ml-[4px] rounded-sm max-sm:sr-only bg-accent-surface-default px-[4px] text-[10px] font-semibold text-accent-text-default">nå</span>}
              </td>
              <td><StatusMerke s={t.s} /></td>
              {visVarslet && <td>{t.v ? <StatusMerke s={t.v} /> : (
                <span className="text-xs text-text-subtle">
                  <span aria-hidden className="sm:hidden">–</span>
                  <span className="max-sm:sr-only">ikke lagret</span>
                </span>
              )}</td>}
              <td title={`Luft ${t.temp}, berget ${t.berg}`}>
                {t.temp}
                <span className="block whitespace-nowrap text-xs font-normal text-text-subtle sm:ml-[6px] sm:inline">berg {t.berg}</span>
              </td>
              <td className="pr-xs text-right sm:pr-md">
                {t.regn && (
                  <span className="inline-flex items-center gap-[4px]" title={t.regnVegg ? 'Regnet treffer veggen' : 'Regnet treffer ikke veggen'}>
                    {t.regnVegg && <span aria-hidden className="inline-block h-[8px] w-[8px] rounded-full bg-[var(--color-accent-blue-400)]" />}
                    {t.regn}
                  </span>
                )}
              </td>
              <td className="pl-xs sm:pl-0"><Sol sol={t.sol} mulig={t.solMulig} /></td>
              <td title={t.vindTekst}>
                <span className="inline-flex items-center gap-[4px] sm:gap-[6px]">
                  <VindPil fra={t.vindFra} />
                  {t.vind}
                  <span className="sr-only">{t.vindTekst}</span>
                </span>
              </td>
              <td className="text-right text-text-subtle max-sm:hidden">{t.fukt}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <div className="mt-xs flex flex-wrap items-center justify-between gap-sm text-xs text-text-subtle">
        {timer.some((t) => t.regnVegg) ? (
          <span className="flex items-center gap-[4px]">
            <span aria-hidden className="inline-block h-[8px] w-[8px] rounded-full bg-[var(--color-accent-blue-400)]" />
            regnet treffer veggen
          </span>
        ) : <span />}
        {skjult > 0 && dag.length > 0 && (
          <button type="button" className="lenke text-sm text-text-default" onClick={() => setHeleDognet((v) => !v)}>
            {heleDognet ? 'Vis bare kl 06–22' : 'Vis hele døgnet'}
          </button>
        )}
      </div>
      {rad.meldinger.length > 0 && (
        <ul className="mt-xs flex flex-col gap-[2px] text-sm">
          {rad.meldinger.map((m, i) => <li key={i}>{m.tekst}</li>)}
        </ul>
      )}
    </div>
  )
}

// Status som farget merke, i samme farger som stripene i rutenettet; ordet står i merket
function StatusMerke({ s }: { s: Status }) {
  return (
    <span className={`inline-block w-[3rem] rounded-[3px] py-[1px] text-center text-[11px] font-medium sm:w-[4.5rem] sm:text-xs ${MORK} ${statusFarge[s]}`}>
      {STATUS_TEKST[s]}
    </span>
  )
}

// Pil som viser hvor vinden blåser (som på værkart): vind fra sør gir pil mot nord
function VindPil({ fra }: { fra: number }) {
  return (
    <svg
      aria-hidden
      viewBox="0 0 24 24"
      width={14}
      height={14}
      fill="none"
      stroke="currentColor"
      strokeWidth={2.5}
      className="shrink-0 text-text-tinted"
      style={{ transform: `rotate(${fra + 180}deg)` }}
    >
      <path strokeLinecap="round" strokeLinejoin="round" d="M12 20V4M5 11l7-7 7 7" />
    </svg>
  )
}

function Forklaring({ visFor, harMeldinger }: { visFor: boolean; harMeldinger: boolean }) {
  const nokkel = (merke: ReactNode, tekst: string) => (
    <span className="flex items-center gap-xs">{merke}{tekst}</span>
  )
  return (
    <div className="mt-sm flex flex-col gap-xs text-sm text-text-subtle">
      <div className="flex flex-wrap items-center gap-x-md gap-y-xs">
        {(['tort', 'fuktig', 'vatt'] as Status[]).map((s) => (
          <span key={s} className="flex items-center gap-xs">
            <span aria-hidden className={`inline-block h-[12px] w-[14px] rounded-[2px] ${statusFarge[s]}`} />
            {STATUS_TEKST[s]}
          </span>
        ))}
        {visFor && nokkel(<span aria-hidden className="inline-block h-[12px] w-[14px] rounded-[2px] bg-surface-tinted" />, 'ikke lagret')}
        {nokkel(<span aria-hidden className="inline-block h-[3px] w-[14px] bg-[var(--color-accent-red-400)]" />, 'direkte sol på veggen')}
        {nokkel(<span aria-hidden className="inline-block h-[3px] w-[14px] bg-[var(--color-accent-red-200)]" />, 'sol mulig ved klar himmel')}
        {nokkel(<span aria-hidden className="inline-block h-[9px] w-[5px] rounded-b-[2px] bg-[var(--color-accent-blue-400)]" />, 'regn')}
      </div>
      {harMeldinger && (
        <p className="flex items-center gap-sm">
          <span aria-hidden className={`relative mr-[8px] inline-flex h-[18px] w-[18px] shrink-0 items-center justify-center rounded-full text-[11px] font-semibold ring-2 ring-white ${MORK} ${statusFarge.tort}`}>
            {BOKSTAV.tort}
            <Treff ok />
          </span>
          <span>
            Tilbakemelding fra klatrer (T tørt, F fuktig, V vått). ✓ stemte, ✗ bommet.
          </span>
        </p>
      )}
    </div>
  )
}

// Pil ned til høyre i raden, som i nettførerens Accordion.
// Snur når dagen er åpen, og blir mørkere når musa er over raden.
function Pil() {
  return (
    <svg
      aria-hidden
      viewBox="0 0 24 24"
      width={20}
      height={20}
      fill="none"
      stroke="currentColor"
      strokeWidth={1.5}
      className="justify-self-end text-text-subtle transition group-open:rotate-180 group-hover/rad:text-text-default motion-reduce:transition-none"
    >
      <path strokeLinecap="round" strokeLinejoin="round" d="m19.5 8.25-7.5 7.5-7.5-7.5" />
    </svg>
  )
}

// Sol i timetabellen med samme merker som solstreken i rutenettet
function Sol({ sol, mulig }: { sol: boolean; mulig: boolean }) {
  if (!sol && !mulig) return null
  return (
    <span className="inline-flex items-center gap-[6px]" title={sol ? 'Direkte sol på veggen' : 'Sola står foran veggen, men det er skyet'}>
      <span aria-hidden className={`inline-block h-[3px] w-[14px] ${sol ? 'bg-[var(--color-accent-red-400)]' : 'bg-[var(--color-accent-red-200)]'}`} />
      <span className="max-sm:sr-only">{sol ? 'Direkte sol' : 'Skyet'}</span>
    </span>
  )
}

// ✓/✗ ved en klatrers melding: stemte stripen med det klatreren meldte?
function Treff({ ok }: { ok: boolean }) {
  return (
    <span
      className={`absolute -right-[11px] -top-[9px] flex h-[15px] w-[15px] items-center justify-center rounded-full bg-white text-[11px] font-bold leading-none shadow-sm ${
        ok ? 'text-forhold-tort' : 'text-state-error'
      }`}
    >
      {ok ? '✓' : '✗'}
    </span>
  )
}

function Fane({ valgt, ...rest }: { valgt: boolean } & ButtonHTMLAttributes<HTMLButtonElement>) {
  return <button type="button" aria-pressed={valgt} className="fane" {...rest} />
}
