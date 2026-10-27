import { type Varsel, klokke, dag, statusFarge, statusTint } from '@/lib/api'

export default function StatusHero({ varsel }: { varsel: Varsel }) {
  const s = varsel.sammendrag
  const om24 = varsel.timer[varsel.timer.length - 1]
  const nesteTort = s.neste_torre_time
  return (
    <section className={`rounded-xl p-md shadow-sm ${statusTint[s.status_na]}`}>
      <div className="flex items-center gap-md">
        <span className={`inline-block h-lg w-lg shrink-0 rounded-full ${statusFarge[s.status_na]}`} aria-hidden />
        <div>
          <p className="text-sm text-text-subtle">Nå på {varsel.felt.navn}</p>
          <p className="text-2xl font-semibold leading-tight">{s.status_na_tekst}</p>
        </div>
      </div>
      {s.grunner_na.length > 0 && (
        <ul className="mt-sm list-disc pl-lg text-sm text-text-tinted">
          {s.grunner_na.map((g) => (
            <li key={g}>{g}</li>
          ))}
        </ul>
      )}
      <dl className="mt-md grid grid-cols-1 gap-sm text-sm sm:grid-cols-3">
        <div className="rounded-lg bg-surface-default p-sm">
          <dt className="text-text-subtle">Om 24 timer</dt>
          <dd className="font-medium">{om24 ? `${om24.status_tekst} (${dag(om24.tid)} kl ${klokke(om24.tid)})` : '–'}</dd>
        </div>
        <div className="rounded-lg bg-surface-default p-sm">
          <dt className="text-text-subtle">Tørre timer neste døgn</dt>
          <dd className="font-medium">{s['tørre_timer_neste_24']} av 24</dd>
        </div>
        <div className="rounded-lg bg-surface-default p-sm">
          <dt className="text-text-subtle">{s.tort_na ? 'Blir vått' : 'Tørt igjen'}</dt>
          <dd className="font-medium">
            {s.tort_na
              ? s.neste_vate_time
                ? `${dag(s.neste_vate_time)} kl ${klokke(s.neste_vate_time)}`
                : 'Ikke neste døgn'
              : nesteTort
                ? `${dag(nesteTort)} kl ${klokke(nesteTort)}`
                : 'Ikke neste døgn'}
          </dd>
        </div>
      </dl>
    </section>
  )
}
