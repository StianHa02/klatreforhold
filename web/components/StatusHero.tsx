import DagBokser from '@/components/DagBokser'
import { type Varsel, statusFarge, statusTint } from '@/lib/api'
import { type DagBoks, STATUS_TEKST } from '@/lib/dager'

const MAKS_GRUNNER = 2 // resten står i verktøytipsene i timestripen

// Status nå med stor skrift, hva som skjer videre i dag, de viktigste grunnene, og dagboksene under.
// Lys statusfarge som bakgrunn og en sterk strek til venstre.
export default function StatusHero({ varsel, bokser }: { varsel: Varsel; bokser: DagBoks[] }) {
  const s = varsel.sammendrag
  const na = bokser[0]
  return (
    <section aria-label="Status nå" className={`relative border border-border-subtle p-sm pl-[calc(0.5rem+6px)] sm:p-md sm:pl-[calc(1rem+6px)] ${statusTint[s.status_na]}`}>
      <span aria-hidden className={`absolute inset-y-0 left-0 w-[6px] ${statusFarge[s.status_na]}`} />
      <p className="font-mabry text-[40px] leading-none">{STATUS_TEKST[s.status_na]}</p>
      {na?.tekst && <p className="mt-xs text-lg first-letter:uppercase">{na.tekst}</p>}
      {s.grunner_na.length > 0 && (
        <ul className="mt-sm flex flex-col gap-[2px] text-sm text-text-tinted">
          {s.grunner_na.slice(0, MAKS_GRUNNER).map((g) => (
            <li key={g}>{g}</li>
          ))}
        </ul>
      )}
      <div className="mt-md">
        <DagBokser bokser={bokser} paFarge skjulNaMobil />
      </div>
    </section>
  )
}
