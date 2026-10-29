import DagBokser from '@/components/DagBokser'
import { type Varsel, statusFarge, statusTint } from '@/lib/api'
import type { DagBoks } from '@/lib/dager'

// Status nå, grunnene, og dagboksene (Nå, I morgen og tre dager til) under.
export default function StatusHero({ varsel, bokser }: { varsel: Varsel; bokser: DagBoks[] }) {
  const s = varsel.sammendrag
  return (
    <section className={`rounded-xl border border-border-subtle p-md ${statusTint[s.status_na]}`}>
      <div className="flex items-center gap-md">
        <span className={`inline-block h-lg w-lg shrink-0 rounded-full ${statusFarge[s.status_na]}`} aria-hidden />
        <div>
          <p className="text-sm text-text-subtle">Nå på {varsel.felt.navn}</p>
          <p className="font-mabry text-2xl leading-tight">{s.status_na_tekst}</p>
        </div>
      </div>
      {s.grunner_na.length > 0 && (
        <ul className="mt-sm list-disc pl-lg text-sm text-text-tinted">
          {s.grunner_na.map((g) => (
            <li key={g}>{g}</li>
          ))}
        </ul>
      )}
      <div className="mt-md">
        <DagBokser bokser={bokser} paFarge />
      </div>
    </section>
  )
}
