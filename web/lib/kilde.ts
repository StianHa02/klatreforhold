// Datakilde for nettsiden. To moduser:
//  - Supabase (produksjon): SUPABASE_URL + SUPABASE_SERVICE_ROLE_KEY er satt. Leser siste varsel som
//    timesjobben har skrevet, og lagrer observasjoner. Nøkkelen brukes bare på serveren.
//  - Python-API (lokal utvikling): KLATREFORHOLD_API_URL, standard http://localhost:8000
import type { Felt, Observasjoner, Status, Time, Varsel } from './api'

const SB_URL = process.env.SUPABASE_URL
const SB_KEY = process.env.SUPABASE_SERVICE_ROLE_KEY
const API_URL = process.env.KLATREFORHOLD_API_URL ?? 'http://localhost:8000'
export const brukerSupabase = Boolean(SB_URL && SB_KEY)

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

/** Klipper det lagrede varselet (laget for opptil en time siden) til "nå + 24 t" og 12 t bakover. */
export function vinduFraNa(v: Varsel, na: Date = new Date(), timer = 24): Varsel {
  const naTime = new Date(na)
  naTime.setUTCMinutes(0, 0, 0)
  if (naTime.getTime() < na.getTime()) naTime.setUTCHours(naTime.getUTCHours() + 1) // tidsstempel = slutten av timen
  const alle = [...v.siste_timer, ...v.timer].sort((a, b) => Date.parse(a.tid) - Date.parse(b.tid))
  const fram = alle.filter((t) => Date.parse(t.tid) >= naTime.getTime()).slice(0, timer + 1)
  const bak = alle.filter((t) => Date.parse(t.tid) < naTime.getTime()).slice(-12)
  if (fram.length === 0) return { ...v, utdatert: true }
  const torre = fram.filter((t) => t.tort)
  const vate = fram.filter((t) => !t.tort)
  const forste = fram[0]
  return {
    ...v,
    na: forste.tid,
    timer: fram,
    siste_timer: bak,
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
      const rows = await sb<{ data: Varsel }[]>('varsel_siste?select=data')
      return rows.map((r) => r.data.felt)
    }
    return await api<Felt[]>('/api/felt')
  } catch (e) {
    console.log(e)
    return null
  }
}

export async function hentVarsel(slug: string, na?: string): Promise<Varsel | null> {
  try {
    if (brukerSupabase) {
      const rows = await sb<{ data: Varsel }[]>(`varsel_siste?felt=eq.${encodeURIComponent(slug)}&select=data`)
      if (!rows.length) return null
      return vinduFraNa(rows[0].data, na ? new Date(na) : new Date())
    }
    return await api<Varsel>(`/api/felt/${slug}/varsel${na ? `?na=${encodeURIComponent(na)}` : ''}`)
  } catch (e) {
    console.log(e)
    return null
  }
}

// ---- observasjoner ----

export async function hentObservasjoner(slug: string): Promise<Observasjoner | null> {
  try {
    if (brukerSupabase) {
      const [stats, rows] = await Promise.all([
        sb<{ antall: number; antall_vurdert: number; andel_riktig: number | null }>('rpc/treffsikkerhet', {
          method: 'POST',
          body: JSON.stringify({ p_felt: slug }),
        }),
        sb<{ tid: string; status: Status; predikert_status: string | null; riktig: boolean | null; kommentar: string | null }[]>(
          `observasjoner?felt=eq.${encodeURIComponent(slug)}&select=tid,status,predikert_status,riktig,kommentar&order=registrert.desc&limit=10`,
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
    return await api<Observasjoner>(`/api/felt/${slug}/observasjoner?siste=10`)
  } catch (e) {
    console.log(e)
    return null
  }
}

const STATUSER = ['tort', 'fuktig', 'vatt'] as const
const PREDIKERT = ['tort', 'fuktig', 'vatt', 'is'] as const

export type NyObservasjon = { status: string; tid?: string | null; predikert_status?: string | null; kommentar?: string | null; kilde?: string }

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
  const tid = obs.tid ? new Date(obs.tid) : new Date()
  if (Number.isNaN(tid.getTime())) return [422, { detail: 'Ugyldig tid' }]
  const nå = Date.now()
  if (tid.getTime() > nå + 5 * 60e3) return [422, { detail: 'Kan ikke registrere observasjoner fram i tid' }]
  if (tid.getTime() < nå - 14 * 24 * 3600e3) return [422, { detail: 'Observasjonen er for gammel (maks 14 dager)' }]
  const kommentar = (obs.kommentar ?? '').replace(/\s+/g, ' ').trim().slice(0, 500) || null
  const felt = await hentFelt()
  if (!felt?.some((f) => f.slug === slug)) return [404, { detail: `Ukjent felt: ${slug}` }]
  const riktig = obs.predikert_status ? (obs.predikert_status === 'tort') === (obs.status === 'tort') : null
  const rad = {
    felt: slug,
    tid: tid.toISOString(),
    status: obs.status,
    predikert_status: obs.predikert_status ?? null,
    riktig,
    kommentar,
    kilde: (obs.kilde ?? 'web').slice(0, 40),
  }
  await sb('observasjoner', { method: 'POST', body: JSON.stringify(rad), headers: { Prefer: 'return=minimal' } })
  return [201, { lagret: { ...rad, riktig: riktig === null ? '' : riktig ? 1 : 0 } }]
}

export type { Time }
