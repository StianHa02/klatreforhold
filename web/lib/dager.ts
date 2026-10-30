// Dag for dag: timene delt i døgn i norsk tid, til dagboksene (Nå, I morgen, +2, +3, +4) og
// ukerutenettene «Neste 4 døgn» og «Siste 7 døgn». Rene funksjoner uten nett (tests/dager.test.mts).
import type { Observasjoner, Status, Time, Varsel } from './api'

export const REGN_MM = 0.2 // mm/t som teller som regn
const OPPHOLD_T = 2 // timer uten regn som fortsatt regnes som samme byge
export const SKALA_MM = 2 // fast skala i alle grafer: regn i mm/t og vann på veggen i mm
export const KLATRE_FRA = 8 // klatretimer: timene som starter kl 08 til og med kl 20 (kl 08–21)
export const KLATRE_TIL = 21
const MIN_VINDU_T = 3 // så mange timer på rad må det være tørt for at dagen regnes som klatrbar
const SIKKER_T = 60 // MET Nordic rekker ca. 2.5 døgn fram; lenger fram er det ECMWF og mer usikkert

export const STATUS_TEKST: Record<Status, string> = { tort: 'Tørt', fuktig: 'Fuktig', vatt: 'Vått' }
export const BOKSTAV: Record<Status, string> = { tort: 'T', fuktig: 'F', vatt: 'V' }

const deler = new Intl.DateTimeFormat('en-CA', {
  timeZone: 'Europe/Oslo', year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', hourCycle: 'h23',
})

/** Dato (YYYY-MM-DD), time (0–23) og minutt i norsk tid. */
export function oslo(ms: number): { dato: string; time: number; minutt: number } {
  const p = Object.fromEntries(deler.formatToParts(new Date(ms)).map((x) => [x.type, x.value]))
  return { dato: `${p.year}-${p.month}-${p.day}`, time: Number(p.hour) % 24, minutt: Number(p.minute) }
}

/** Starten av timen; tidsstempelet i varselet er slutten av timen (nedbør og stråling gjelder timen før). */
export const startAv = (t: { tid: string }) => Date.parse(t.tid) - 3600e3
export const pad = (h: number) => String(h).padStart(2, '0')
export const plussDager = (dato: string, n: number) =>
  new Date(Date.parse(`${dato}T12:00:00Z`) + n * 864e5).toISOString().slice(0, 10)

/** «I dag», «I morgen», «I går» eller f.eks. «lør 31.». */
export function dagNavn(dato: string, iDag: string): string {
  if (dato === iDag) return 'I dag'
  if (dato === plussDager(iDag, 1)) return 'I morgen'
  if (dato === plussDager(iDag, -1)) return 'I går'
  const t = new Date(`${dato}T12:00:00Z`).toLocaleDateString('nb-NO', { weekday: 'short', day: 'numeric', timeZone: 'UTC' })
  return `${t.replace(/\./g, '')}.`
}

/** F.eks. «lørdag 31. oktober», til skjermlesere og verktøytips. */
export const dagLang = (dato: string) =>
  new Date(`${dato}T12:00:00Z`).toLocaleDateString('nb-NO', { weekday: 'long', day: 'numeric', month: 'long', timeZone: 'UTC' })

const K16 = ['N', 'NNØ', 'NØ', 'ØNØ', 'Ø', 'ØSØ', 'SØ', 'SSØ', 'S', 'SSV', 'SV', 'VSV', 'V', 'VNV', 'NV', 'NNV']
/** Kompassretning for grader (0 = nord), med 16 eller 8 streker. */
export function kompass(grader: number, streker: 8 | 16 = 16): string {
  const i = Math.round((((grader % 360) + 360) % 360) / (360 / streker)) % streker
  return streker === 16 ? K16[i] : K16[i * 2]
}

export type Dag = { dato: string; timer: (Time | null)[] } // 24 plasser, én per time (starttid i norsk tid)

/** Deler timene i døgn i norsk tid. Når sommertiden slutter kommer timen 02–03 to ganger: de slås sammen
 *  (regn summeres, siste status gjelder). Når den starter blir plassen for kl 02 stående tom. */
