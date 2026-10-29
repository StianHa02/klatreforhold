import HistorikkScroll from '@/components/HistorikkScroll'
import { type Observasjoner, type Status, type TidligereVarsel, type Time, dag, klokke, statusFarge } from '@/lib/api'
import { dagNokkel, perDag, sisteRegn, treff } from '@/lib/historikk'

// Siste 7 døgn: hva modellen mener har skjedd på veggen, hva varselet sa på forhånd, hva klatrerne
// meldte, og været som styrer tørkingen (regn, sol på veggen, vind). Én SVG med faste piksler per time,
// så teksten holder størrelsen; på mobil rulles den sideveis og starter ved «nå».
const PX = 4 // piksler per time
const RADER = [
  { navn: 'dag', h: 16, tekst: '' },
  { navn: 'status', h: 18, tekst: 'Modellen' },
  { navn: 'varslet', h: 8, tekst: 'Varslet' },
  { navn: 'obs', h: 22, tekst: 'Klatrere' },
  { navn: 'regn', h: 52, tekst: 'Regn' },
  { navn: 'sol', h: 40, tekst: 'Sol på veggen' },
  { navn: 'vind', h: 44, tekst: 'Vind' },
] as const
const GAP = 4
const topp: Record<string, number> = {}
let y0 = 0
for (const r of RADER) { topp[r.navn] = y0; y0 += r.h + GAP }
const H = y0

const BOKSTAV: Record<Status, string> = { tort: 'T', fuktig: 'F', vatt: 'V', is: 'I' }
const FYLL: Record<Status, string> = {
  tort: 'var(--color-forhold-tort)',
  fuktig: 'var(--color-forhold-fuktig)',
  vatt: 'var(--color-forhold-vatt)',
  is: 'var(--color-forhold-is)',
}
const TEKST_PA: Record<Status, string> = { tort: 'white', fuktig: 'var(--color-dark-900)', vatt: 'white', is: 'white' }
const STATUS_TEKST: Record<Status, string> = { tort: 'Tørt', fuktig: 'Fuktig', vatt: 'Vått', is: 'Is' }

type Obs = Observasjoner['observasjoner'][number]

