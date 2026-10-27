import { type Time, klokke, statusFarge } from '@/lib/api'

// Én kolonne per time: farge = status, under: regn mot veggen og sol.
export default function HourStrip({ timer }: { timer: Time[] }) {
  return (
    <section className="rounded-xl bg-surface-default p-md shadow-sm">
      <h2 className="mb-sm font-medium">Neste 24 timer</h2>
      <div className="overflow-x-auto">
        <ol className="flex w-full min-w-[40rem] gap-px">
          {timer.map((t, i) => (
            <li
              key={t.tid}
              className="flex min-w-0 flex-1 flex-col items-center gap-xs text-xs"
              title={`${klokke(t.tid)}: ${t.status_tekst}. ${t.grunner.join('. ')}`}
            >
              <span className="text-text-subtle">{i === 0 ? 'Nå' : klokke(t.tid).slice(0, 2)}</span>
              <span className={`h-lg w-full ${statusFarge[t.status]} ${i === 0 ? 'rounded-l-md' : ''} ${i === timer.length - 1 ? 'rounded-r-md' : ''}`} />
              <span className="h-[1rem] text-text-subtle">{t.sol_pa_veggen ? '☀' : ''}</span>
              <span className="text-text-subtle">{t.nedbor_mm >= 0.1 ? t.nedbor_mm.toFixed(1) : ''}</span>
              {t.p_vatt !== null && <span className="text-text-subtle">{Math.round((1 - t.p_vatt) * 100)}%</span>}
            </li>
          ))}
        </ol>
      </div>
      <div className="mt-sm flex flex-wrap gap-md text-xs text-text-subtle">
        <Legend farge="bg-forhold-tort" tekst="Tørt" />
        <Legend farge="bg-forhold-fuktig" tekst="Fuktig" />
        <Legend farge="bg-forhold-vatt" tekst="Vått" />
        <Legend farge="bg-forhold-is" tekst="Is" />
        <span>☀ sol på veggen</span>
        <span>tall = nedbør mm/t</span>
        {timer.some((t) => t.p_vatt !== null) && <span>% = sannsynlighet for tørt (ML)</span>}
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
