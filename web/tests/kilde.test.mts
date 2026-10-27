process.env.SUPABASE_URL = 'https://fake.supabase.co'
process.env.SUPABASE_SERVICE_ROLE_KEY = 'nøkkel'
import { readFileSync } from 'node:fs'
const lagret = JSON.parse(readFileSync(new URL('./varsel_eksempel.json', import.meta.url), 'utf8'))
const kall: { url: string; init: RequestInit }[] = []
globalThis.fetch = (async (url: string, init: RequestInit = {}) => {
  kall.push({ url, init })
  let body: unknown = []
  if (url.includes('varsel_siste')) body = [{ data: lagret }]
  if (url.includes('rpc/treffsikkerhet')) body = { antall: 3, antall_vurdert: 2, andel_riktig: 0.5 }
  if (url.includes('observasjoner?felt')) body = [{ tid: '2026-10-26T10:00:00Z', status: 'tort', predikert_status: 'vatt', riktig: false, kommentar: null }]
  if (init.method === 'POST' && url.endsWith('/observasjoner')) return new Response('', { status: 201 })
  return new Response(JSON.stringify(body), { status: 200 })
}) as typeof fetch
const k = await import('../lib/kilde.ts')
const assert = (c: unknown, m: string) => { if (!c) { console.log('FEIL', m); process.exit(1) } else console.log('OK', m) }

assert(k.brukerSupabase, 'supabase-modus')
const v = await k.hentVarsel('ekstraveggen', '2026-10-26T14:20:00+01:00')
assert(v && v.timer[0].tid === '2026-10-26T15:00:00+01:00', `første time er 15:00 (fikk ${v?.timer[0].tid})`)
assert(v!.siste_timer.length === 12 && v!.siste_timer[11].tid === '2026-10-26T14:00:00+01:00', 'siste 12 timer slutter 14:00')
assert(v!.sammendrag.status_na === v!.timer[0].status, 'sammendrag følger første time')
assert(v!.utdatert === false, 'ikke utdatert 2 t etter generering')
const gammel = await k.hentVarsel('ekstraveggen', '2026-10-26T20:00:00+01:00')
assert(gammel!.utdatert === true, 'utdatert etter 3+ timer')
const felt = await k.hentFelt()
assert(felt?.[0].slug === 'ekstraveggen', 'felt fra varsel_siste')
const obs = await k.hentObservasjoner('ekstraveggen')
assert(obs?.antall === 3 && obs.observasjoner[0].riktig === 0, 'observasjoner + treffsikkerhet')
const [st, svar] = await k.lagreObservasjon('ekstraveggen', { status: 'tort', predikert_status: 'vatt', kommentar: '  helt\n tørt ' })
const post = kall.find((c) => c.init.method === 'POST' && c.url.endsWith('/observasjoner'))!
const rad = JSON.parse(post.init.body as string)
assert(st === 201 && rad.riktig === false && rad.kommentar === 'helt tørt' && rad.felt === 'ekstraveggen', 'lagrer observasjon')
assert((post.init.headers as Record<string, string>).Authorization === 'Bearer nøkkel', 'service-nøkkel i header')
const [s2] = await k.lagreObservasjon('ekstraveggen', { status: 'gjørme' })
assert(s2 === 422, 'avviser ugyldig status')
const [s3] = await k.lagreObservasjon('ekstraveggen', { status: 'tort', tid: '2030-01-01T00:00:00Z' })
assert(s3 === 422, 'avviser framtid')
const [s4] = await k.lagreObservasjon('ukjent', { status: 'tort' })
assert(s4 === 404, 'avviser ukjent felt')
