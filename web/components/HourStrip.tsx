import type { CSSProperties } from 'react'
import { type Time, klokke, statusFarge } from '@/lib/api'

// Én kolonne per time: farge = status, under: regn mot veggen og sol. `naIndeks` markerer timen nå;
// timene før er det modellen mener har vært (vises svakere).
// På smale skjermer brytes stripen i to rader, så hele døgnet vises uten å scrolle.
export default function HourStrip({ timer, naIndeks = 0 }: { timer: Time[]; naIndeks?: number }) {
  const n = timer.length
  const perRad = Math.ceil(n / 2) // timer per rad på mobil
  const kolonner = { '--n': n, '--m': perRad } as CSSProperties
  return (
    <section className="rounded-xl border border-border-subtle bg-surface-default p-md">
      <h2 className="h3 mb-sm">{naIndeks > 0 ? `${naIndeks} timer tilbake og ${n - naIndeks - 1} fram` : 'Neste 24 timer'}</h2>
      <ol
        style={kolonner}
        className="grid grid-cols-[repeat(var(--m),minmax(0,1fr))] gap-x-px gap-y-md sm:grid-cols-[repeat(var(--n),minmax(0,1fr))]"
      >
        {timer.map((t, i) => {
          const radStart = i % perRad === 0
          const radSlutt = i % perRad === perRad - 1 || i === n - 1
          const rund = [
            i === 0 ? 'rounded-l-md' : radStart ? 'max-sm:rounded-l-md' : '',
            i === n - 1 ? 'rounded-r-md' : radSlutt ? 'max-sm:rounded-r-md' : '',
          ].join(' ')
          return (
            <li
              key={t.tid}
              className="flex min-w-0 flex-col items-center gap-xs text-[10px] tabular-nums sm:text-xs"
              title={`${klokke(t.tid)}: ${t.status_tekst}. ${t.grunner.join('. ')}`}
            >
              <span className={i === naIndeks ? 'font-medium text-text-default' : 'text-text-subtle'}>
                {i === naIndeks ? 'Nå' : klokke(t.tid).slice(0, 2)}
              </span>
              <span
                className={`h-lg w-full ${statusFarge[t.status]} ${rund} ${i < naIndeks ? 'opacity-50' : ''} ${
                  i === naIndeks ? 'ring-2 ring-text-default ring-offset-1' : ''
                }`}
              />
              <span className="h-[1rem] text-text-subtle">{t.sol_pa_veggen ? '☀' : ''}</span>
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
        <Legend farge="bg-forhold-is" tekst="Is" />
        <span>☀ sol på veggen</span>
        <span>desimaltall = nedbør mm/t</span>
        {timer.some((t) => t.p_vatt !== null) && <span>heltall = % sjanse for tørt (ML)</span>}
      </div>
    </section>
  )
}

function Legend({ farge, tekst }: { farge: string; tekst: string }) {
  return (
    <span className="flex items-center gap-xs">
      <span className={`inline-block h-sm w-sm rounded-sm ${farge}`} />
      {tekst}
    </span>
  )
}
