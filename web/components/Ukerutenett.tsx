'use client'

import { type ButtonHTMLAttributes, type ReactNode, useState } from 'react'
import { type Status, statusFarge } from '@/lib/api'
import { BOKSTAV, SKALA_MM, STATUS_TEKST, type UkeRad, biter, pad } from '@/lib/dager'

// Ukerutenett: én rad per døgn med 24 timer, uten sideveis rulling. Øverst i hver rad en strek når sola
// står på veggen, så status per time og regn som søyler under. Klatrernes meldinger er prikker.
// Trykk på en dag for time for time (tabellen er også den tilgjengelige versjonen av rutenettet).
// All tekst lages på serveren, så klienten formaterer ingen datoer selv.

const RAD = 'grid grid-cols-[4.5rem_minmax(0,1fr)_6rem] items-center gap-x-sm sm:grid-cols-[6rem_minmax(0,1fr)_9rem]'
const MANGLER = 'mangler' // «dagen før»-visning: timen finnes, men varselet ble ikke lagret
type Verdi = Status | typeof MANGLER
const BAND_TOPP = 5 // sol 3 px + 2 px luft
const BAND_H = 22
const REGN_H = 12
const pst = (h: number) => `${(h / 24) * 100}%`
const MORK = 'text-[color:var(--color-dark-900)]' // mørk tekst har nok kontrast på alle statusfargene

export default function Ukerutenett({ rader, bryter = false, tekster, treff }: {
  rader: UkeRad[]
  bryter?: boolean // vis «Slik det ble | Slik det ble varslet»
  tekster: { etter: string; for?: string }
  treff?: { etter: string; for: string }
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
      <p className="text-sm text-text-subtle">{visFor ? tekster.for : tekster.etter}</p>
      {treff && <p className="mt-xs text-sm">{visFor ? treff.for : treff.etter}</p>}

      <div className={`${RAD} mt-sm text-xs text-text-subtle`} aria-hidden>
        <span />
        <span className="relative h-[16px] self-end">
          {[0, 6, 12, 18].map((h) => (
            <span key={h} className="absolute top-0 text-text-tinted" style={{ left: pst(h) }}>kl {pad(h)}</span>
          ))}
        </span>
        <span className="grid grid-cols-3 text-right leading-tight">
          <span><span className="block font-medium text-text-default">Regn</span>mm</span>
          <span><span className="block font-medium text-text-default">Sol</span>timer</span>
          <span><span className="block font-medium text-text-default">Vind</span>m/s</span>
        </span>
      </div>
      <ul>
        {rader.map((r) => (
          <li key={r.id} className="border-t border-border-subtle first:border-t-0">
            <details className="group">
              <summary className={`${RAD} focus cursor-pointer list-none rounded-md py-[6px] hover:bg-background-tinted [&::-webkit-details-marker]:hidden`}>
                <span className="whitespace-nowrap text-sm leading-tight">
                  <span aria-hidden className="mr-[2px] inline-block text-text-subtle transition group-open:rotate-90">›</span>
                  {r.navn}
                  {r.merknad && <span className="block pl-[10px] text-xs text-text-subtle">{r.merknad}</span>}
                </span>
                <Band rad={r} visFor={visFor} />
                <span aria-hidden className="grid grid-cols-3 text-right text-sm tabular-nums">
                  <span>{r.sum.regn}</span>
                  <span>{r.sum.sol}</span>
                  <span>{r.sum.vind}</span>
                </span>
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
    <span aria-hidden className="relative block" style={{ height: BAND_TOPP + BAND_H + 2 + REGN_H }}>
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

function Tabell({ rad, visVarslet }: { rad: UkeRad; visVarslet: boolean }) {
  return (
    <div className="mb-sm overflow-x-auto">
      <table className="w-full text-left text-sm tabular-nums">
        <caption className="sr-only">Time for time</caption>
        <thead className="text-text-subtle">
          <tr>
            <th scope="col" className="py-[2px] pr-sm font-normal">Kl</th>
            <th scope="col" className="pr-sm font-normal">Berget</th>
            {visVarslet && <th scope="col" className="pr-sm font-normal">Dagen før</th>}
            <th scope="col" className="pr-sm text-right font-normal">Regn mm</th>
            <th scope="col" className="pr-sm font-normal">Sol</th>
            <th scope="col" className="pr-sm text-right font-normal">Vind m/s</th>
            <th scope="col" className="text-right font-normal" title="Luftfuktighet">Luftfukt.</th>
          </tr>
        </thead>
        <tbody>
          {rad.tabell.map((t) => (
            <tr key={t.kl} className="border-t border-border-subtle">
              <td className="py-[2px] pr-sm">{t.kl}</td>
              <td className="pr-sm"><Status s={t.s} /></td>
              {visVarslet && <td className="pr-sm">{t.v ? <Status s={t.v} /> : <span className="text-text-subtle">ikke lagret</span>}</td>}
              <td className="pr-sm text-right">{t.regn}</td>
              <td className="pr-sm">{t.sol ? 'ja' : t.solMulig ? 'mulig' : '–'}</td>
              <td className="pr-sm text-right">{t.vind}</td>
              <td className="text-right">{t.fukt}</td>
            </tr>
          ))}
        </tbody>
      </table>
      {rad.meldinger.length > 0 && (
        <ul className="mt-xs flex flex-col gap-[2px] text-sm">
          {rad.meldinger.map((m, i) => <li key={i}>{m.tekst}</li>)}
        </ul>
      )}
    </div>
  )
}

function Status({ s }: { s: Status }) {
  return (
    <span className="inline-flex items-center gap-[4px]">
      <span aria-hidden className={`inline-block h-[10px] w-[10px] rounded-full ${statusFarge[s]}`} />
      {STATUS_TEKST[s]}
    </span>
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
        {nokkel(<span aria-hidden className="inline-block h-[9px] w-[5px] rounded-b-[2px] bg-[var(--color-accent-blue-400)]" />, `regn (full søyle ${SKALA_MM} mm/t)`)}
      </div>
      {harMeldinger && (
        <p className="flex items-center gap-sm">
          <span aria-hidden className={`relative mr-[8px] inline-flex h-[18px] w-[18px] shrink-0 items-center justify-center rounded-full text-[11px] font-semibold ring-2 ring-white ${MORK} ${statusFarge.tort}`}>
            {BOKSTAV.tort}
            <Treff ok />
          </span>
          <span>
            En klatrer meldte hvordan det var (T tørt, F fuktig, V vått). ✓ betyr at fargen på stripen stemte med det klatreren
            meldte, ✗ at den bommet.
          </span>
        </p>
      )}
      <p>Trykk på en dag for time for time.</p>
    </div>
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

// Fane i nettførerens stil: blå strek under den valgte
function Fane({ valgt, ...rest }: { valgt: boolean } & ButtonHTMLAttributes<HTMLButtonElement>) {
  return <button type="button" aria-pressed={valgt} className="fane" {...rest} />
}
