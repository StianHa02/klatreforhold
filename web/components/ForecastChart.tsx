import { type Time, klokke } from '@/lib/api'

// Enkel SVG-graf uten avhengigheter: vann på veggen (felt), regn mot veggen (søyler),
// og bergtemperatur mot duggpunkt (linjer). Hver graf tegnes i to formater, ett smalt for
// mobil og ett bredt for større skjermer, så teksten holder lesbar størrelse uten scrolling.
// Vann og regn deler én fast skala (0–1 mm), så grafen kan sammenlignes fra dag til dag og mellom felt.
// Veggen holder maks ca. 0.7 mm (film + tak/sprekker), så 1 mm er nok; kraftigere regn kappes og får tallet over.
// Mellom berg og duggpunkt: grønt når berget er varmere (ingen kondens), blått når det er kaldere;
// sterkere farge jo større avstand (full ved 4 °C: under ca. 2 °C er det fare for kondens).
const SKALA_MM = 1
const MARGIN_FULL_C = 4
const MAKS_OPASITET = 0.45
type Format = { W: number; H: number; font: number; hvert: number; pad: { l: number; r: number; t: number; b: number } }
const SMAL: Format = { W: 360, H: 180, font: 12, hvert: 6, pad: { l: 44, r: 6, t: 14, b: 24 } }
const BRED: Format = { W: 760, H: 150, font: 10, hvert: 3, pad: { l: 52, r: 8, t: 12, b: 22 } }

function geometri(timer: Time[], { W, H, pad }: Format) {
  const n = timer.length
  const x = (i: number) => pad.l + (i / Math.max(n - 1, 1)) * (W - pad.l - pad.r)
  const bunn = H - pad.b
  const skala = (min: number, max: number) => (v: number) => bunn - ((v - min) / (max - min)) * (H - pad.t - pad.b)
  const line = (f: (t: Time) => number, y: (v: number) => number) =>
    timer.map((t, i) => `${i ? 'L' : 'M'}${x(i).toFixed(1)},${y(f(t)).toFixed(1)}`).join(' ')
  return { n, x, bunn, skala, line }
}

function Akse({ timer, f, na }: { timer: Time[]; f: Format; na: number }) {
  const { x, bunn } = geometri(timer, f)
  return (
    <>
      <line x1={f.pad.l} x2={f.W - f.pad.r} y1={bunn} y2={bunn} stroke="var(--color-light-800)" />
      {na > 0 && (
        <>
          <line x1={x(na)} x2={x(na)} y1={f.pad.t} y2={bunn} stroke="var(--color-dark-200)" strokeDasharray="3 3" />
          <text x={x(na) + 3} y={f.pad.t + f.font * 0.8} fontSize={f.font} fill="var(--color-dark-200)">nå</text>
        </>
      )}
      {timer.map((t, i) =>
        (i - na) % f.hvert === 0 ? (
          <text key={t.tid} x={x(i)} y={f.H - 6} fontSize={f.font} textAnchor="middle" fill="var(--color-dark-200)">
            {klokke(t.tid).slice(0, 2)}
          </text>
        ) : null,
      )}
    </>
  )
}

function VannGraf({ timer, f, na }: { timer: Time[]; f: Format; na: number }) {
  const { n, x, bunn, skala, line } = geometri(timer, f)
  const y = skala(0, SKALA_MM) // fast skala for både vann (mm) og regn (mm per time)
  const klipp = (v: number) => Math.min(v, SKALA_MM)
  const area = `${line((t) => klipp(t.vann_mm), y)} L${x(n - 1)},${bunn} L${x(0)},${bunn} Z`
  const bw = Math.max(2, (f.W - f.pad.l - f.pad.r) / n - 2)
  return (
    <svg viewBox={`0 0 ${f.W} ${f.H}`} className="w-full" role="img" aria-label="Vann på veggen og regn mot veggen, fast skala 0 til 1 mm">
      {[0.5, 1].map((mm) => (
        <g key={mm}>
          <line x1={f.pad.l} x2={f.W - f.pad.r} y1={y(mm)} y2={y(mm)} stroke="var(--color-light-600)" />
          <text x={2} y={y(mm) + f.font * 0.35} fontSize={f.font} fill="var(--color-dark-200)">{mm === SKALA_MM ? `${mm} mm` : mm}</text>
        </g>
      ))}
      <text x={2} y={bunn} fontSize={f.font} fill="var(--color-dark-200)">0</text>
      {timer.map((t, i) => (
        <rect key={t.tid} x={x(i) - bw / 2} y={y(klipp(t.regn_mot_veggen_mm))} width={bw}
              height={bunn - y(klipp(t.regn_mot_veggen_mm))} fill="var(--color-accent-blue-200)">
          <title>{`kl ${klokke(t.tid)}: ${t.regn_mot_veggen_mm.toFixed(1)} mm regn mot veggen, ${t.vann_mm.toFixed(2)} mm vann på veggen`}</title>
        </rect>
      ))}
      {timer.map((t, i) => (t.regn_mot_veggen_mm > SKALA_MM ? (
        <text key={`k${t.tid}`} x={x(i)} y={y(SKALA_MM) - 2} fontSize={f.font * 0.85} textAnchor="middle" fill="var(--color-dark-200)">
          {t.regn_mot_veggen_mm.toFixed(1)}
        </text>
      ) : null))}
      <path d={area} fill="var(--color-accent-blue-400)" fillOpacity={0.35} stroke="var(--color-accent-blue-400)" />
      <Akse timer={timer} f={f} na={na} />
    </svg>
  )
}

