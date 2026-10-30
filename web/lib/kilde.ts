// Datakilde for nettsiden. To moduser:
//  - Supabase (produksjon): SUPABASE_URL + SUPABASE_SERVICE_ROLE_KEY er satt. Leser siste varsel som
//    timesjobben har skrevet, og lagrer observasjoner. Nøkkelen brukes bare på serveren.
//  - Python-API (lokal utvikling): KLATREFORHOLD_API_URL, standard http://localhost:8000
//    Brukes også med Supabase-nøkler hvis KLATREFORHOLD_DATAKILDE=api (Docker), så varselet regnes ut
//    på nytt med koden du har lokalt. Arkivet og statistikken leses fortsatt fra Supabase når nøklene finnes.
import type { Felt, Observasjoner, Status, TidligereVarsel, Time, Varsel } from './api'

const SB_URL = process.env.SUPABASE_URL
const SB_KEY = process.env.SUPABASE_SERVICE_ROLE_KEY
const API_URL = process.env.KLATREFORHOLD_API_URL ?? 'http://localhost:8000'
const harSupabase = Boolean(SB_URL && SB_KEY)
export const brukerSupabase = harSupabase && process.env.KLATREFORHOLD_DATAKILDE !== 'api'

async function sb<T>(path: string, init: RequestInit = {}): Promise<T> {
  const res = await fetch(`${SB_URL}/rest/v1/${path}`, {
    ...init,
    cache: 'no-store',
    headers: {
      apikey: SB_KEY!,
      Authorization: `Bearer ${SB_KEY}`,
      'Content-Type': 'application/json',
      ...(init.headers ?? {}),
    },
  })
  if (!res.ok) throw new Error(`Supabase ${path}: ${res.status} ${await res.text()}`)
  const text = await res.text()
  return (text ? JSON.parse(text) : null) as T
}

async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, { ...init, cache: 'no-store' })
  if (!res.ok) throw new Error(`API ${path}: ${res.status} ${await res.text()}`)
  return (await res.json()) as T
}

// ---- varsel ----

/** Klipper det lagrede varselet (laget for opptil en time siden) til "nå + 24 t" og 12 t bakover.
 *  `framover` og `historikk` får alle timene fra og før nå (dagboksene og ukerutenettene). */
export function vinduFraNa(v: Varsel, na: Date = new Date(), timer = 24): Varsel {
  const naTime = new Date(na)
  naTime.setUTCMinutes(0, 0, 0)
  if (naTime.getTime() < na.getTime()) naTime.setUTCHours(naTime.getUTCHours() + 1) // tidsstempel = slutten av timen
  const alle = [...v.siste_timer, ...v.timer].sort((a, b) => Date.parse(a.tid) - Date.parse(b.tid))
  const framover = alle.filter((t) => Date.parse(t.tid) >= naTime.getTime())
  const fram = framover.slice(0, timer + 1)
  const tidligere = alle.filter((t) => Date.parse(t.tid) < naTime.getTime())
  const bak = tidligere.slice(-12)
  if (fram.length === 0) return { ...v, utdatert: true }
  const torre = fram.filter((t) => t.tort)
  const vate = fram.filter((t) => !t.tort)
  const forste = fram[0]
  return {
    ...v,
    na: forste.tid,
    timer: fram,
    siste_timer: bak,
    historikk: tidligere,
    framover,
    utdatert: na.getTime() - Date.parse(v.na) > 3 * 3600e3, // v.na = timen modellen ble kjørt for
    sammendrag: {
      status_na: forste.status,
      status_na_tekst: forste.status_tekst,
      tort_na: forste.tort,
      tort_om_24t: fram[fram.length - 1].tort,
      'tørre_timer_neste_24': torre.length,
      neste_torre_time: torre[0]?.tid ?? null,
      neste_vate_time: vate[0]?.tid ?? null,
      grunner_na: forste.grunner,
    },
  }
}