export function delIDager(timer: Time[]): Dag[] {
  const dager = new Map<string, (Time | null)[]>()
  for (const t of [...timer].sort((a, b) => Date.parse(a.tid) - Date.parse(b.tid))) {
    const { dato, time } = oslo(startAv(t))
    const rad = dager.get(dato) ?? Array<Time | null>(24).fill(null)
    const har = rad[time]
    rad[time] = har
      ? {
          ...t,
          nedbor_mm: har.nedbor_mm + t.nedbor_mm,
          regn_mot_veggen_mm: har.regn_mot_veggen_mm + t.regn_mot_veggen_mm,
          sol_pa_veggen: har.sol_pa_veggen || t.sol_pa_veggen,
        }
      : t
    dager.set(dato, rad)
  }
  return [...dager.entries()].sort(([a], [b]) => a.localeCompare(b)).map(([dato, timer]) => ({ dato, timer }))
}

/** Lengste sammenhengende løp av timer der `ok(status)` gjelder, innenfor klatretimene. `til` er sluttklokka. */
export function lengsteLop(timer: (Time | null)[], ok: (s: Status) => boolean): { fra: number; til: number } | null {
  let best: { fra: number; til: number } | null = null
  let fra = -1
  for (let h = KLATRE_FRA; h <= KLATRE_TIL; h++) {
    const t = h < KLATRE_TIL ? timer[h] : null
    if (t && ok(t.status)) {
      if (fra < 0) fra = h
    } else if (fra >= 0) {
      if (!best || h - fra > best.til - best.fra) best = { fra, til: h }
      fra = -1
    }
  }
  return best
}

export type DagSum = {
  status: Status | null // null: ingen timer med data i klatretimene
  tekst: string
  regn_mm: number
  soltimer: number
  vind: number | null // snitt m/s
  usikker: boolean
}

/** Oppsummerer et døgn for planlegging: finnes det et tørt vindu i klatretimene (kl 08–21)? */
export function oppsummerDag(dag: Dag, naMs: number): DagSum {
  const alle = dag.timer.filter((t): t is Time => t !== null)
  const klatre = dag.timer.slice(KLATRE_FRA, KLATRE_TIL).filter((t): t is Time => t !== null)
  const regn_mm = alle.reduce((s, t) => s + t.nedbor_mm, 0)
  const felles = {
    regn_mm,
    soltimer: alle.filter((t) => t.sol_pa_veggen).length,
    vind: alle.length ? alle.reduce((s, t) => s + t.vind_ms, 0) / alle.length : null,
    usikker: klatre.length > 0 && startAv(klatre[0]) - naMs > SIKKER_T * 3600e3,
  }
  if (!klatre.length) return { ...felles, status: null, tekst: '–' }
  const tort = lengsteLop(dag.timer, (s) => s === 'tort')
  if (tort && tort.til - tort.fra >= Math.min(MIN_VINDU_T, klatre.length)) {
    const hele = tort.fra === KLATRE_FRA && tort.til === KLATRE_TIL
    return { ...felles, status: 'tort', tekst: hele ? 'hele dagen' : `kl ${pad(tort.fra)}–${pad(tort.til)}` }
  }
  const nesten = lengsteLop(dag.timer, (s) => s === 'tort' || s === 'fuktig')
  if (nesten && nesten.til - nesten.fra >= Math.min(MIN_VINDU_T, klatre.length)) {
    return { ...felles, status: 'fuktig', tekst: `beste kl ${pad(nesten.fra)}–${pad(nesten.til)}` }
  }
  // is/snø vises som vått, men dagteksten sier hvorfor
  return { ...felles, status: 'vatt', tekst: klatre.some((t) => t.is_sno) ? 'is/snø' : regn_mm >= 0.1 ? `${regn_mm.toFixed(1)} mm regn` : 'ingen tørre timer' }
}

export type DagBoks = { nokkel: string; navn: string; status: Status | null; tekst: string; usikker: boolean }