function TempGraf({ timer, f, na }: { timer: Time[]; f: Format; na: number }) {
  const { x, bunn, skala, line } = geometri(timer, f)
  const temps = timer.flatMap((t) => [t.bergtemp, t.duggpunkt])
  const tMin = Math.floor(Math.min(...temps) - 1)
  const tMax = Math.ceil(Math.max(...temps) + 1)
  const yT = skala(tMin, tMax)
  // Feltet mellom linjene time for time; der linjene krysser deles biten i to trekanter
  const opasitet = (avstand: number) => Math.min(Math.abs(avstand) / MARGIN_FULL_C, 1) * MAKS_OPASITET
  const p = (xx: number, v: number) => `${xx.toFixed(1)},${yT(v).toFixed(1)}`
  const fyll: { d: string; tort: boolean; op: number }[] = []
  for (let i = 0; i < timer.length - 1; i++) {
    const a = timer[i]
    const b = timer[i + 1]
    const d0 = a.bergtemp - a.duggpunkt
    const d1 = b.bergtemp - b.duggpunkt
    if (d0 * d1 >= 0) {
      fyll.push({
        d: `M${p(x(i), a.bergtemp)} L${p(x(i + 1), b.bergtemp)} L${p(x(i + 1), b.duggpunkt)} L${p(x(i), a.duggpunkt)} Z`,
        tort: d0 + d1 >= 0,
        op: opasitet((d0 + d1) / 2),
      })
    } else {
      const k = d0 / (d0 - d1)
      const xk = x(i) + k * (x(i + 1) - x(i))
      const vk = a.bergtemp + k * (b.bergtemp - a.bergtemp)
      fyll.push({ d: `M${p(x(i), a.bergtemp)} L${p(xk, vk)} L${p(x(i), a.duggpunkt)} Z`, tort: d0 > 0, op: opasitet(d0 / 2) })
      fyll.push({ d: `M${p(xk, vk)} L${p(x(i + 1), b.bergtemp)} L${p(x(i + 1), b.duggpunkt)} Z`, tort: d1 > 0, op: opasitet(d1 / 2) })
    }
  }
  return (
    <svg viewBox={`0 0 ${f.W} ${f.H}`} className="w-full" role="img" aria-label="Bergtemperatur og duggpunkt">
      {fyll.map((s, i) => (
        <path key={i} d={s.d} fill={s.tort ? 'var(--color-forhold-tort)' : 'var(--color-forhold-vatt)'} fillOpacity={s.op} />
      ))}
      <path d={line((t) => t.bergtemp, yT)} fill="none" stroke="var(--color-accent-red-400)" strokeWidth={2} />
      <path d={line((t) => t.duggpunkt, yT)} fill="none" stroke="var(--color-accent-blue-400)" strokeWidth={2} strokeDasharray="4 3" />
      <text x={2} y={f.pad.t + f.font * 0.8} fontSize={f.font} fill="var(--color-dark-200)">{tMax}°</text>
      <text x={2} y={bunn} fontSize={f.font} fill="var(--color-dark-200)">{tMin}°</text>
      <Akse timer={timer} f={f} na={na} />
    </svg>
  )
}

// Smal graf under sm-brekkpunktet, bred over
function Responsiv({ timer, Graf, na }: { timer: Time[]; Graf: typeof VannGraf; na: number }) {
  return (
    <>
      <div className="sm:hidden"><Graf timer={timer} f={SMAL} na={na} /></div>
      <div className="hidden sm:block"><Graf timer={timer} f={BRED} na={na} /></div>
    </>
  )
}

export default function ForecastChart({ timer, naIndeks = 0 }: { timer: Time[]; naIndeks?: number }) {
  return (
    <section className="kort p-sm sm:p-md">
      <h2 className="seksjon mb-sm">Vann på veggen</h2>
      <Responsiv timer={timer} Graf={VannGraf} na={naIndeks} />
      <p className="mt-xs text-xs text-text-subtle">
        Felt: vann på veggen (mm). Søyler: regn mot veggen (mm/t), kappet ved 1 mm.
      </p>

      <h2 className="seksjon mb-sm mt-lg">Bergtemperatur og duggpunkt</h2>
      <Responsiv timer={timer} Graf={TempGraf} na={naIndeks} />
      <p className="mt-xs text-xs text-text-subtle">
        <span className="text-[color:var(--color-accent-red-400)]">━</span> berg{' '}
        <span className="text-[color:var(--color-accent-blue-400)]">┅</span> duggpunkt. Grønt: berget kan tørke. Blått: det kondenserer.
      </p>
    </section>
  )
}
