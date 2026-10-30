import Info from '@/components/Info'
import Ukerutenett from '@/components/Ukerutenett'
import type { Time } from '@/lib/api'
import { delIDager, lagUkeRad, oppsummerDag, oslo, plussDager } from '@/lib/dager'

// Neste 4 døgn i samme rutenett som historikken: når på dagen blir det tørt, når kommer regnet,
// når står sola på veggen. Folk planlegger og avtaler med partnere opptil fire dager fram.
export default function NesteDogn({ timer, naMs }: { timer: Time[]; naMs: number }) {
  const iDag = oslo(naMs).dato
  const dager = delIDager(timer.filter((t) => Date.parse(t.tid) > naMs)).filter((d) => d.dato <= plussDager(iDag, 4))
  if (!dager.length) return null
  const summer = dager.map((d) => oppsummerDag(d, naMs))
  const rader = dager.map((d, i) => lagUkeRad(d, { iDag, naMs, merknad: summer[i].usikker ? 'usikkert' : undefined }))
  return (
    <section className="kort p-md">
      <div className="flex items-center gap-xs">
        <h2 className="seksjon">Neste 4 døgn</h2>
        <Info>Lenger enn 2–3 døgn fram er varselet mer usikkert.</Info>
      </div>
      <div className="mt-sm">
        <Ukerutenett rader={rader} />
      </div>
    </section>
  )
}