/** Når skjer `tid` sett fra i dag: «kl 14» eller «i morgen kl 09» (starten av timen). */
function naar(tid: string, iDag: string): string {
  const o = oslo(Date.parse(tid) - 3600e3)
  return o.dato === iDag ? `kl ${pad(o.time)}` : o.dato === plussDager(iDag, 1) ? `i morgen kl ${pad(o.time)}` : `${dagNavn(o.dato, iDag)} kl ${pad(o.time)}`
}

/** Fem bokser: Nå, I morgen og tre dager til. Dager uten varsel får «–». */
export function dagBokser(v: Varsel, naMs: number): DagBoks[] {
  const iDag = oslo(naMs).dato
  const s = v.sammendrag
  const na: DagBoks = {
    nokkel: 'na',
    navn: 'Nå',
    status: s.status_na ?? null,
    tekst: s.tort_na
      ? s.neste_vate_time ? `vått fra ${naar(s.neste_vate_time, iDag)}` : 'tørt neste døgn'
      : s.neste_torre_time ? `tørt fra ${naar(s.neste_torre_time, iDag)}` : 'ikke tørt neste døgn',
    usikker: false,
  }
  const dager = delIDager(v.framover ?? v.timer)
  return [na, ...[1, 2, 3, 4].map((n) => {
    const dato = plussDager(iDag, n)
    const dag = dager.find((d) => d.dato === dato)
    const sum = dag ? oppsummerDag(dag, naMs) : null
    return { nokkel: dato, navn: dagNavn(dato, iDag), status: sum?.status ?? null, tekst: sum?.tekst ?? '–', usikker: sum?.usikker ?? false }
  })]
}

export type SisteRegn = {
  start: string // tidsstempel for første regntime (slutten av timen)
  slutt: string
  mm: number
  timer_siden: number
  tort_igjen: string | null // første tørre time etter regnet (slutten av timen), hvis det har skjedd
}

/** Siste regnbyge før `naMs`, og når veggen var tørr igjen ifølge modellen. Null hvis det ikke har regnet. */
export function sisteRegn(timer: Time[], naMs: number): SisteRegn | null {
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
  const tort = for_.slice(slutt + 1).find((t) => t.tort)
  return {
    start: for_[start].tid,
    slutt: for_[slutt].tid,
    mm: for_.slice(start, slutt + 1).reduce((s, t) => s + t.nedbor_mm, 0),
    timer_siden: Math.round((naMs - Date.parse(for_[slutt].tid)) / 3600e3),
    tort_igjen: tort?.tid ?? null,
  }
}

/** Sammenhengende løp av like verdier over plassene (null = ingen data). */
export function biter<T>(verdier: (T | null)[]): { v: T | null; fra: number; til: number }[] {
  const ut: { v: T | null; fra: number; til: number }[] = []
  verdier.forEach((v, i) => {
    const siste = ut[ut.length - 1]
    if (siste && siste.v === v) siste.til = i + 1
    else ut.push({ v, fra: i, til: i + 1 })
  })
  return ut
}

/** Stemmer det klatreren meldte med statusen som vises (tørt mot ikke tørt)? Null uten status. */
export const riktig = (meldt: Status, vist: Status | null | undefined) =>
  vist ? (meldt === 'tort') === (vist === 'tort') : null

/** Modellens status per time, nøkkel «YYYY-MM-DDTHH» (starttid i norsk tid), til tilbakemeldingsskjemaet. */
export function statusPerTime(timer: Time[]): Record<string, Status> {
  const ut: Record<string, Status> = {}
  for (const t of timer) {
    const o = oslo(startAv(t))
    ut[`${o.dato}T${pad(o.time)}`] = t.status
  }
  return ut
}

// ---- ukerutenettet (serialiserbart, så klientkomponenten ikke formaterer datoer selv) ----

