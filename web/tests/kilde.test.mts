process.env.SUPABASE_URL = 'https://fake.supabase.co'
process.env.SUPABASE_SERVICE_ROLE_KEY = 'nøkkel'
import { readFileSync } from 'node:fs'
const lagret = JSON.parse(readFileSync(new URL('./varsel_eksempel.json', import.meta.url), 'utf8'))
const kall: { url: string; init: RequestInit }[] = []
let arkivTomt = false
globalThis.fetch = (async (url: string, init: RequestInit = {}) => {
  kall.push({ url, init })
  let body: unknown = []
  if (url.includes('select=felt:data->felt')) body = [{ felt: lagret.felt }] // hentFelt: bare felt-delen
  else if (url.includes('varsel_siste')) body = [{ data: lagret }]
  else if (url.includes('/varsel?')) body = arkivTomt ? [] : [{ status: 'vatt' }] // arkivet sier vått
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

// tid uten tidssone tolkes som norsk tid (vinter UTC+1, sommer UTC+2)
assert(k.tolkTid('2026-10-27T14:30:00').toISOString() === '2026-10-27T13:30:00.000Z', 'vintertid')
assert(k.tolkTid('2026-07-15T14:30:00').toISOString() === '2026-07-15T12:30:00.000Z', 'sommertid')
assert(k.tolkTid('2026-07-15T14:30:00Z').toISOString() === '2026-07-15T14:30:00.000Z', 'eksplisitt UTC beholdes')
assert(Number.isNaN(k.tolkTid('i går').getTime()), 'tull gir ugyldig dato')

// predikert status hentes fra arkivet, ikke fra klienten
kall.length = 0
const [s5, svar5] = await k.lagreObservasjon('ekstraveggen', { status: 'tort', tid: new Date(Date.now() - 3 * 3600e3).toISOString(), predikert_status: 'tort' })
const arkivKall = kall.find((c) => c.url.includes('/varsel?'))
const rad5 = JSON.parse(kall.find((c) => c.init.method === 'POST' && c.url.endsWith('/observasjoner'))!.init.body as string)
assert(s5 === 201 && arkivKall && rad5.predikert_status === 'vatt' && rad5.riktig === false, 'arkivet vinner over klienten')
assert(arkivKall!.url.includes('generert=lte.') && /tid=eq\.\d{4}-\d\d-\d\dT\d\d%3A00%3A00\.000Z/.test(arkivKall!.url), 'slår opp riktig time i arkivet')

// lokalt merkes observasjoner som dev
process.env.KLATREFORHOLD_KILDE = 'dev'
kall.length = 0
await k.lagreObservasjon('ekstraveggen', { status: 'tort', kilde: 'web' })
const rad6 = JSON.parse(kall.find((c) => c.init.method === 'POST' && c.url.endsWith('/observasjoner'))!.init.body as string)
assert(rad6.kilde === 'dev', 'dev-merking fra miljøet')

// før arkivet startet: bruk siste varsels anslag for timen
arkivTomt = true
kall.length = 0
const time = lagret.siste_timer[3] // en time i siste_timer i eksempelvarselet
const midtITimen = new Date(Date.parse(time.tid) - 30 * 60e3).toISOString()
const [s7] = await k.lagreObservasjon('ekstraveggen', { status: 'tort', tid: midtITimen })
const rad7 = JSON.parse(kall.find((c) => c.init.method === 'POST' && c.url.endsWith('/observasjoner'))!.init.body as string)
assert(s7 === 201 && rad7.predikert_status === time.status, `reserve fra varsel_siste (${rad7.predikert_status} = ${time.status})`)
arkivTomt = false

// historikk: alle timer før nå, mens siste_timer fortsatt er kuttet til 12
const vh = await k.hentVarsel('ekstraveggen', '2026-10-26T14:20:00+01:00')
const forNa = [...lagret.siste_timer, ...lagret.timer].filter((t: { tid: string }) => Date.parse(t.tid) < Date.parse('2026-10-26T15:00:00+01:00'))
assert(vh!.historikk!.length === forNa.length && vh!.historikk!.at(-1)!.tid === '2026-10-26T14:00:00+01:00', `historikk har alle ${forNa.length} timer før nå`)
const etterNa = [...lagret.siste_timer, ...lagret.timer].filter((t: { tid: string }) => Date.parse(t.tid) >= Date.parse('2026-10-26T15:00:00+01:00'))
assert(vh!.framover!.length === etterNa.length && vh!.timer.length === Math.min(25, etterNa.length), 'framover har alle timer fra nå, timer bare neste døgn')

// varslet dagen før: ledetiden nærmest 24 t per time (22-26 t godtas), ved likt den korteste
const valgt = k.velgTidligereVarsel([
  { tid: '2026-10-28T10:00:00Z', status: 'vatt', ledetid_timer: 26 },
  { tid: '2026-10-28T10:00:00Z', status: 'tort', ledetid_timer: 23 },
  { tid: '2026-10-28T10:00:00Z', status: 'fuktig', ledetid_timer: 25 },
  { tid: '2026-10-28T13:00:00Z', status: 'fuktig', ledetid_timer: 22 },
  { tid: '2026-10-28T09:00:00Z', status: 'vatt', ledetid_timer: 12 },
])
assert(valgt.length === 2 && valgt[0].status === 'tort' && valgt[1].tid === '2026-10-28T13:00:00Z', 'velger ledetid nærmest 24 t, hull er greit')
kall.length = 0
await k.hentTidligereVarsel('ekstraveggen', new Date('2026-10-22T00:00:00Z'))
assert(kall.some((c) => c.url.includes('/varsel?') && c.url.includes('ledetid_timer=in.(22,23,24,25,26)') && c.url.includes('tid=gte.2026-10-22')), 'spør arkivet om 5 ledetider (under 1000 rader)')
kall.length = 0
await k.hentObservasjoner('ekstraveggen', new Date('2026-10-22T00:00:00Z'))
assert(kall.some((c) => c.url.includes('observasjoner?felt') && c.url.includes('tid=gte.') && !c.url.includes('limit=10&')), 'observasjoner etter en dato')
