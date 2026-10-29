import type { Felt } from '@/lib/api'

/** Rad med alle feltene, så man kan bytte felt uten å gå via forsiden. Ruller sidelengs på mobil. */
export default function FeltVelger({ felt, slug }: { felt: Felt[]; slug: string }) {
  if (felt.length < 2) return null
  const sortert = [...felt].sort((a, b) => a.navn.localeCompare(b.navn, 'nb'))

  return (
    <nav aria-label="Velg felt" className="-mx-md overflow-x-auto px-md">
      <ul className="flex w-max gap-xs text-sm">
        {sortert.map((f) => {
          const valgt = f.slug === slug
          return (
            <li key={f.slug}>
              <a
                href={`/felt/${f.slug}`}
                aria-current={valgt ? 'page' : undefined}
                className={`focus block whitespace-nowrap rounded-full border px-sm py-[4px] ${
                  valgt
                    ? 'border-text-default bg-text-default text-surface-default'
                    : 'border-border-subtle bg-surface-default hover:border-text-default'
                }`}
              >
                {f.navn}
              </a>
            </li>
          )
        })}
      </ul>
    </nav>
  )
}
