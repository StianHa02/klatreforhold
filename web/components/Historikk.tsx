import Ukerutenett from '@/components/Ukerutenett'
import type { Observasjoner, Status, TidligereVarsel, Time } from '@/lib/api'
import { type SisteRegn, dagNavn, delIDager, lagUkeRad, oslo, pad, plussDager, sisteRegn } from '@/lib/dager'

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

  const meldinger = rader.flatMap((r) => r.meldinger)
  const telle = (felt: 'etter' | 'for') => {
    const vurdert = meldinger.filter((m) => m[felt] !== null)
    return { ok: vurdert.filter((m) => m[felt]).length, n: vurdert.length }
  }
  const e = telle('etter')
  const f = telle('for')
  const treff = meldinger.length
    ? {
        etter: `Stemte med ${e.ok} av ${e.n} tilbakemeldinger.`,
        for: f.n
          ? `Stemte med ${f.ok} av ${f.n} tilbakemeldinger${meldinger.length > f.n ? ` (${meldinger.length - f.n} uten lagret varsel)` : ''}.`
          : 'Ingen lagrede varsler for disse tilbakemeldingene.',
      }
    : undefined

  return (
    <section className="kort p-md">
      <h2 className="seksjon">Siste 7 døgn</h2>
      <p className="byline">Hvordan veggen har vært, med klatrernes meldinger</p>
      <p className="mt-sm">{regnTekst(sisteRegn(fortid, naMs), iDag)}</p>
      <div className="mt-sm">
        <Ukerutenett
          rader={rader}
          bryter={tidligere.length > 0}
          tekster={{
            etter: 'Modellen kjørt på været slik det faktisk ble.',
            for: 'Varselet slik det så ut ca. 24 timer før. Grått: ikke lagret.',
          }}
          treff={treff}
        />
      </div>
    </section>
  )
}

/** «i dag», «i går» eller «ons 28.» */
const dagOrd = (dato: string, iDag: string) => {
  const n = dagNavn(dato, iDag)
  return n.startsWith('I ') ? n.toLowerCase() : n
}

function regnTekst(r: SisteRegn | null, iDag: string): string {
  if (!r) return 'Ingen regn de siste 7 døgnene.'
  if (r.timer_siden <= 0) return `Det regner nå (${r.mm.toFixed(1)} mm så langt).`
  const fra = oslo(Date.parse(r.start) - 3600e3)
  const til = oslo(Date.parse(r.slutt))
  const byge = `Sist regn ${dagOrd(fra.dato, iDag)} kl ${pad(fra.time)}–${pad(til.time)} · ${r.mm.toFixed(1)} mm`
  if (!r.tort_igjen) return `${byge} · ikke tørt igjen ennå (${r.timer_siden} t siden)`
  const torrStart = Date.parse(r.tort_igjen) - 3600e3
  const t = oslo(torrStart)
  const timer = Math.round((torrStart - Date.parse(r.slutt)) / 3600e3)
  return `${byge} · tørt igjen ${timer > 0 ? `etter ${timer} t` : 'med en gang'} (${dagOrd(t.dato, iDag)} kl ${pad(t.time)})`
}
