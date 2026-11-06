'use client'

import { type ReactNode, useId, useState } from 'react'
import { ANDRE, grupperFelt, normaliser } from '@/lib/omraader'

export type Visning = 'varsel' | 'liste'
export type FeltInfo = { slug: string; navn: string; omraade: string | null }

const VALG: { verdi: Visning; tekst: string }[] = [
  { verdi: 'varsel', tekst: 'Med varsel' },
  { verdi: 'liste', tekst: 'Bare felt' },
]

// Forsiden: søk på feltnavn, filter på område og valg mellom varsel dag for dag eller bare navn.
// Kortene tegnes på serveren (varselet er stort) og sendes inn per slug; her velges bare hvilke som vises.
// Visningsvalget lagres i en informasjonskapsel, så serveren tegner riktig visning neste gang (ingen blinking).
export default function FeltOversikt({
  felt,
  start,
  varsel,
  liste,
}: {
  felt: FeltInfo[]
  start: Visning
  varsel: Record<string, ReactNode>
  liste: Record<string, ReactNode>
}) {
  const [visning, setVisning] = useState<Visning>(start)
  const [sok, setSok] = useState('')
  const [omraade, setOmraade] = useState('')
  const sokId = useId()
  const omraadeId = useId()

  function velg(v: Visning) {
    setVisning(v)
    document.cookie = `visning=${v}; path=/; max-age=31536000; samesite=lax`
  }

  const alleGrupper = grupperFelt(felt)
  const q = normaliser(sok.trim())
  const grupper = alleGrupper
    .filter((g) => !omraade || g.omraade === omraade)
    .map((g) => ({ ...g, felt: q ? g.felt.filter((f) => normaliser(f.navn).includes(q)) : g.felt }))
    .filter((g) => g.felt.length > 0)
  const antall = grupper.reduce((n, g) => n + g.felt.length, 0)
  const kort = visning === 'varsel' ? varsel : liste

  return (
    <div className="flex flex-col gap-sm">
      <div className="flex flex-col gap-sm sm:flex-row sm:items-end">
        <label htmlFor={sokId} className="flex flex-1 flex-col gap-xs text-sm">
          <span className="text-text-subtle">Søk etter felt</span>
          <input
            id={sokId}
            type="search"
            value={sok}
            onChange={(e) => setSok(e.target.value)}
            placeholder="Feltnavn"
            autoComplete="off"
            className="focus-box border-2 border-border-default bg-surface-default px-sm py-xs"
          />
        </label>
        <label htmlFor={omraadeId} className="flex flex-col gap-xs text-sm sm:w-[14rem]">
          <span className="text-text-subtle">Område</span>
          <select
            id={omraadeId}
            value={omraade}
            onChange={(e) => setOmraade(e.target.value)}
            className="focus-box border-2 border-border-default bg-surface-default px-sm py-xs"
          >
            <option value="">Alle områder</option>
            {alleGrupper.map((g) => (
              <option key={g.omraade} value={g.omraade}>
                {g.omraade} ({g.felt.length})
              </option>
            ))}
          </select>
        </label>
      </div>
      <div role="group" aria-label="Visning" className="flex border-b-2 border-border-subtle">
        {VALG.map((o) => (
          <button key={o.verdi} type="button" aria-pressed={visning === o.verdi} onClick={() => velg(o.verdi)} className="fane">
            {o.tekst}
          </button>
        ))}
      </div>
      <p className="sr-only" aria-live="polite">
        {antall === 1 ? '1 felt' : `${antall} felt`}
      </p>
      {grupper.length === 0 ? (
        <p className="kort p-md text-sm text-text-subtle">Ingen felt passer til «{sok.trim()}».</p>
      ) : (
        grupper.map((g) => (
          <section key={g.omraade} aria-labelledby={`omraade-${g.omraade}`} className="flex flex-col gap-sm">
            <h2 id={`omraade-${g.omraade}`} className="seksjon pt-sm">
              {g.omraade === ANDRE ? 'Andre felt' : g.omraade}
            </h2>
            <ul className="flex flex-col gap-sm">
              {g.felt.map((f) => (
                <li key={f.slug}>{kort[f.slug]}</li>
              ))}
            </ul>
          </section>
        ))
      )}
    </div>
  )
}
