import type { Status, Time, Varsel } from '../lib/api.ts'
const d = await import('../lib/dager.ts')
const assert = (c: unknown, m: string) => { if (!c) { console.log('FEIL', m); process.exit(1) } else console.log('OK', m) }

const H = 3600e3
/** En time som starter `startMs` (tidsstempelet er slutten av timen). */
function time(startMs: number, o: Partial<Time> = {}): Time {
  return {
    tid: new Date(startMs + H).toISOString(), status: 'tort', status_tekst: '', tort: true, p_vatt: null, vann_mm: 0,
    bergtemp: 8, duggpunkt: 6, lufttemp: 9, luftfuktighet: 85, nedbor_mm: 0, regn_mot_veggen_mm: 0,
    vind_ms: 3, vindretning: 225, sol_pa_veggen: false, sol_wm2: 0, timer_til_tort: null, grunner: [], ...o,
  }
}
/** Timer for ett døgn i norsk vintertid (UTC+1), status per klokketime. */
function dognVinter(dato: string, status: (h: number) => Status, o: (h: number) => Partial<Time> = () => ({})): Time[] {
  const midnatt = Date.parse(`${dato}T00:00:00+01:00`)
  return Array.from({ length: 24 }, (_, h) => {
    const s = status(h)
    return time(midnatt + h * H, { status: s, tort: s === 'tort', ...o(h) })
  })
}

// norsk tid og sommertid
assert(d.oslo(Date.parse('2026-10-25T00:30:00Z')).time === 2 && d.oslo(Date.parse('2026-10-25T01:30:00Z')).time === 2, 'kl 02 to ganger når sommertiden slutter')
assert(d.oslo(Date.parse('2026-07-01T12:00:00Z')).time === 14, 'sommertid UTC+2')

// timen 23-24 hører til samme døgn (tidsstempelet er slutten av timen)
const sen = d.delIDager([time(Date.parse('2026-10-29T22:00:00Z'), { nedbor_mm: 1 })])
assert(sen.length === 1 && sen[0].dato === '2026-10-29' && sen[0].timer[23]?.nedbor_mm === 1, 'kl 23-24 ligger på riktig dag og plass')

// 25-timersdøgnet 25. oktober: 24 plasser, den doble timen slås sammen
const start25 = Date.parse('2026-10-24T22:00:00Z') // midnatt norsk sommertid
const dogn25 = Array.from({ length: 25 }, (_, i) => time(start25 + i * H, { nedbor_mm: i === 2 || i === 3 ? 0.5 : 0, status: i === 3 ? 'vatt' : 'tort' }))
const dst = d.delIDager(dogn25)
assert(dst.length === 1 && dst[0].timer.every((t) => t !== null), 'sommertid slutter: alle 24 plasser fylt')
assert(dst[0].timer[2]!.nedbor_mm === 1 && dst[0].timer[2]!.status === 'vatt', 'den doble timen: regn summert, siste status')

// dagsoppsummering i klatretimene (kl 08-21)
const naMs = Date.parse('2026-10-29T20:30:00Z')
const vattTil13 = d.delIDager(dognVinter('2026-10-30', (h) => (h < 13 ? 'vatt' : 'tort'), (h) => ({ nedbor_mm: h === 5 ? 2 : 0, sol_pa_veggen: h === 16 })))[0]
const s1 = d.oppsummerDag(vattTil13, naMs)
assert(s1.status === 'tort' && s1.tekst === 'kl 13–21' && s1.regn_mm === 2 && s1.soltimer === 1, `tørt vindu (${s1.tekst})`)
const helt = d.oppsummerDag(d.delIDager(dognVinter('2026-10-30', () => 'tort'))[0], naMs)
assert(helt.status === 'tort' && helt.tekst === 'hele dagen', 'tørt hele dagen')
const fuktig = d.oppsummerDag(d.delIDager(dognVinter('2026-10-30', (h) => (h >= 10 && h < 15 ? 'fuktig' : 'vatt')))[0], naMs)
assert(fuktig.status === 'fuktig' && fuktig.tekst === 'beste kl 10–15', `fuktig vindu (${fuktig.tekst})`)
const kort = d.oppsummerDag(d.delIDager(dognVinter('2026-10-30', (h) => (h === 12 || h === 13 ? 'tort' : 'vatt'), (h) => ({ nedbor_mm: h < 6 ? 1 : 0 })))[0], naMs)
assert(kort.status === 'vatt' && kort.tekst === '6.0 mm regn', `to tørre timer er ikke nok (${kort.status})`)
assert(!s1.usikker && d.oppsummerDag(d.delIDager(dognVinter('2026-11-02', () => 'tort'))[0], naMs).usikker, 'over 60 t fram er usikkert')

