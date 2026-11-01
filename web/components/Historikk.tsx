import Info from '@/components/Info'
import Ukerutenett from '@/components/Ukerutenett'
import type { Observasjoner, Status, TidligereVarsel, Time } from '@/lib/api'
import { delIDager, lagUkeRad, oslo, plussDager } from '@/lib/dager'

type Obs = Observasjoner['observasjoner'][number]

// Siste 7 døgn: hva modellen mener har skjedd på veggen (kjørt i etterkant på været slik det ble),
// eller hva varselet sa dagen før, med klatrernes meldinger. Så hver klatrer kan sjekke selv.
export default function Historikk({ timer, naMs, tidligere, obs }: {
  timer: Time[] // historikken fra varselet (timer før nå)
  naMs: number
  tidligere: TidligereVarsel[] // varslet dagen før, fra arkivet
  obs: Obs[]
}) {
  const fortid = timer.filter((t) => Date.parse(t.tid) <= naMs)
  if (!fortid.length) return null
  const iDag = oslo(naMs).dato
  const varslet = new Map<number, Status>(tidligere.map((v) => [Date.parse(v.tid), v.status]))
  const rader = delIDager(fortid)
    .filter((d) => d.dato >= plussDager(iDag, -6))
    .map((d) => lagUkeRad(d, { iDag, naMs, varslet, meldinger: obs }))
    .reverse() // i dag øverst, så går det bakover

  return (
    <section className="kort p-sm sm:p-md">
      <div className="flex items-center gap-xs">
        <h2 className="seksjon">Siste 7 døgn</h2>
        <Info>
          {tidligere.length > 0
            ? '«Slik det ble» er modellen kjørt i etterkant på været som faktisk kom. «Slik det ble varslet» er det varselet sa dagen før.'
            : 'Modellen kjørt i etterkant på været som faktisk kom.'}
        </Info>
      </div>
      <div className="mt-sm">
        <Ukerutenett rader={rader} bryter={tidligere.length > 0} />
      </div>
    </section>
  )
}

