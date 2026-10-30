import { statusFarge, statusTint } from '@/lib/api'
import { type DagBoks, STATUS_TEKST } from '@/lib/dager'

// Fem bokser: Nå, I morgen og tre dager til, farget etter status. Folk planlegger klatring og avtaler
// med partnere opptil fire dager fram. Teksten sier alltid statusen, så fargen er ikke eneste kjennetegn.
// `paFarge`: boksene står på en farget flate (toppen av feltsiden); hvit kant skiller dem fra bakgrunnen.
// `skjulNaMobil`: «Nå» står allerede med stor skrift over boksene, så på mobil vises bare de fire dagene,
// og de får plass til litt større tekst.
export default function DagBokser({ bokser, paFarge = false, skjulNaMobil = false }: {
  bokser: DagBoks[]
  paFarge?: boolean
  skjulNaMobil?: boolean
}) {
  const liten = skjulNaMobil ? 'text-xs sm:text-[11px]' : 'text-[11px]'
  const minst = skjulNaMobil ? 'text-[11px] sm:text-[10px]' : 'text-[10px]'
  return (
    <ol className={`grid gap-xs ${skjulNaMobil ? 'grid-cols-4 sm:grid-cols-5' : 'grid-cols-5'}`} aria-label="Varsel dag for dag">
      {bokser.map((b, i) => (
        <li
          key={b.nokkel}
          className={`flex min-w-0 flex-col overflow-hidden text-center ${skjulNaMobil && i === 0 ? 'max-sm:hidden' : ''} ${paFarge ? 'border-2 border-white shadow-sm' : 'border border-border-subtle'} ${b.status ? statusTint[b.status] : 'bg-surface-default'}`}
        >
          <span aria-hidden className={`h-[4px] shrink-0 ${b.status ? statusFarge[b.status] : 'bg-surface-tinted'}`} />
          <span className={`truncate px-[2px] pt-[4px] leading-tight text-text-subtle ${liten}`}>{b.navn}</span>
          <span className="text-sm font-medium leading-snug">{b.status ? STATUS_TEKST[b.status] : '–'}</span>
          <span className={`px-[2px] pb-[6px] leading-tight text-text-tinted ${minst}`}>
            {b.status ? b.tekst : 'ingen data'}
            {b.usikker && <span className="block text-text-subtle">usikkert</span>}
          </span>
        </li>
      ))}
    </ol>
  )
}
