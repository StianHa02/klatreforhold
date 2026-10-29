'use client'

import { type ReactNode, useState } from 'react'

export type Visning = 'varsel' | 'liste'

const VALG: { verdi: Visning; tekst: string }[] = [
  { verdi: 'varsel', tekst: 'Med varsel' },
  { verdi: 'liste', tekst: 'Bare felt' },
]

// Forsiden kan vise feltene med varsel dag for dag, eller bare som en liste med navn.
// Valget lagres i en informasjonskapsel, så serveren tegner riktig visning neste gang (ingen blinking).
export default function VisningsBryter({ start, varsel, liste }: { start: Visning; varsel: ReactNode; liste: ReactNode }) {
  const [visning, setVisning] = useState<Visning>(start)

  function velg(v: Visning) {
    setVisning(v)
    document.cookie = `visning=${v}; path=/; max-age=31536000; samesite=lax`
  }

  return (
    <div className="flex flex-col gap-sm">
      {/* Samme knappestil som Knapp i Ukerutenett og Chip i tilbakemeldingsskjemaet */}
      <div role="group" aria-label="Visning" className="flex gap-xs">
        {VALG.map((o) => (
          <button
            key={o.verdi}
            type="button"
            aria-pressed={visning === o.verdi}
            onClick={() => velg(o.verdi)}
            className={`focus cursor-pointer rounded-lg border-2 px-sm py-xs text-sm transition ${
              visning === o.verdi
                ? 'border-accent-border-default bg-accent-surface-default text-accent-text-default'
                : 'border-border-default bg-surface-default hover:bg-surface-tinted'
            }`}
          >
            {o.tekst}
          </button>
        ))}
      </div>
      {visning === 'varsel' ? varsel : liste}
    </div>
  )
}
