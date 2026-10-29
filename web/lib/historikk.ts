// Oppsummeringer av historikken på feltsiden: siste regnbyge og én rad per døgn.
// Rene funksjoner uten nett, så de kan testes (tests/historikk.test.mts).
import type { Status, Time } from './api'

const REGN_MM = 0.2 // mm/t som teller som regn
const OPPHOLD_T = 2 // timer uten regn som fortsatt regnes som samme byge

const osloDag = new Intl.DateTimeFormat('en-CA', { timeZone: 'Europe/Oslo', year: 'numeric', month: '2-digit', day: '2-digit' })
const osloTime = new Intl.DateTimeFormat('en-GB', { timeZone: 'Europe/Oslo', hour: '2-digit', hourCycle: 'h23' })
export const dagNokkel = (iso: string) => osloDag.format(new Date(iso))
export const timeIOslo = (iso: string) => Number(osloTime.format(new Date(iso)))

export type SisteRegn = {
  start: string // tidsstempel for første regntime (slutten av timen)
  slutt: string
  mm: number
  timer_siden: number
  soltimer_siden: number
  vind_siden: number | null // snitt m/s
}

/** Siste regnbyge før `na`, og hvor mye sol og vind veggen har fått siden. Null hvis det ikke har regnet. */
export function sisteRegn(timer: Time[], na: string): SisteRegn | null {
  const naMs = Date.parse(na)
  const for_ = timer.filter((t) => Date.parse(t.tid) <= naMs)
  let slutt = -1
  for (let i = for_.length - 1; i >= 0; i--) if (for_[i].nedbor_mm >= REGN_MM) { slutt = i; break }
  if (slutt < 0) return null
  let start = slutt
  let opphold = 0
  for (let i = slutt - 1; i >= 0; i--) {
    if (for_[i].nedbor_mm >= REGN_MM) { start = i; opphold = 0 }
    else if (++opphold > OPPHOLD_T) break
  }
  const byge = for_.slice(start, slutt + 1)
  const etter = for_.slice(slutt + 1)
  return {
    start: for_[start].tid,
    slutt: for_[slutt].tid,
    mm: byge.reduce((s, t) => s + t.nedbor_mm, 0),
    timer_siden: Math.round((naMs - Date.parse(for_[slutt].tid)) / 3600e3),
    soltimer_siden: etter.filter((t) => t.sol_pa_veggen).length,
    vind_siden: etter.length ? etter.reduce((s, t) => s + t.vind_ms, 0) / etter.length : null,
  }
}

export type Dogn = {
  dag: string // YYYY-MM-DD i norsk tid
  forste: string // første tidsstempel i døgnet
  regn_mm: number
  soltimer: number
  maks_vind: number
  status: Status // vanligste status kl 08-20, når folk klatrer
}

const ALVOR: Status[] = ['tort', 'fuktig', 'vatt', 'is']

/** Én rad per døgn (norsk tid). Ved likt antall vinner den våteste statusen. */
export function perDag(timer: Time[]): Dogn[] {
  const grupper = new Map<string, Time[]>()
  for (const t of timer) {
    const k = dagNokkel(t.tid)
    grupper.set(k, [...(grupper.get(k) ?? []), t])
  }
  return [...grupper.entries()].map(([dag, ts]) => {
    const dagtid = ts.filter((t) => timeIOslo(t.tid) >= 8 && timeIOslo(t.tid) <= 20)
    const telling = new Map<Status, number>()
    for (const t of dagtid.length ? dagtid : ts) telling.set(t.status, (telling.get(t.status) ?? 0) + 1)
    const status = [...telling.entries()].sort((a, b) => b[1] - a[1] || ALVOR.indexOf(b[0]) - ALVOR.indexOf(a[0]))[0][0]
    return {
      dag,
      forste: ts[0].tid,
      regn_mm: ts.reduce((s, t) => s + t.nedbor_mm, 0),
      soltimer: ts.filter((t) => t.sol_pa_veggen).length,
      maks_vind: Math.max(...ts.map((t) => t.vind_ms)),
      status,
    }
  })
}

/** Stemte varselet med tilbakemeldingene? Teller bare de som er vurdert (har `riktig`). */
export function treff(obs: { riktig: number | '' }[]): { riktige: number; vurdert: number } {
  const vurdert = obs.filter((o) => o.riktig !== '')
  return { riktige: vurdert.filter((o) => Number(o.riktig) === 1).length, vurdert: vurdert.length }
}
