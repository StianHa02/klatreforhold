import { statusFarge, statusTint } from '@/lib/api'
import { type DagBoks, STATUS_TEKST } from '@/lib/dager'

// Fem bokser: Nå, I morgen og tre dager til, farget etter status. Folk planlegger klatring og avtaler
// med partnere opptil fire dager fram. Teksten sier alltid statusen, så fargen er ikke eneste kjennetegn.
// `paFarge`: boksene står på en farget flate (toppen av feltsiden); hvit kant skiller dem fra bakgrunnen.
export default function DagBokser({ bokser, paFarge = false }: { bokser: DagBoks[]; paFarge?: boolean }) {
  return (
    <ol className="grid grid-cols-5 gap-xs" aria-label="Varsel dag for dag">
      {bokser.map((b) => (
        <li
          key={b.nokkel}
          className={`flex min-w-0 flex-col overflow-hidden rounded-lg text-center ${paFarge ? 'border-2 border-white shadow-sm' : 'border border-border-subtle'} ${b.status ? statusTint[b.status] : 'bg-surface-default'}`}
        >
          <span aria-hidden className={`h-[4px] shrink-0 ${b.status ? statusFarge[b.status] : 'bg-surface-tinted'}`} />
          <span className="truncate px-[2px] pt-[4px] text-[11px] leading-tight text-text-subtle">{b.navn}</span>
          <span className="text-sm font-medium leading-snug">{b.status ? STATUS_TEKST[b.status] : '–'}</span>
          <span className="px-[2px] pb-[6px] text-[10px] leading-tight text-text-tinted">
            {b.status ? b.tekst : 'ingen data'}
            {b.usikker && <span className="block text-text-subtle">usikkert</span>}
          </span>
        </li>
      ))}
    </ol>
  )
}