export default function Historikk({ timer, na, tidligere, obs }: {
  timer: Time[]
  na: string
  tidligere: TidligereVarsel[]
  obs: Obs[]
}) {
  if (timer.length < 24) return null // gammelt varsel uten historikk (før første kjøring med 7 døgn)
  const n = timer.length
  const W = n * PX
  const t0 = Date.parse(timer[0].tid) - 3600e3 // starten av første time
  const xTid = (ms: number) => ((ms - t0) / 3600e3) * PX
  const indeks = new Map(timer.map((t, i) => [Date.parse(t.tid), i]))

  const regn = sisteRegn(timer, na)
  const dogn = perDag(timer).slice(-7)
  const { riktige, vurdert } = treff(obs)
  const harSolWm2 = timer.some((t) => t.sol_wm2 !== undefined)

  // Skalaer
  const maksRegn = Math.max(2, ...timer.map((t) => t.nedbor_mm))
  const maksSol = Math.max(300, ...timer.map((t) => t.sol_wm2 ?? 0))
  const maksVind = Math.max(8, ...timer.map((t) => t.vind_ms))
  const yRegn = (mm: number) => (Math.min(mm, maksRegn) / maksRegn) * RADER[4].h
  const bunn = (navn: string) => topp[navn] + RADER.find((r) => r.navn === navn)!.h
  const linje = (f: (t: Time) => number, rad: string, maks: number, min = 0) =>
    timer.map((t, i) => {
      const h = RADER.find((r) => r.navn === rad)!.h
      const y = bunn(rad) - ((Math.max(min, Math.min(f(t), maks)) - min) / (maks - min)) * h
      return `${i ? 'L' : 'M'}${(i * PX + PX / 2).toFixed(1)},${y.toFixed(1)}`
    }).join(' ')

  // Sammenhengende statusbiter, med bokstav når biten er bred nok (farge er ikke eneste kjennetegn)
  const biter: { s: Status; fra: number; til: number }[] = []
  timer.forEach((t, i) => {
    const siste = biter[biter.length - 1]
    if (siste && siste.s === t.status) siste.til = i
    else biter.push({ s: t.status, fra: i, til: i })
  })
  const midnatt = timer.map((t, i) => ({ t, i })).filter(({ t, i }) => i > 0 && dagNokkel(t.tid) !== dagNokkel(timer[i - 1].tid))
  const sol = timer.map((t, i) => ({ t, i, s: t.sol_wm2 ?? (t.sol_pa_veggen ? maksSol * 0.6 : 0) }))
  const solArea = `M0,${bunn('sol')} ${sol.map(({ i, s }) => `L${i * PX + PX / 2},${bunn('sol') - (s / maksSol) * RADER[5].h}`).join(' ')} L${W},${bunn('sol')} Z`

  return (
    <section className="rounded-xl border border-border-subtle bg-surface-default p-md">
      <h2 className="h3">Siste 7 døgn</h2>
      <p className="mt-xs text-sm">
        {!regn ? 'Ingen regn de siste 7 døgnene.'
          : regn.timer_siden <= 0 ? `Det regner nå (${regn.mm.toFixed(1)} mm så langt).`
          : <>
              Sist regn: {dag(regn.start)} kl {klokke(new Date(Date.parse(regn.start) - 3600e3).toISOString()).slice(0, 2)}–{klokke(regn.slutt).slice(0, 2)},{' '}
              {regn.mm.toFixed(1)} mm · {regn.timer_siden} t siden · {regn.soltimer_siden} t sol på veggen siden
              {regn.vind_siden !== null && ` · snittvind ${regn.vind_siden.toFixed(1)} m/s`}
            </>}
      </p>
      {vurdert > 0 && (
        <p className="mt-xs text-sm text-text-subtle">
          Siste 7 døgn stemte varselet med {riktige} av {vurdert} tilbakemeldinger (tørt mot ikke tørt).
        </p>
      )}

      <ol className="mt-sm grid grid-cols-7 gap-px text-center text-[11px] tabular-nums sm:text-xs">
        {dogn.map((d) => (
          <li key={d.dag} className="flex flex-col items-center gap-[2px]">
            <span className="text-text-subtle">{dag(d.forste).split(' ')[0].replace('.', '')}</span>
            <span className={`flex h-md w-full items-center justify-center rounded-sm text-[10px] font-medium ${statusFarge[d.status]} ${d.status === 'fuktig' ? 'text-dark-900' : 'text-white'}`}
                  title={`${STATUS_TEKST[d.status]} det meste av dagen (kl 08–20)`}>
              {BOKSTAV[d.status]}
            </span>
            <span>{d.regn_mm >= 0.1 ? <>{d.regn_mm.toFixed(1)}<span className="max-sm:hidden"> mm</span></> : '–'}</span>
            <span className="text-text-subtle">☀ {d.soltimer}<span className="max-sm:hidden"> t</span></span>
            <span className="text-text-subtle">{Math.round(d.maks_vind)}<span className="max-sm:hidden"> m/s</span></span>
          </li>
        ))}
      </ol>
      <p className="mt-xs text-[11px] text-text-subtle sm:hidden">Per dag: regn (mm), timer sol på veggen, sterkeste vind (m/s).</p>

      <div className="mt-md flex text-[11px] text-text-subtle">
        <div className="w-[64px] shrink-0">
          {RADER.map((r) => (
            <div key={r.navn} style={{ height: r.h, marginBottom: GAP }} className="flex flex-col justify-center leading-tight">
              {r.tekst}
              {r.navn === 'regn' && <span className="text-[10px]">maks {maksRegn.toFixed(1)} mm/t</span>}
              {r.navn === 'vind' && <span className="text-[10px]">0–{Math.round(maksVind)} m/s</span>}
            </div>
          ))}
        </div>
        <HistorikkScroll>
          <svg width={W + 18} height={H} role="img" aria-label="Status, tilbakemeldinger, regn, sol og vind time for time de siste 7 døgnene">
            {/* natt: ingen stråling på flaten */}
            {harSolWm2 && timer.map((t, i) => (t.sol_wm2 === 0 ? (
              <rect key={`n${t.tid}`} x={i * PX} y={topp.status} width={PX} height={H - topp.status} fill="var(--color-light-400)" />
            ) : null))}
            {midnatt.map(({ t, i }) => (
              <g key={`d${t.tid}`}>
                <line x1={i * PX} x2={i * PX} y1={0} y2={H} stroke="var(--color-light-800)" />
                <text x={i * PX + 3} y={11} fontSize={11} fill="var(--color-dark-200)">{dag(t.tid)}</text>
              </g>
            ))}
            <line x1={W} x2={W} y1={0} y2={H} stroke="var(--color-dark-200)" strokeDasharray="3 3" />
            <text x={W + 2} y={11} fontSize={11} fill="var(--color-dark-200)">nå</text>

            {biter.map((b) => {
              const bredde = (b.til - b.fra + 1) * PX
              return (
                <g key={`s${b.fra}`}>
                  <rect x={b.fra * PX} y={topp.status} width={bredde} height={RADER[1].h} fill={FYLL[b.s]} />
                  {bredde >= 16 && (
                    <text x={b.fra * PX + bredde / 2} y={topp.status + 13} fontSize={11} textAnchor="middle" fill={TEKST_PA[b.s]}>{BOKSTAV[b.s]}</text>
                  )}
                </g>
              )
            })}
            {tidligere.map((v) => {
              const i = indeks.get(Date.parse(v.tid))
              return i === undefined ? null : (
                <rect key={`v${v.tid}`} x={i * PX} y={topp.varslet + 1} width={PX} height={RADER[2].h - 2} fill={FYLL[v.status]}>
                  <title>{`${dag(v.tid)} ${klokke(v.tid)}: varslet ${STATUS_TEKST[v.status].toLowerCase()} ${v.ledetid_timer} t før`}</title>
                </rect>
              )
            })}
            {obs.map((o) => {
              const x = xTid(Date.parse(o.time))
              if (x < 0 || x > W) return null
              const cy = topp.obs + RADER[3].h / 2
              return (
                <g key={`o${o.time}-${o.status}-${o.kommentar}`}>
                  <title>{`${dag(o.time)} ${klokke(o.time)}: klatrer meldte ${STATUS_TEKST[o.status].toLowerCase()}${o.riktig === '' ? '' : Number(o.riktig) === 1 ? ', varselet stemte' : ', varselet bommet'}${o.kommentar ? ` («${o.kommentar}»)` : ''}`}</title>
                  <circle cx={x} cy={cy} r={8} fill={FYLL[o.status]} stroke="white" />
                  <text x={x} y={cy + 4} fontSize={10} textAnchor="middle" fill={TEKST_PA[o.status]}>{BOKSTAV[o.status]}</text>
                  {o.riktig !== '' && (
                    <text x={x + 10} y={cy + 4} fontSize={11} fill="var(--color-dark-400)">{Number(o.riktig) === 1 ? '✓' : '✗'}</text>
                  )}
                </g>
              )
            })}

            {timer.map((t, i) => (
              <g key={`r${t.tid}`}>
                <rect x={i * PX} y={bunn('regn') - yRegn(t.nedbor_mm)} width={PX - 0.5} height={yRegn(t.nedbor_mm)} fill="var(--color-accent-blue-200)" />
                <rect x={i * PX} y={bunn('regn') - yRegn(t.regn_mot_veggen_mm)} width={PX - 0.5} height={yRegn(t.regn_mot_veggen_mm)} fill="var(--color-accent-blue-400)" />
              </g>
            ))}
            <line x1={0} x2={W} y1={bunn('regn')} y2={bunn('regn')} stroke="var(--color-light-800)" />

            <path d={solArea} fill="var(--color-accent-yellow-400)" fillOpacity={0.6} stroke="var(--color-accent-yellow-400)" />
            <line x1={0} x2={W} y1={bunn('sol')} y2={bunn('sol')} stroke="var(--color-light-800)" />

            <path d={linje((t) => t.luftfuktighet, 'vind', 100, 50)} fill="none" stroke="var(--color-dark-50)" strokeWidth={1} strokeDasharray="2 2" />
            <path d={linje((t) => t.vind_ms, 'vind', maksVind)} fill="none" stroke="var(--color-dark-400)" strokeWidth={1.5} />
            {timer.map((t, i) => (i % 6 === 3 ? (
              // pil i den retningen vinden blåser (vindretning er der den kommer fra)
              <path key={`p${t.tid}`} d="M0,-5 L0,5 M-3,2 L0,5 L3,2" fill="none" stroke="var(--color-dark-200)" strokeWidth={1}
                    transform={`translate(${i * PX + PX / 2},${topp.vind + 7}) rotate(${t.vindretning})`} />
            ) : null))}
            <line x1={0} x2={W} y1={bunn('vind')} y2={bunn('vind')} stroke="var(--color-light-800)" />

            {/* usynlige kolonner med verdiene for timen ved hover/trykk */}
            {timer.map((t, i) => (
              <rect key={`h${t.tid}`} x={i * PX} y={topp.status} width={PX} height={H - topp.status} fill="transparent">
                <title>{`${dag(t.tid)} kl ${klokke(t.tid)}: ${t.status_tekst} · regn ${t.nedbor_mm.toFixed(1)} mm (mot veggen ${t.regn_mot_veggen_mm.toFixed(1)}) · ${t.sol_wm2 !== undefined ? `sol på veggen ${t.sol_wm2} W/m²` : t.sol_pa_veggen ? 'sol på veggen' : 'ikke sol på veggen'} · vind ${t.vind_ms.toFixed(1)} m/s · fuktighet ${Math.round(t.luftfuktighet)} %`}</title>
              </rect>
            ))}
          </svg>
        </HistorikkScroll>
      </div>

      <div className="mt-sm flex flex-col gap-xs text-xs text-text-subtle">
        <p>
          <b className="font-medium text-text-default">Modellen:</b> modellen kjørt i etterkant på været slik det ble.{' '}
          <b className="font-medium text-text-default">Varslet:</b> varselet slik det så ut 1–6 timer før (finnes fra 27. oktober 2026).{' '}
          <b className="font-medium text-text-default">Klatrere:</b> tilbakemeldinger, ✓/✗ om varselet stemte.
        </p>
        <p>
          T tørt, F fuktig, V vått, I is. Regn: lys søyle er nedbør, mørk er regn som treffer veggen. Sol: stråling
          på veggen (lyse felt er natt). Vind: hel linje m/s, piler viser hvor vinden blåser, stiplet linje er
          luftfuktighet 50–100 % (over ~90 % tørker berget svært sakte). Hold over eller trykk for verdiene.
        </p>
      </div>
    </section>
  )
}
