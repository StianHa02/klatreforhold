import type { CSSProperties } from 'react'
import { type Time, klokke, statusFarge } from '@/lib/api'

// Én kolonne per time: farge = status med solstreken over (som i rutenettene), under: regn. `naIndeks` markerer timen nå;
// timene før er det modellen mener har vært (vises svakere). Grunnene står i verktøytipset.
// På smale skjermer brytes stripen i to rader, så hele døgnet vises uten å scrolle.
export default function HourStrip({ timer, naIndeks = 0 }: { timer: Time[]; naIndeks?: number }) {
  const n = timer.length
  const perRad = Math.ceil(n / 2) // timer per rad på mobil
  const kolonner = { '--n': n, '--m': perRad } as CSSProperties
  return (
    <section className="kort p-sm sm:p-md">
      <h2 className="seksjon mb-sm">Time for time</h2>
      <ol
        style={kolonner}
        className="isolate grid grid-cols-[repeat(var(--m),minmax(0,1fr))] gap-x-px gap-y-md sm:grid-cols-[repeat(var(--n),minmax(0,1fr))]"
      >
        {timer.map((t, i) => {
          return (
            <li
              key={t.tid}
              className="flex min-w-0 flex-col items-center gap-xs text-[11px] tabular-nums sm:text-xs"
              title={`${klokke(t.tid)}: ${t.status_tekst}. ${t.grunner.join('. ')}`}
            >
              <span className={i === naIndeks ? 'font-medium text-text-default' : 'text-text-subtle'}>
                {i === naIndeks ? 'Nå' : klokke(t.tid).slice(0, 2)}
              </span>
              <span
                aria-hidden
                className={`-mb-[2px] h-[3px] w-full ${
                  t.sol_pa_veggen ? 'bg-[var(--color-accent-red-400)]' : t.sol_mulig ? 'sol-mulig' : ''
                }`}
              />
              <span
                className={`h-lg w-full ${statusFarge[t.status]} ${i < naIndeks ? 'opacity-50' : ''} ${
                  i === naIndeks ? 'relative z-10 ring-2 ring-text-default ring-offset-1' : ''
                }`}
              />
              <span className="text-text-subtle">{t.nedbor_mm >= 0.1 ? t.nedbor_mm.toFixed(1) : ''}</span>
              {t.p_vatt !== null && <span className="text-text-subtle">{Math.round((1 - t.p_vatt) * 100)}</span>}
            </li>
          )
        })}
      </ol>
      <div className="mt-md flex flex-wrap gap-x-md gap-y-xs text-xs text-text-subtle">
        <Legend farge="bg-forhold-tort" tekst="Tørt" />
        <Legend farge="bg-forhold-fuktig" tekst="Fuktig" />
        <Legend farge="bg-forhold-vatt" tekst="Vått" />
        <span className="flex items-center gap-xs">
          <span aria-hidden className="inline-block h-[3px] w-sm bg-[var(--color-accent-red-400)]" />
          direkte sol på veggen
        </span>
        <span className="flex items-center gap-xs">
          <span aria-hidden className="inline-block h-[3px] w-sm sol-mulig" />
          sol mulig ved klar himmel
        </span>
        <span>0.4 = mm regn</span>
        {timer.some((t) => t.p_vatt !== null) && <span>heltall = % sjanse for tørt</span>}
      </div>
    </section>
  )
}

function Legend({ farge, tekst }: { farge: string; tekst: string }) {
  return (
    <span className="flex items-center gap-xs">
      <span aria-hidden className={`inline-block h-sm w-sm ${farge}`} />
      {tekst}
    </span>
  )
}
