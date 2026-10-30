import Ukerutenett from '@/components/Ukerutenett'
import type { Time } from '@/lib/api'
import { dagNavn, delIDager, lagUkeRad, oppsummerDag, oslo, plussDager } from '@/lib/dager'

// Neste 4 døgn i samme rutenett som historikken: når på dagen blir det tørt, når kommer regnet,
// når står sola på veggen. Folk planlegger og avtaler med partnere opptil fire dager fram.
export default function NesteDogn({ timer, naMs }: { timer: Time[]; naMs: number }) {
  const iDag = oslo(naMs).dato
  const dager = delIDager(timer.filter((t) => Date.parse(t.tid) > naMs)).filter((d) => d.dato <= plussDager(iDag, 4))
  if (!dager.length) return null
  const summer = dager.map((d) => oppsummerDag(d, naMs))
  const rader = dager.map((d, i) => lagUkeRad(d, { iDag, naMs, merknad: summer[i].usikker ? 'usikkert' : undefined }))
  const forsteTorre = dager.findIndex((_, i) => summer[i].status === 'tort')
  const navn = forsteTorre >= 0 ? dagNavn(dager[forsteTorre].dato, iDag) : ''
  return (
    <section className="kort p-md">
      <h2 className="seksjon">Neste 4 døgn</h2>
      <p className="byline">Varselet framover, time for time</p>
      <p className="mt-sm">
        {forsteTorre >= 0
          ? `Neste tørre vindu: ${navn.startsWith('I ') ? navn.toLowerCase() : navn} ${summer[forsteTorre].tekst}${summer[forsteTorre].usikker ? ' (usikkert)' : ''}.`
          : 'Ingen tørre vinduer på minst tre timer (kl 08–21) de neste fire dagene.'}
      </p>
      <div className="mt-sm">
        <Ukerutenett
          rader={rader}
          tekster={{ etter: 'Lenger enn 2–3 døgn fram er varselet mer usikkert.' }}
        />
      </div>
    </section>
  )
}