export async function hentFelt(): Promise<Felt[] | null> {
  try {
    if (brukerSupabase) {
      // Bare felt-delen av jsonb-en; hele varselet er ~130 kB per felt
      const rows = await sb<{ felt: Felt }[]>('varsel_siste?select=felt:data->felt&order=felt.asc')
      return rows.map((r) => r.felt)
    }
    return await api<Felt[]>('/api/felt')
  } catch (e) {
    console.log(e)
    return null
  }
}

export async function hentVarsel(slug: string, na?: string): Promise<Varsel | null> {
  try {
    const naTid = na ? tolkTid(na) : new Date()
    if (brukerSupabase) {
      const rows = await sb<{ data: Varsel }[]>(`varsel_siste?felt=eq.${encodeURIComponent(slug)}&select=data`)
      if (!rows.length) return null
      return vinduFraNa(rows[0].data, naTid)
    }
    // samme form i begge moduser: be API-et om ut dag +4 og klipp på samme måte
    const v = await api<Varsel>(`/api/felt/${slug}/varsel?timer=120${na ? `&na=${encodeURIComponent(na)}` : ''}`)
    return vinduFraNa(v, naTid)
  } catch (e) {
    console.log(e)
    return null
  }
}

/** Alle felt med varselet klippet fra nå, til forsiden. */
export async function hentOversikt(): Promise<Varsel[] | null> {
  try {
    if (brukerSupabase) {
      const rows = await sb<{ data: Varsel }[]>('varsel_siste?select=data&order=felt.asc')
      return rows.map((r) => vinduFraNa(r.data))
    }
    const felt = await api<Felt[]>('/api/felt')
    const varsler = await Promise.all(felt.map((f) => hentVarsel(f.slug)))
    return varsler.filter((v): v is Varsel => v !== null)
  } catch (e) {
    console.log(e)
    return null
  }
}

const DAGEN_FOR = 24 // «varslet dagen før»: ledetiden nærmest 24 t
const SLINGRING = 2 // timesjobben har hull, så 22-26 t godtas

/** For hver time: varselet med ledetid nærmest `mal` (innenfor ± SLINGRING), ved likt den korteste. */
export function velgTidligereVarsel(rader: TidligereVarsel[], mal = DAGEN_FOR): TidligereVarsel[] {
  const perTime = new Map<number, TidligereVarsel>()
  for (const r of rader) {
    const avvik = Math.abs(r.ledetid_timer - mal)
    if (avvik > SLINGRING) continue
    const t = Date.parse(r.tid)
    const har = perTime.get(t)
    const harAvvik = har ? Math.abs(har.ledetid_timer - mal) : Infinity
    if (!har || avvik < harAvvik || (avvik === harAvvik && r.ledetid_timer < har.ledetid_timer)) perTime.set(t, r)
  }
  return [...perTime.entries()].sort((a, b) => a[0] - b[0]).map(([, r]) => r)
}

/** Varselet slik det så ut dagen før, for timene etter `fra`. Tom liste uten Supabase-nøkler.
 *  PostgREST gir maks 1000 rader per kall, så vi spør bare etter 5 ledetider (5 × 168 = 840). */
export async function hentTidligereVarsel(slug: string, fra: Date): Promise<TidligereVarsel[]> {
  if (!harSupabase) return []
  const ledetider = Array.from({ length: 2 * SLINGRING + 1 }, (_, i) => DAGEN_FOR - SLINGRING + i).join(',')
  try {
    const rader = await sb<TidligereVarsel[]>(
      `varsel?felt=eq.${encodeURIComponent(slug)}&tid=gte.${encodeURIComponent(fra.toISOString())}` +
        `&ledetid_timer=in.(${ledetider})&select=tid,status,ledetid_timer&order=tid.asc&limit=1000`,
    )
    return velgTidligereVarsel(rader)
  } catch (e) {
    console.log(e)
    return []
  }
}