// dagboksene: Nå + fire dager, manglende dag gir «–»
const framover = [...dognVinter('2026-10-30', (h) => (h < 13 ? 'vatt' : 'tort')), ...dognVinter('2026-10-31', () => 'tort'), ...dognVinter('2026-11-01', () => 'vatt')]
const varsel = {
  felt: { slug: 'x', navn: 'X', felt_id: 1, lat: 0, lon: 0, orientering: 300 }, generert: '', na: '', kilde: '', ml_modell: false,
  sammendrag: { status_na: 'vatt', status_na_tekst: 'Vått', tort_na: false, tort_om_24t: true, 'tørre_timer_neste_24': 8, neste_torre_time: '2026-10-30T13:00:00Z', neste_vate_time: null, grunner_na: [] },
  timer: framover.slice(0, 25), siste_timer: [], framover, forbehold: '',
} as Varsel
const bokser = d.dagBokser(varsel, naMs)
assert(bokser.length === 5 && bokser[0].navn === 'Nå' && bokser[0].tekst === 'tørt fra i morgen kl 13', `Nå-boksen (${bokser[0].tekst})`)
assert(bokser[1].navn === 'I morgen' && bokser[1].status === 'tort' && bokser[1].tekst === 'kl 13–21', 'I morgen')
assert(bokser[2].tekst === 'hele dagen' && bokser[3].status === 'vatt', 'dag +2 og +3')
assert(bokser[4].status === null && bokser[4].tekst === '–', 'dag uten varsel gir «–»')
assert(/^man 2\.$/.test(bokser[4].navn) && /^lør 31\.$/.test(bokser[2].navn), `ukedager (${bokser[2].navn}, ${bokser[4].navn})`)

// siste regn og når veggen var tørr igjen
const uke = dognVinter('2026-10-28', (h) => (h >= 3 && h < 12 ? 'vatt' : 'tort'), (h) => ({ nedbor_mm: h === 2 || h === 4 ? 1.5 : h === 3 ? 0.1 : 0 }))
const r = d.sisteRegn(uke, Date.parse('2026-10-28T23:00:00Z'))!
assert(r && r.start === uke[2].tid && r.slutt === uke[4].tid && Math.abs(r.mm - 3.1) < 1e-9, 'byge med kort opphold er én byge')
assert(r.tort_igjen === uke[12].tid && r.timer_siden === 19, `tørt igjen etter regnet (${r.tort_igjen}, ${r.timer_siden} t siden)`)
assert(d.sisteRegn(uke.map((t) => ({ ...t, nedbor_mm: 0 })), naMs) === null, 'ingen regn gir null')

// hjelpere
const b = d.biter<Status>(['vatt', 'vatt', 'tort', null, null, 'tort'])
assert(b.length === 4 && b[0].til === 2 && b[1].v === 'tort' && b[2].v === null && b[3].fra === 5, 'statusløp')
assert(d.riktig('tort', 'tort') === true && d.riktig('fuktig', 'vatt') === true && d.riktig('tort', 'fuktig') === false && d.riktig('tort', null) === null, 'tørt mot ikke tørt')
assert(d.kompass(300) === 'VNV' && d.kompass(270) === 'V' && d.kompass(225, 8) === 'SV' && d.kompass(350) === 'N', 'kompass')
const spt = d.statusPerTime(dognVinter('2026-10-28', (h) => (h === 14 ? 'vatt' : 'tort')))
assert(spt['2026-10-28T14'] === 'vatt' && spt['2026-10-28T00'] === 'tort' && Object.keys(spt).length === 24, 'status per time til skjemaet')

// en rad i ukerutenettet: meldinger, «nå», summer og tabell
const iGar = d.delIDager(dognVinter('2026-10-28', (h) => (h < 12 ? 'vatt' : 'tort'), (h) => ({ nedbor_mm: h === 4 ? 1.2 : 0, sol_pa_veggen: h === 15 || h === 16, sol_mulig: h >= 13 && h <= 16 })))[0]
const varslet = new Map<number, Status>([[Date.parse(iGar.timer[14]!.tid), 'vatt']])
const rad = d.lagUkeRad(iGar, {
  iDag: '2026-10-29', naMs, varslet,
  meldinger: [{ time: '2026-10-28T13:20:00Z', status: 'tort', kommentar: 'helt fint' }, { time: '2026-10-27T13:00:00Z', status: 'vatt', kommentar: '' }],
})
assert(rad.navn === 'I går' && rad.celler.length === 24 && rad.na === undefined, 'rad for i går')
assert(rad.meldinger.length === 1 && Math.abs(rad.meldinger[0].pos - (14 + 20 / 60)) < 1e-9, 'melding plassert kl 14:20 norsk tid')
assert(rad.meldinger[0].etter === true && rad.meldinger[0].for === false, 'riktig i etterkant, feil dagen før')
assert(rad.sum.regn === '1.2' && rad.sum.sol === '2 t' && rad.sum.vind === '3' && rad.tabell.length === 24, 'summer og tabell')
assert(rad.sum.linje.replace(/\u00a0/g, ' ') === '1.2 mm · 2 t sol · 3 m/s', 'summene på én linje')
assert(rad.celler[13]!.solMulig && !rad.celler[13]!.sol && rad.celler[15]!.sol && !rad.celler[12]!.solMulig && rad.tabell[13].solMulig, 'sol mulig mot direkte sol')
assert(rad.celler[14]!.v === 'vatt' && rad.celler[13]!.v === null && rad.tabell[4].regn === '1.2', 'varslet dagen før per time')
assert(rad.tabell[5].regn === '' && rad.tabell[13].h === 13 && rad.tabell[13].temp === '9°' && rad.tabell[13].berg === '8°' && rad.tabell[13].vindTekst === '3 m/s fra sørvest' && !rad.tabell.some((t) => t.na), 'timetabell: temperatur, vind og ingen «nå» i går')
const iDagRad = d.lagUkeRad(d.delIDager(dognVinter('2026-10-29', () => 'tort'))[0], { iDag: '2026-10-29', naMs })
assert(iDagRad.navn === 'I dag' && Math.abs(iDagRad.na! - 21.5) < 1e-9, '«nå» kl 21:30')