export type UkeCelle = { s: Status | null; v: Status | null; regn: number; sol: boolean; tittel: string }
export type UkeMelding = { pos: number; status: Status; etter: boolean | null; for: boolean | null; tekst: string }
export type UkeTabellRad = { kl: string; s: Status; v: Status | null; regn: string; sol: boolean; vind: string; fukt: string }
export type UkeRad = {
  id: string
  navn: string
  lang: string // til skjermlesere
  merknad?: string
  celler: (UkeCelle | null)[]
  sum: { regn: string; sol: string; vind: string }
  na?: number // posisjon for «nå» i timer (0–24)
  meldinger: UkeMelding[]
  tabell: UkeTabellRad[]
}

type Melding = Pick<Observasjoner['observasjoner'][number], 'time' | 'status' | 'kommentar'>

/** Én rad i ukerutenettet. `varslet`: varselet dagen før per tidsstempel (ms). */
export function lagUkeRad(dag: Dag, o: { iDag: string; naMs: number; varslet?: Map<number, Status>; meldinger?: Melding[]; merknad?: string }): UkeRad {
  const lang = dagLang(dag.dato)
  const ts = dag.timer.filter((t): t is Time => t !== null)
  const varslet = (t: Time) => o.varslet?.get(Date.parse(t.tid)) ?? null
  const celler = dag.timer.map((t, h): UkeCelle | null => {
    if (!t) return null
    const v = varslet(t)
    return {
      s: t.status,
      v,
      regn: t.nedbor_mm,
      sol: t.sol_pa_veggen,
      tittel: `${lang} kl ${pad(h)}–${pad((h + 1) % 24)}: ${STATUS_TEKST[t.status]}`
        + (o.varslet ? ` (varslet dagen før: ${v ? STATUS_TEKST[v].toLowerCase() : 'ikke lagret'})` : '')
        + ` · regn ${t.nedbor_mm.toFixed(1)} mm · ${t.sol_pa_veggen ? 'sol på veggen' : 'ikke sol på veggen'}`
        + ` · vind ${t.vind_ms.toFixed(1)} m/s fra ${kompass(t.vindretning, 8)} · luftfuktighet ${Math.round(t.luftfuktighet)} %`,
    }
  })
  const meldinger = (o.meldinger ?? []).flatMap((m): UkeMelding[] => {
    const p = oslo(Date.parse(m.time))
    if (p.dato !== dag.dato) return []
    const c = celler[p.time]
    return [{
      pos: p.time + p.minutt / 60,
      status: m.status,
      etter: riktig(m.status, c?.s),
      for: riktig(m.status, c?.v),
      tekst: `kl ${pad(p.time)}:${pad(p.minutt)} meldte en klatrer ${STATUS_TEKST[m.status].toLowerCase()}${m.kommentar ? `: «${m.kommentar}»` : ''}`,
    }]
  })
  const n = oslo(o.naMs)
  const regn = ts.reduce((s, t) => s + t.nedbor_mm, 0)
  const sol = ts.filter((t) => t.sol_pa_veggen).length
  const vind = ts.length ? ts.reduce((s, t) => s + t.vind_ms, 0) / ts.length : null
  return {
    id: dag.dato,
    navn: dagNavn(dag.dato, o.iDag),
    lang: `${lang}: ${regn >= 0.1 ? `${regn.toFixed(1)} mm regn` : 'ikke regn'}, ${sol} timer sol på veggen`
      + `${vind !== null ? `, snittvind ${Math.round(vind)} m/s` : ''}. Åpne for time for time.`,
    merknad: o.merknad,
    celler,
    sum: { regn: regn >= 0.1 ? regn.toFixed(1) : '–', sol: `${sol} t`, vind: vind !== null ? String(Math.round(vind)) : '–' },
    na: n.dato === dag.dato ? n.time + n.minutt / 60 : undefined,
    meldinger,
    tabell: dag.timer.flatMap((t, h): UkeTabellRad[] => (t ? [{
      kl: pad(h),
      s: t.status,
      v: varslet(t),
      regn: t.nedbor_mm >= 0.05 ? t.nedbor_mm.toFixed(1) : '–',
      sol: t.sol_pa_veggen,
      vind: `${Math.round(t.vind_ms)} ${kompass(t.vindretning, 8)}`,
      fukt: `${Math.round(t.luftfuktighet)} %`,
    }] : [])),
  }
}