// ---- observasjoner ----

/** Siste 10 observasjoner, eller alle etter `fra` (til historikken). */
export async function hentObservasjoner(slug: string, fra?: Date): Promise<Observasjoner | null> {
  try {
    if (brukerSupabase) {
      const [stats, rows] = await Promise.all([
        sb<{ antall: number; antall_vurdert: number; andel_riktig: number | null }>('rpc/treffsikkerhet', {
          method: 'POST',
          body: JSON.stringify({ p_felt: slug }),
        }),
        sb<{ tid: string; status: Status; predikert_status: string | null; riktig: boolean | null; kommentar: string | null }[]>(
          `observasjoner?felt=eq.${encodeURIComponent(slug)}&select=tid,status,predikert_status,riktig,kommentar` +
            (fra ? `&tid=gte.${encodeURIComponent(fra.toISOString())}&order=tid.asc&limit=500` : '&order=registrert.desc&limit=10'),
        ),
      ])
      return {
        ...stats,
        observasjoner: rows.map((r) => ({
          time: r.tid,
          status: r.status,
          predikert_status: r.predikert_status ?? '',
          riktig: r.riktig === null ? '' : r.riktig ? 1 : 0,
          kommentar: r.kommentar ?? '',
        })),
      }
    }
    const res = await api<Observasjoner>(`/api/felt/${slug}/observasjoner?siste=${fra ? 500 : 10}`)
    if (fra) res.observasjoner = res.observasjoner.filter((o) => Date.parse(o.time) >= fra.getTime())
    return res
  } catch (e) {
    console.log(e)
    return null
  }
}

const STATUSER = ['tort', 'fuktig', 'vatt', 'is'] as const
const PREDIKERT = ['tort', 'fuktig', 'vatt', 'is'] as const

export type NyObservasjon = { status: string; tid?: string | null; predikert_status?: string | null; kommentar?: string | null; kilde?: string }

/** Tid uten tidssone (f.eks. "2026-10-27T14:30:00") tolkes som norsk tid. */
export function tolkTid(s: string): Date {
  if (/[zZ]$|[+-]\d\d:?\d\d$/.test(s)) return new Date(s)
  const m = s.match(/^(\d{4})-(\d\d)-(\d\d)T(\d\d):(\d\d)(?::(\d\d))?$/)
  if (!m) return new Date(NaN)
  const somUtc = Date.UTC(+m[1], +m[2] - 1, +m[3], +m[4], +m[5], +(m[6] ?? 0))
  const offset = (t: number) => {
    const navn = new Intl.DateTimeFormat('en-US', { timeZone: 'Europe/Oslo', timeZoneName: 'shortOffset' })
      .formatToParts(new Date(t)).find((p) => p.type === 'timeZoneName')?.value ?? 'GMT'
    const o = navn.match(/GMT([+-]\d+)(?::(\d+))?/)
    return o ? (Number(o[1]) * 60 + Math.sign(Number(o[1])) * Number(o[2] ?? 0)) * 60e3 : 0
  }
  const forste = somUtc - offset(somUtc)
  return new Date(somUtc - offset(forste)) // andre runde håndterer sommertid-skiftet
}

/** Varselets status for timen `tid` faller i, slik det så ut sist før tidspunktet (minst ledetid). */
async function predikertFra(slug: string, tid: Date): Promise<string | null> {
  const timeslutt = new Date(Math.ceil(tid.getTime() / 3600e3) * 3600e3).toISOString()
  try {
    const q = (filter: string) =>
      sb<{ status: string }[]>(
        `varsel?felt=eq.${encodeURIComponent(slug)}&tid=eq.${encodeURIComponent(timeslutt)}${filter}&select=status&limit=1`,
      )
    const forFor = await q(`&generert=lte.${encodeURIComponent(tid.toISOString())}&order=generert.desc`)
    if (forFor.length) return forFor[0].status
    const senere = await q('&order=generert.asc') // f.eks. rett etter at arkivet startet
    if (senere.length) return senere[0].status
    // Reserve: siste varsel inneholder modellens anslag for de siste 24 timene (dekker tiden før arkivet)
    const siste = await sb<{ data: Varsel }[]>(`varsel_siste?felt=eq.${encodeURIComponent(slug)}&select=data`)
    const v = siste[0]?.data
    const treff = v && [...v.siste_timer, ...v.timer].find((t) => Date.parse(t.tid) === Date.parse(timeslutt))
    return treff?.status ?? null
  } catch (e) {
    console.log(e)
    return null
  }
}

