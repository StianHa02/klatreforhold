import type { Time } from '../lib/api.ts'
const h = await import('../lib/historikk.ts')
const assert = (c: unknown, m: string) => { if (!c) { console.log('FEIL', m); process.exit(1) } else console.log('OK', m) }

// 48 timer fra 2026-10-27 00 UTC (01 norsk tid); regn kl 05-07 UTC med en tørr time i mellom, sol om ettermiddagen
const timer: Time[] = Array.from({ length: 48 }, (_, i) => {
  const tid = new Date(Date.UTC(2026, 9, 27, i)).toISOString()
  const regn = i === 5 || i === 7 ? 1.5 : i === 6 ? 0.1 : 0
  return {
    tid, status: i >= 5 && i < 20 ? 'vatt' : 'tort', status_tekst: '', tort: true, p_vatt: null, vann_mm: 0,
    bergtemp: 8, duggpunkt: 6, lufttemp: 9, luftfuktighet: 85, nedbor_mm: regn, regn_mot_veggen_mm: regn / 2,
    vind_ms: i < 24 ? 2 : 6, vindretning: 270, sol_pa_veggen: i % 24 >= 14 && i % 24 <= 16, sol_wm2: 0,
    timer_til_tort: null, grunner: [],
  }
})
const na = new Date(Date.UTC(2026, 9, 28, 23)).toISOString()
const r = h.sisteRegn(timer, na)!
assert(r && r.start === timer[5].tid && r.slutt === timer[7].tid, 'byge med kort opphold er én byge')
assert(Math.abs(r.mm - 3.1) < 1e-9, `mm i bygen (${r.mm})`)
assert(r.timer_siden === 40, `timer siden (${r.timer_siden})`)
assert(r.soltimer_siden === 6, `soltimer siden (${r.soltimer_siden})`)
assert(h.sisteRegn(timer.map((t) => ({ ...t, nedbor_mm: 0 })), na) === null, 'ingen regn gir null')

const d = h.perDag(timer)
assert(d.length === 3 && d[0].dag === '2026-10-27', `døgn i norsk tid (${d.map((x) => x.dag)})`)
assert(d[0].status === 'vatt' && d[1].status === 'tort', 'vanligste status kl 08-20')
assert(Math.abs(d[0].regn_mm - 3.1) < 1e-9 && d[0].soltimer === 3 && d[1].maks_vind === 6, 'regn, sol og vind per døgn')
assert(h.timeIOslo('2026-07-01T12:00:00Z') === 14 && h.timeIOslo('2026-12-01T12:00:00Z') === 13, 'klokkeslett i Oslo med sommertid')

const t = h.treff([{ riktig: 1 }, { riktig: 0 }, { riktig: '' }, { riktig: 1 }])
assert(t.riktige === 2 && t.vurdert === 3, 'treff teller bare vurderte')