/** Validerer og lagrer. Returnerer [http-status, svar]. */
export async function lagreObservasjon(slug: string, obs: NyObservasjon): Promise<[number, unknown]> {
  if (!brukerSupabase) {
    const res = await fetch(`${API_URL}/api/felt/${slug}/observasjoner`, {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify(obs),
    })
    return [res.status, await res.json().catch(() => ({}))]
  }
  if (!STATUSER.includes(obs.status as (typeof STATUSER)[number])) return [422, { detail: 'Ugyldig status' }]
  if (obs.predikert_status && !PREDIKERT.includes(obs.predikert_status as (typeof PREDIKERT)[number]))
    return [422, { detail: 'Ugyldig predikert_status' }]
  const tid = obs.tid ? tolkTid(obs.tid) : new Date()
  if (Number.isNaN(tid.getTime())) return [422, { detail: 'Ugyldig tid' }]
  const nå = Date.now()
  if (tid.getTime() > nå + 5 * 60e3) return [422, { detail: 'Kan ikke registrere observasjoner fram i tid' }]
  if (tid.getTime() < nå - 14 * 24 * 3600e3) return [422, { detail: 'Observasjonen er for gammel (maks 14 dager)' }]
  const kommentar = (obs.kommentar ?? '').replace(/\s+/g, ' ').trim().slice(0, 500) || null
  const felt = await hentFelt()
  if (!felt?.some((f) => f.slug === slug)) return [404, { detail: `Ukjent felt: ${slug}` }]
  // Hva sa varselet for denne timen? Slås opp i arkivet; klientens verdi er bare reserve.
  const predikert = (await predikertFra(slug, tid)) ?? obs.predikert_status ?? null
  const riktig = predikert ? (predikert === 'tort') === (obs.status === 'tort') : null
  const rad = {
    felt: slug,
    tid: tid.toISOString(),
    status: obs.status,
    predikert_status: predikert,
    riktig,
    kommentar,
    // KLATREFORHOLD_KILDE=dev lokalt, så testklikk kan holdes utenfor treningsdataene
    kilde: (process.env.KLATREFORHOLD_KILDE || obs.kilde || 'web').slice(0, 40),
  }
  await sb('observasjoner', { method: 'POST', body: JSON.stringify(rad), headers: { Prefer: 'return=minimal' } })
  return [201, { lagret: { ...rad, riktig: riktig === null ? '' : riktig ? 1 : 0 } }]
}

export type { Time }

// ---- statistikk til "Om modellen" ----

export type FeltStatistikk = {
  felt: string
  observasjoner: number
  tort: number
  fuktig: number
  vatt: number
  is?: number
  vurdert: number
  andel_riktig: number | null
  kjoringer: number
  forste_varsel: string
  siste_varsel: string
}

/** Antall observasjoner (uten dev/test) og størrelsen på varselarkivet per felt. Null uten Supabase. */
export async function hentStatistikk(): Promise<FeltStatistikk[] | null> {
  if (!harSupabase) return null
  try {
    const res = await sb<{ felt: FeltStatistikk[] }>('rpc/statistikk', { method: 'POST', body: '{}' })
    return res.felt
  } catch (e) {
    console.log(e)
    return null
  }
}
